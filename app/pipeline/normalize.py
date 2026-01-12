from typing import List
from app.models import TranscriptLine
from app.llm.gemini import normalize_with_gemini
from app.pipeline.evaluate import build_evaluation_record


def run_normalization(transcript: List[TranscriptLine]) -> dict:
    llm_result = normalize_with_gemini(transcript)
    evaluation = build_evaluation_record(transcript, llm_result)
    return evaluation
