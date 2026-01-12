from datetime import datetime
from uuid import uuid4
from typing import List, Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.asr.vosk_adapter import run_vosk_asr_stream
from app.llm.gemini import normalize_with_gemini
from app.storage.session_store import (
    store_raw_transcript,
    store_structured_output,
    store_metadata,
)

ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = str(uuid4())

    transcript: List[Dict[str, Any]] = []

    try:
        async for event in run_vosk_asr_stream(ws):

            if event["type"] == "partial":
                await ws.send_json({
                    "type": "partial",
                    "text": event["text"],
                })

            elif event["type"] == "transcript":
                text = event["data"]["text"]

                transcript.append({
                    "speaker": "unknown",
                    "text": text,
                    "timestamp": datetime.now().isoformat(),
                })

                await ws.send_json({
                    "type": "transcript",
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "speaker": "unknown",
                    "text": text,
                })

            elif event["type"] == "stop":
                llm_result = normalize_with_gemini(transcript)

                store_raw_transcript(session_id, transcript)
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
        return
