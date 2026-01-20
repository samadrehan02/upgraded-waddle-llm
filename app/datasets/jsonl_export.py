import json
from pathlib import Path
from typing import Dict, Any, List


BASE_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = BASE_DIR / "data" / "datasets"
DATASET_DIR.mkdir(parents=True, exist_ok=True)

JSONL_PATH = DATASET_DIR / "clinical_v1.jsonl"


def _normalize_list(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        out = []
        for v in value:
            out.extend(_normalize_list(v))
        return out

    if isinstance(value, dict):
        for key in ("name", "value", "label"):
            if key in value and value[key]:
                return [str(value[key])]
        return [str(value)]

    return [str(value)]


def export_session(
    session_id: str,
    structured_state: Dict[str, Any],
    language: str = "hi",
):
    record = {
        "schema_version": "v1",
        "session_id": session_id,
        "language": language,
        "input": {
            "symptoms": _normalize_list(structured_state.get("symptoms")),
            "investigations": _normalize_list(structured_state.get("investigations")),
        },
        "output": {
            "diagnosis": _normalize_list(structured_state.get("diagnosis")),
            "tests": _normalize_list(structured_state.get("tests")),
            "medications": _normalize_list(structured_state.get("medications")),
            "advice": _normalize_list(structured_state.get("advice")),
        },
        "meta": {
            "source": "ai_scribe_v1",
        },
    }

    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
