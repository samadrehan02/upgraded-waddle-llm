from typing import Dict, Any
from app.models import StructuredState

REQUIRED_KEYS = {
    "utterances",
    "symptoms",
    "medications",
    "diagnosis",
    "advice",
    "investigations",
    "tests",
    }

def normalize_structured_state(
    previous: StructuredState,
    candidate: Dict[str, Any],
) -> StructuredState:
    """
    Ensures candidate state:
    - contains all required keys
    - does not drop existing data
    - preserves list types
    """

    normalized: Dict[str, Any] = {}

    for key in REQUIRED_KEYS:
        if key in candidate and isinstance(candidate[key], list):
            normalized[key] = candidate[key]
        else:
            # fallback to previous state if missing or invalid
            normalized[key] = previous[key]

    normalized["patient"] = previous.get("patient", {}).copy()

    if "patient" in candidate and isinstance(candidate["patient"], dict):
        for field, value in candidate["patient"].items():
            if value is not None:
                normalized["patient"][field] = value
                
    return normalized  # type: ignore

def merge_utterances_with_speakers(
    previous_utterances,
    updated_utterances,
):
    """
    Preserve old utterances exactly.
    Replace only matching new utterances (by index) with speaker-assigned versions.
    """
    prev_by_index = {u["index"]: u for u in previous_utterances}

    merged = []

    for u in updated_utterances:
        idx = u.get("index")
        if idx in prev_by_index:
            old = prev_by_index[idx]
            merged.append({
                **old,
                "speaker": u.get("speaker", old.get("speaker")),
            })
        else:
            merged.append(u)

    return merged