from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass
import time
import asyncio
import uuid
from copy import deepcopy

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.asr.vosk_adapter import run_vosk_asr_stream
from app.llm.incremental import update_structured_state
from app.llm.gemini import generate_report_from_state
from app.datasets.jsonl_export import export_session
from app.vectorstore.chroma_store import store_consultation
from app.vectorstore.suggestions import generate_system_suggestions
from app.storage.session_store import (
    store_raw_transcript,
    store_structured_state,
    store_structured_output,
    store_metadata,
    store_pdf_report,
)
from app.storage.session_registry import register_session, remove_session
from app.core.session_models import (
    SessionState,
    FinalUtterance,
    TranscriptEdit,
    StructuredEdit,
    LLMDraft,
)

# --------------------
# CONFIG
# --------------------

SILENCE_THRESHOLD_SECONDS = 12
MIN_UPDATE_INTERVAL = 20
MIN_UTTERANCES_PER_UPDATE = 3

# --------------------
# LOCAL MODELS
# --------------------

@dataclass(frozen=True)
class RawUtterance:
    utterance_id: str
    timestamp: str
    text: str


@dataclass
class ASRUtterance:
    utterance_id: str
    text: str
    confidence: float


def _new_raw_utterance(text: str) -> RawUtterance:
    return RawUtterance(
        utterance_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow().isoformat(),
        text=text,
    )


def _base_structured_state() -> Dict[str, Any]:
    return {
        "patient": {"name": None, "age": None, "gender": None},
        "utterances": [],
        "symptoms": [],
        "medications": [],
        "diagnosis": [],
        "advice": [],
        "investigations": [],
        "tests": [],
    }

# --------------------
# EDIT APPLICATION
# --------------------

def apply_transcript_edits(
    transcript: List[FinalUtterance],
    edits: List[TranscriptEdit],
) -> List[FinalUtterance]:
    by_id = {u.utterance_id: u for u in transcript}
    edited = dict(by_id)

    for e in edits:
        u = edited.get(e.utterance_id)
        if not u:
            continue

        if e.field == "text":
            edited[e.utterance_id] = FinalUtterance(
                utterance_id=u.utterance_id,
                timestamp=u.timestamp,
                text=e.new_value,
                speaker=u.speaker,
            )
        elif e.field == "speaker":
            edited[e.utterance_id] = FinalUtterance(
                utterance_id=u.utterance_id,
                timestamp=u.timestamp,
                text=u.text,
                speaker=e.new_value,
            )

    return [edited[u.utterance_id] for u in transcript]


def apply_structured_edits(
    state: Dict[str, Any],
    edits: List[StructuredEdit],
) -> Dict[str, Any]:
    out = deepcopy(state)

    for e in edits:
        section = e.section
        if section not in out:
            continue

        if e.action == "add":
            out[section].append(e.value)

        elif e.action == "remove":
            out[section] = [v for v in out[section] if v != e.value]

        elif e.action == "modify":
            for i, v in enumerate(out[section]):
                if isinstance(v, dict) and v.get("name") == e.value.get("name"):
                    out[section][i] = e.value

    return out

# --------------------
# ROUTER
# --------------------

ws_router = APIRouter()

@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    now = datetime.utcnow()
    session_id = now.strftime("%Y-%m-%d_%H-%M-%S_%f")
    session_date = now.strftime("%Y-%m-%d")

    state = SessionState(
        session_id=session_id,
        session_date=session_date,
        final_structured_state=_base_structured_state(),
    )
    register_session(state)

    last_llm_update_time = 0.0
    llm_lock = asyncio.Lock()

    # --------------------
    # INCREMENTAL LLM UPDATE (CORRECT)
    # --------------------

    async def run_incremental_update(
        new_utts: List[FinalUtterance],
        force: bool = False,
    ):
        nonlocal last_llm_update_time

        if not new_utts:
            return

        if not force and len(new_utts) < MIN_UTTERANCES_PER_UPDATE:
            return

        now_ts = time.time()
        if not force and now_ts - last_llm_update_time < MIN_UPDATE_INTERVAL:
            return

        async with llm_lock:
            loop = asyncio.get_running_loop()

            async with state.lock:
                base_state = deepcopy(state.final_structured_state)

            utterance_dicts = [
                {
                    "index": i + 1,
                    "speaker": u.speaker,
                    "text": u.text,
                    "timestamp": u.timestamp,
                }
                for i, u in enumerate(new_utts)
            ]

            updated_state = await loop.run_in_executor(
                None,
                update_structured_state,
                base_state,
                utterance_dicts,
            )

            draft = LLMDraft(
                draft_id=str(uuid.uuid4()),
                created_at=datetime.utcnow().isoformat(),
                input_utterance_ids=[u.utterance_id for u in new_utts],
                structured_patch=updated_state,
                model="gemini",
            )

            async with state.lock:
                state.llm_drafts.append(draft)
                state.final_structured_state = updated_state
                state.last_processed_index = len(state.final_transcript)
                last_llm_update_time = time.time()

    # --------------------
    # SILENCE WATCHER
    # --------------------

    async def silence_watcher():
        while True:
            await asyncio.sleep(1)

            async with state.lock:
                if not state.active:
                    return

                if time.monotonic() - state.last_text_time < SILENCE_THRESHOLD_SECONDS:
                    continue

                if state.last_processed_index >= len(state.final_transcript):
                    continue

                pending = state.final_transcript[state.last_processed_index :]

            await run_incremental_update(pending)

    silence_task = asyncio.create_task(silence_watcher())

    # --------------------
    # MAIN LOOP
    # --------------------

    try:
        async for event in run_vosk_asr_stream(ws):

            if event["type"] == "partial":
                await ws.send_json({"type": "partial", "text": event["text"]})
                continue

            if event["type"] == "transcript":
                text = event["data"]["text"]

                raw = _new_raw_utterance(text)
                final = FinalUtterance(
                    utterance_id=raw.utterance_id,
                    timestamp=raw.timestamp,
                    text=text,
                    speaker="unknown",
                )

                async with state.lock:
                    state.raw_transcript.append(raw)
                    state.asr_utterances.append(
                        ASRUtterance(raw.utterance_id, text, 1.0)
                    )
                    state.final_transcript.append(final)
                    state.last_text_time = time.monotonic()

                await ws.send_json({
                    "type": "transcript",
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "speaker": "unknown",
                    "text": text,
                    "utterance_id": raw.utterance_id,
                })
                continue

            # ---------------- STOP ----------------

            if event["type"] == "stop":
                async with state.lock:
                    state.active = False

                silence_task.cancel()

                async with state.lock:
                    remaining = state.final_transcript[state.last_processed_index :]

                if remaining:
                    await run_incremental_update(remaining, force=True)

                async with state.lock:
                    transcript = apply_transcript_edits(
                        state.final_transcript,
                        state.transcript_edits,
                    )

                    structured = apply_structured_edits(
                        state.final_structured_state,
                        state.structured_edits,
                    )

                    structured["utterances"] = [
                        {
                            "index": i + 1,
                            "speaker": u.speaker,
                            "text": u.text,
                            "timestamp": u.timestamp,
                        }
                        for i, u in enumerate(transcript)
                    ]

                    state.final_transcript = transcript
                    state.final_structured_state = structured

                loop = asyncio.get_running_loop()

                llm_result = await loop.run_in_executor(
                    None,
                    generate_report_from_state,
                    state.final_structured_state,
                )

                clinical_report = llm_result.get("data", {}).get("clinical_report", "")

                store_pdf_report(
                    state.session_id,
                    session_date,
                    state.final_structured_state,
                    clinical_report,
                )

                store_raw_transcript(
                    state.session_id,
                    [u.__dict__ for u in state.raw_transcript],
                )

                store_raw_transcript(
                    f"{state.session_id}_corrected",
                    [u.__dict__ for u in state.final_transcript],
                )

                store_structured_state(
                    state.session_id,
                    state.final_structured_state,
                )

                store_structured_output(state.session_id, llm_result)

                store_metadata(
                    state.session_id,
                    {
                        "session_id": state.session_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "model": llm_result.get("model"),
                        "patient": state.final_structured_state.get("patient"),
                    },
                )

                store_consultation(
                    session_id=state.session_id,
                    structured_state=state.final_structured_state,
                )

                export_session(
                    session_id=state.session_id,
                    structured_state=state.final_structured_state,
                )

                suggestions = await loop.run_in_executor(
                    None,
                    generate_system_suggestions,
                    state.final_structured_state,
                )

                await ws.send_json({
                    "type": "structured",
                    "session_id": state.session_id,
                    "structured_state": state.final_structured_state,
                    "clinical_report": clinical_report,
                    "pdf": f"/data/sessions/{session_date}/{state.session_id}/clinical_report.pdf",
                    "system_suggestions": suggestions,
                })

                remove_session(state.session_id)
                break

    except WebSocketDisconnect:
        async with state.lock:
            state.active = False
        silence_task.cancel()
        remove_session(state.session_id)
