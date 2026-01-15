from typing import TypedDict, List, Literal, Optional

class TranscriptLine(TypedDict):
    speaker : Literal["patient", "doctor", "unknown"]
    text : str
    timestamp : str

class Utterance(TypedDict):
    index: int
    speaker: Literal["patient", "doctor", "unknown"]
    text: str
    timestamp: str


class Symptom(TypedDict):
    name: str
    duration: Optional[str]


class Medication(TypedDict):
    name: str
    dosage: Optional[str]


class StructuredState(TypedDict):
    utterances: List[Utterance]
    symptoms: List[Symptom]
    medications: List[Medication]
    diagnosis: List[str]
    advice: List[str]
    
class Investigation(TypedDict):
    name: str
    value: Optional[str]

class StructuredState(TypedDict):
    utterances: List[Utterance]
    symptoms: List[Symptom]
    medications: List[Medication]
    diagnosis: List[str]
    advice: List[str]
    investigations: List[Investigation]
    tests: List[str]
