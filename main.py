from uuid import uuid4

from app.asr.vosk_adapter import run_vosk_asr
from app.pipeline.normalize import run_normalization
from app.storage import store_evaluation

session_id = str(uuid4())

transcript = run_vosk_asr()

evaluation = run_normalization(transcript)

store_evaluation(session_id, evaluation)
