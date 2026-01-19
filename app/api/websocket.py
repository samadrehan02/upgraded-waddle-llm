from datetime import datetime
from typing import List, Dict, Any
import time
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.vectorstore.chroma_store import store_consultation
from app.asr.vosk_adapter import run_vosk_asr_stream
from app.llm.incremental import update_structured_state
from app.llm.gemini import generate_report_from_state
from app.storage.session_store import (
    store_raw_transcript,
    store_structured_output,
    store_structured_state,
    store_metadata,
    store_pdf_report,
)

ws_router = APIRouter()

SILENCE_THRESHOLD_SECONDS = 12
MIN_UPDATE_INTERVAL = 20  # seconds
MIN_UTTERANCES_PER_UPDATE = 3 

EXTRACT_TRIGGERS = (
    # symptoms
    "pain", "fever", "cough", "cold", "vomit", "headache",
    "दर्द", "बुखार", "खांसी",

    # duration / numbers
    "day", "days", "din", "saal", "year",

    # medications
    "tablet", "medicine", "mg", "dose",

    # investigations
    "bp", "pressure", "temperature", "temp",
    "blood pressure",

    # tests
    "test", "जांच", "karwa", "करवा",
)


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

    transcript: List[Dict[str, Any]] = []

    session_state = {
        "structured": {
            "patient": {
                "name": None,
                "age": None,
                "gender": None,
            },
            "utterances": [],
            "symptoms": [],
            "medications": [],
            "diagnosis": [],
            "advice": [],
            "investigations": [],
            "tests": [],
        },
        "last_processed_index": 0,
    }

    last_text_time = time.monotonic()
    last_llm_update_time = 0.0
    pause_triggered = False
    llm_in_flight = False
    active = True

    async def run_incremental_update(
        new_utterances: List[Dict[str, Any]],
        force: bool = False,
    ):
        nonlocal llm_in_flight, last_llm_update_time

        if not new_utterances or llm_in_flight:
            return

        if not force and len(new_utterances) < MIN_UTTERANCES_PER_UPDATE:
            return

        if not force and not worth_llm_call(new_utterances):
            session_state["last_processed_index"] = max(
                u["index"] for u in new_utterances if "index" in u
            )
            return

        now_ts = time.time()
        if not force and now_ts - last_llm_update_time < MIN_UPDATE_INTERVAL:
            return

        llm_in_flight = True

        try:
            loop = asyncio.get_running_loop()

            t0 = time.time()
            print(
                f"[SESSION {session_id}] "
                f"INCREMENTAL UPDATE START ({len(new_utterances)} utterances)"
            )

            updated_state = await loop.run_in_executor(
                None,
                update_structured_state,
                session_state["structured"],
                new_utterances,
            )

            print(
                f"[SESSION {session_id}] "
                f"INCREMENTAL UPDATE DONE in {time.time() - t0:.2f}s"
            )

            session_state["structured"] = updated_state
            session_state["last_processed_index"] = max(
                u["index"] for u in new_utterances if "index" in u
            )
            last_llm_update_time = time.time()

        except Exception as e:
            print(f"[SESSION {session_id}] Incremental update failed: {e}")

        finally:
            llm_in_flight = False

    async def check_patient_silence():
        nonlocal pause_triggered, last_text_time, active

        while active:
            await asyncio.sleep(1)

            silence_duration = time.monotonic() - last_text_time

            if (
                not pause_triggered
                and not llm_in_flight
                and silence_duration >= SILENCE_THRESHOLD_SECONDS
                and session_state["last_processed_index"] < len(transcript)
            ):
                pause_triggered = True

                new_utterances = [
                    u for u in transcript
                    if u["index"] > session_state["last_processed_index"]
                ]

                await run_incremental_update(new_utterances)

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
                    "index": len(transcript) + 1,
                    "speaker": "unknown",
                    "text": text,
                    "timestamp": datetime.now().isoformat(),
                }

                transcript.append(utterance)
                session_state["structured"]["utterances"].append(utterance)

                last_text_time = time.monotonic()
                pause_triggered = False

                await ws.send_json({
                    "type": "transcript",
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "speaker": "unknown",
                    "text": text,
                })

            elif event["type"] == "stop":
                if session_state["last_processed_index"] < len(transcript):
                    new_utterances = [
                        u for u in transcript
                        if u["index"] > session_state["last_processed_index"]
                    ]
                    await run_incremental_update(new_utterances, force=True)

                loop = asyncio.get_running_loop()
                t0 = time.time()
                print(f"[SESSION {session_id}] REPORT GENERATION START")

                llm_result = await loop.run_in_executor(
                    None,
                    generate_report_from_state,
                    session_state["structured"],
                )

                if "data" not in llm_result:
                    print(
                        f"[SESSION {session_id}] REPORT GENERATION FAILED:",
                        llm_result,
                    )

                clinical_report = (
                    llm_result.get("data", {}).get("clinical_report", "")
                    if isinstance(llm_result, dict)
                    else ""
                )

                print(f"[SESSION {session_id}] PDF GENERATION START")

                pdf_path = store_pdf_report(
                    session_id,
                    session_date=session_date,
                    structured_state=session_state["structured"],
                    clinical_report=clinical_report,
                )

                print(f"[SESSION {session_id}] PDF GENERATION DONE: {pdf_path}")
                print(
                    f"[SESSION {session_id}] REPORT GENERATION DONE "
                    f"in {time.time() - t0:.2f}s"
                )

                store_raw_transcript(session_id, transcript)
                store_structured_state(session_id, session_state["structured"])
                store_structured_output(session_id, llm_result)

                store_metadata(
                    session_id,
                    {
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                        "model": llm_result.get("model"),
                        "prompt_version": llm_result.get("prompt_version"),
                        "patient": session_state["structured"]["patient"],
                    },
                )
                store_consultation(
                    session_id=session_id,
                    structured_state=session_state["structured"]
                )
                await ws.send_json({
                    "type": "structured",
                    "data": llm_result,
                    "pdf": f"/data/sessions/{session_date}/{session_id}/clinical_report.pdf",
                })

                transcript.clear()

    except WebSocketDisconnect:
        active = False
        silence_task.cancel()
        return
