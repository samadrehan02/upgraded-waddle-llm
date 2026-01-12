from typing import List, Literal, TypedDict


class TranscriptLine(TypedDict):
    speaker: Literal["patient", "doctor", "unknown"]
    text: str
    timestamp: str


class RawSession(TypedDict):
    session_id: str
    transcript: List[TranscriptLine]


class NormalizedOutput(TypedDict, total=False):
    symptoms: list
    diagnosis: list
    medications: list
    advice: list
    clinical_report: str
