from typing import List
from app.models import TranscriptLine
from app.llm.gemini import normalize_with_gemini

def run_normalization(transcript: List[TranscriptLine]) -> dict:
    return normalize_with_gemini(transcript)