import json
from datetime import datetime
from vosk import Model, KaldiRecognizer

MODEL_PATH = "models/vosk/hi/vosk-model-hi-0.22"
SAMPLE_RATE = 16000
model = Model(MODEL_PATH)


async def run_vosk_asr_stream(ws):
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)
    recognizer.SetPartialWords(True)

    while True:
        msg = await ws.receive()

        if "text" in msg and msg["text"]:
            raw = msg["text"].strip()

            if raw == "stop":
                yield {"type": "stop"}
                break

            try:
                payload = json.loads(raw)
                if payload.get("type") == "stop":
                    yield {"type": "stop"}
                    break
            except json.JSONDecodeError:
                pass

        if "bytes" not in msg:
            continue

        data = msg["bytes"]

        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            text = result.get("text", "").strip()

            if text:
                yield {
                    "type": "transcript",
                    "data": {
                        "speaker": "unknown",
                        "text": text,
                        "timestamp": datetime.now().isoformat(),
                    },
                }
        else:
            partial = json.loads(recognizer.PartialResult())
            if partial.get("partial"):
                yield {
                    "type": "partial",
                    "text": partial["partial"],
                }
