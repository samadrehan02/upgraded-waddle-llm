from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, field
import time
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.datasets.jsonl_export import export_session
from app.asr.vosk_adapter import run_vosk_asr_stream
from app.llm.incremental import update_structured_state
from app.llm.gemini import generate_report_from_state
from app.vectorstore.chroma_store import store_consultation
from app.vectorstore.suggestions import generate_system_suggestions
from app.storage.session_store import (
    store_raw_transcript,
    store_structured_output,
    store_structured_state,
    store_metadata,
    store_pdf_report,
)

ws_router = APIRouter()

SILENCE_THRESHOLD_SECONDS = 12
MIN_UPDATE_INTERVAL = 20
MIN_UTTERANCES_PER_UPDATE = 3

EXTRACT_TRIGGERS = (
    "pain", "fever", "cough", "cold", "vomit", "headache",
    "दर्द", "बुखार", "खांसी",
    "day", "days", "din", "saal", "year",
    "tablet", "medicine", "mg", "dose",
    "bp", "pressure", "temperature", "temp",
    "blood pressure",
    "test", "जांच", "karwa", "करवा",
)

@dataclass
class SessionState:
    session_id: str
    session_date: str

    transcript: List[Dict[str, Any]] = field(default_factory=list)
    structured: Dict[str, Any] = field(default_factory=dict)

    last_processed_index: int = 0
    last_text_time: float = field(default_factory=time.monotonic)

    active: bool = True
    pause_triggered: bool = False

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def worth_llm_call(utterances: List[Dict[str, Any]]) -> bool:
    for u in utterances:
        text = u.get("text", "").lower()
        if any(trigger in text for trigger in EXTRACT_TRIGGERS):
            return True
    return False


@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    now = datetime.now()
    session_id = now.strftime("%Y-%m-%d_%H-%M-%S_%f")
    session_date = now.strftime("%Y-%m-%d")

    state = SessionState(
        session_id=session_id,
        session_date=session_date,
        structured={
            "patient": {"name": None, "age": None, "gender": None},
            "utterances": [],
            "symptoms": [],
            "medications": [],
            "diagnosis": [],
            "advice": [],
            "investigations": [],
            "tests": [],
        },
    )

    last_llm_update_time = 0.0
    llm_lock = asyncio.Lock()

    async def run_incremental_update(
        state: SessionState,
        new_utterances: List[Dict[str, Any]],
        force: bool = False,
    ):
        nonlocal last_llm_update_time

        if not new_utterances:
            return

        if not force and len(new_utterances) < MIN_UTTERANCES_PER_UPDATE:
            return

        if not force and not worth_llm_call(new_utterances):
            async with state.lock:
                state.last_processed_index = max(
                    u["index"] for u in new_utterances if "index" in u
                )
            return

        now_ts = time.time()
        if not force and now_ts - last_llm_update_time < MIN_UPDATE_INTERVAL:
            return

        async with llm_lock:
            try:
                loop = asyncio.get_running_loop()
                t0 = time.time()

                print(
                    f"[SESSION {state.session_id}] "
                    f"INCREMENTAL UPDATE START ({len(new_utterances)} utterances)"
                )

                updated_state = await loop.run_in_executor(
                    None,
                    update_structured_state,
                    state.structured,
                    new_utterances,
                )

                print(
                    f"[SESSION {state.session_id}] "
                    f"INCREMENTAL UPDATE DONE in {time.time() - t0:.2f}s"
                )

                async with state.lock:
                    state.structured = updated_state
                    state.last_processed_index = max(
                        u["index"] for u in new_utterances if "index" in u
                    )
                    last_llm_update_time = time.time()

            except Exception as e:
                print(f"[SESSION {state.session_id}] Incremental update failed: {e}")

    async def check_patient_silence():
        while True:
            await asyncio.sleep(1)

            async with state.lock:
                if not state.active:
                    return

                silence_duration = time.monotonic() - state.last_text_time

                should_trigger = (
                    not state.pause_triggered
                    and silence_duration >= SILENCE_THRESHOLD_SECONDS
                    and state.last_processed_index < len(state.transcript)
                )

                if should_trigger:
                    state.pause_triggered = True
                    new_utterances = [
                        u for u in state.transcript
                        if u["index"] > state.last_processed_index
                    ]
                else:
                    new_utterances = None

            if new_utterances:
                await run_incremental_update(state, new_utterances)

    silence_task = asyncio.create_task(check_patient_silence())

    try:
        async for event in run_vosk_asr_stream(ws):

            if event["type"] == "partial":
                await ws.send_json({
                    "type": "partial",
                    "text": event["text"],
                })

            elif event["type"] == "transcript":
                text = event["data"]["text"]

                utterance = {
                    "index": len(state.transcript) + 1,
                    "speaker": "unknown",
                    "text": text,
                    "timestamp": datetime.now().isoformat(),
                }

                async with state.lock:
                    state.transcript.append(utterance)
                    state.structured["utterances"].append(utterance)
                    state.last_text_time = time.monotonic()
                    state.pause_triggered = False

                await ws.send_json({
                    "type": "transcript",
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "speaker": "unknown",
                    "text": text,
                })

            elif event["type"] == "stop":
                async with state.lock:
                    state.active = False

                silence_task.cancel()

                async with state.lock:
                    new_utterances = [
                        u for u in state.transcript
                        if u["index"] > state.last_processed_index
                    ]

                if new_utterances:
                    await run_incremental_update(state, new_utterances, force=True)

                loop = asyncio.get_running_loop()
                t0 = time.time()
                print(f"[SESSION {state.session_id}] REPORT GENERATION START")

                llm_result = await loop.run_in_executor(
                    None,
                    generate_report_from_state,
                    state.structured,
                )

                clinical_report = (
                    llm_result.get("data", {}).get("clinical_report", "")
                    if isinstance(llm_result, dict)
                    else ""
                )

                print(f"[SESSION {state.session_id}] PDF GENERATION START")

                pdf_path = store_pdf_report(
                    state.session_id,
                    session_date=state.session_date,
                    structured_state=state.structured,
                    clinical_report=clinical_report,
                )

                print(
                    f"[SESSION {state.session_id}] REPORT GENERATION DONE "
                    f"in {time.time() - t0:.2f}s"
                )

                async with state.lock:
                    transcript_copy = list(state.transcript)
                    structured_copy = dict(state.structured)

                store_raw_transcript(state.session_id, transcript_copy)
                store_structured_state(state.session_id, structured_copy)
                store_structured_output(state.session_id, llm_result)

                store_metadata(
                    state.session_id,
                    {
                        "session_id": state.session_id,
                        "timestamp": datetime.now().isoformat(),
                        "model": llm_result.get("model"),
                        "prompt_version": llm_result.get("prompt_version"),
                        "patient": structured_copy["patient"],
                    },
                )

                store_consultation(
                    session_id=state.session_id,
                    structured_state=structured_copy,
                )

                export_session(
                    session_id=state.session_id,
                    structured_state=structured_copy,
                )

                system_suggestions = await loop.run_in_executor(
                    None,
                    generate_system_suggestions,
                    structured_copy,
                )

                await ws.send_json({
                    "type": "structured",
                    "structured_state": structured_copy,
                    "clinical_report": clinical_report,
                    "pdf": f"/data/sessions/{state.session_date}/{state.session_id}/clinical_report.pdf",
                    "system_suggestions": system_suggestions,
                    "meta": {
                        "model": llm_result.get("model"),
                        "error": llm_result.get("error"),
                    }
                })

                break

    except WebSocketDisconnect:
        async with state.lock:
            state.active = False
        silence_task.cancel()
        return
