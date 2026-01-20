from typing import Dict, Any, List
from pathlib import Path
import chromadb
from chromadb.config import Settings

BASE_DIR = Path(__file__).resolve().parents[2]
CHROMA_DIR = BASE_DIR / "data" / "chroma"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

print("[CHROMA] Persist dir:", CHROMA_DIR)


client = chromadb.PersistentClient(
    path=str(CHROMA_DIR),
    settings=Settings(anonymized_telemetry=False),
)

collection = client.get_or_create_collection(
    name="clinical_knowledge"
)

def _normalize_to_strings(value: Any) -> List[str]:
    """
    Convert ANYTHING into a list of strings.
    Never raises.
    """
    out: List[str] = []

    if value is None:
        return out

    # list / tuple
    if isinstance(value, (list, tuple)):
        for item in value:
            out.extend(_normalize_to_strings(item))
        return out

    # dict
    if isinstance(value, dict):
        # prefer common keys
        for key in ("name", "value", "label"):
            if key in value and value[key]:
                out.append(str(value[key]))
                return out

        # fallback: stringify dict
        out.append(str(value))
        return out

    # scalar
    out.append(str(value))
    return out


def _safe_join(value: Any) -> str:

    parts = _normalize_to_strings(value)
    return ", ".join(p for p in parts if p.strip())

def build_document(structured_state: Dict[str, Any]) -> str:
    sections: List[str] = []

    diagnosis = _safe_join(structured_state.get("diagnosis"))
    if diagnosis:
        sections.append(f"Diagnosis: {diagnosis}")

    medications = _safe_join(structured_state.get("medications"))
    if medications:
        sections.append(f"Medications: {medications}")

    tests = _safe_join(structured_state.get("tests"))
    if tests:
        sections.append(f"Tests advised: {tests}")

    symptoms = _safe_join(structured_state.get("symptoms"))
    if symptoms:
        sections.append(f"Symptoms: {symptoms}")

    investigations = _safe_join(structured_state.get("investigations"))
    if investigations:
        sections.append(f"Investigations: {investigations}")

    advice = _safe_join(structured_state.get("advice"))
    if advice:
        sections.append(f"Advice: {advice}")

    # Absolute fallback
    if not sections:
        return "Clinical consultation recorded."

    return ". ".join(sections)

def build_metadata(structured_state: Dict[str, Any]) -> Dict[str, str]:
    metadata: Dict[str, str] = {}

    diagnosis = _safe_join(structured_state.get("diagnosis"))
    if diagnosis:
        metadata["diagnosis"] = diagnosis

    tests = _safe_join(structured_state.get("tests"))
    if tests:
        metadata["tests"] = tests

    # Always include source/version
    metadata["source"] = "ai_scribe_v1"

    return metadata

def store_consultation(
    session_id: str,
    structured_state: Dict[str, Any],
) -> None:

    try:
        document = build_document(structured_state)
        metadata = build_metadata(structured_state)

        collection.add(
            ids=[str(session_id)],
            documents=[document],
            metadatas=[metadata],
        )

        print(f"[VECTOR STORE] Stored session {session_id}")

    except Exception as e:
        # Absolute last line of defense
        print(
            f"[VECTOR STORE] HARD FAILURE for session {session_id}: {e}"
        )
