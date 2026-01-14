from datetime import datetime
from typing import List, Dict, Any
import time
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.asr.vosk_adapter import run_vosk_asr_stream
from app.llm.incremental import update_structured_state
from app.llm.gemini import generate_report_from_state
from app.storage.session_store import (
    store_raw_transcript,
    store_structured_output,
    store_structured_state,
    store_metadata,
)

ws_router = APIRouter()

SILENCE_THRESHOLD_SECONDS = 8


@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    now = datetime.now()
    session_id = now.strftime("%Y-%m-%d_%H-%M-%S_%f")

    transcript: List[Dict[str, Any]] = []

    session_state = {
        "structured": {
            "utterances": [],
            "symptoms": [],
            "medications": [],
            "diagnosis": [],
            "advice": [],
        },
        "last_processed_index": 0,
    }

    last_speaker: str | None = None
    last_text_time = time.monotonic()
    pause_triggered = False
    active = True

    async def check_patient_silence():
        nonlocal last_speaker, last_text_time, pause_triggered, active

        while active:
            await asyncio.sleep(1)

            silence_duration = time.monotonic() - last_text_time

            if (
                not pause_triggered
                and last_speaker == "patient"
                and silence_duration >= SILENCE_THRESHOLD_SECONDS
                and session_state["last_processed_index"] < len(transcript)
            ):
                pause_triggered = True

                new_utterances = [
                    u for u in transcript
                    if u["index"] > session_state["last_processed_index"]
                ]

                print(
                    f"[SESSION {session_id}] "
                    f"Incremental update with {len(new_utterances)} utterances"
                )

                try:
                    updated_state = update_structured_state(
                        session_state["structured"],
                        new_utterances,
                    )
                    session_state["structured"] = updated_state
                    session_state["last_processed_index"] = max(
                        u["index"] for u in new_utterances
                    )
                except Exception as e:
                    print(
                        f"[SESSION {session_id}] "
                        f"Incremental update failed: {e}"
                    )

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

                # TEMP: treat all speech as patient for pause detection
                last_speaker = "patient"
                last_text_time = time.monotonic()
                pause_triggered = False

                await ws.send_json({
                    "type": "transcript",
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "speaker": "unknown",
                    "text": text,
                })

            elif event["type"] == "stop":
                new_utterances = [
                    u for u in transcript
                    if u["index"] > session_state["last_processed_index"]
                ]

                if new_utterances:
                    try:
                        updated_state = update_structured_state(
                            session_state["structured"],
                            new_utterances,
                        )
                        session_state["structured"] = updated_state
                        session_state["last_processed_index"] = max(
                            u["index"] for u in new_utterances
                        )
                    except Exception as e:
                        print(
                            f"[SESSION {session_id}] "
                            f"Final incremental update failed: {e}"
                        )

                llm_result = generate_report_from_state(session_state["structured"])

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
                    },
                )

                await ws.send_json({
                    "type": "structured",
                    "data": llm_result,
                })

                transcript.clear()

    except WebSocketDisconnect:
        active = False
        silence_task.cancel()
        return
