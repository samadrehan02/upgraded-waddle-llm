from dataclasses import dataclass, field
from typing import Dict, Any, List
import asyncio

@dataclass
class FinalUtterance:
    utterance_id: str
    timestamp: str
    text: str
    speaker: str

@dataclass
class TranscriptEdit:
    edit_id: str
    utterance_id: str
    field: str
    old_value: str
    new_value: str
    edited_by: str
    edited_at: str

@dataclass
class StructuredEdit:
    edit_id: str
    section: str
    action: str
    value: Dict[str, Any]
    edited_by: str
    edited_at: str

@dataclass
class LLMDraft:
    draft_id: str
    created_at: str
    input_utterance_ids: List[str]
    structured_patch: Dict[str, Any]
    model: str
    accepted: bool = False

@dataclass
class SessionState:
    session_id: str
    session_date: str

    raw_transcript: list = field(default_factory=list)
    asr_utterances: list = field(default_factory=list)
    llm_drafts: List[LLMDraft] = field(default_factory=list)
    transcript_edits: List[TranscriptEdit] = field(default_factory=list)
    structured_edits: List[StructuredEdit] = field(default_factory=list)
    final_transcript: List[FinalUtterance] = field(default_factory=list)
    final_structured_state: Dict[str, Any] = field(default_factory=dict)
    final_clinical_report: str | None = None

    active: bool = True
    last_text_time: float = 0.0
    last_processed_index: int = 0

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
