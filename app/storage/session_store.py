import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List


BASE_DIR = Path("data/sessions")


def _session_dir(session_id: str) -> Path:
    date_dir = BASE_DIR / datetime.now().strftime("%Y-%m-%d")
    session_dir = date_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def store_raw_transcript(session_id: str, transcript: List[Dict[str, Any]]) -> None:
    path = _session_dir(session_id) / "raw_transcript.json"
    path.write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def store_structured_output(session_id: str, structured: Dict[str, Any]) -> None:
    path = _session_dir(session_id) / "structured_output.json"
    path.write_text(
        json.dumps(structured, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def store_metadata(
    session_id: str,
    metadata: Dict[str, Any],
) -> None:
    path = _session_dir(session_id) / "metadata.json"
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def store_structured_state(session_id: str, structured_state: dict):
    session_dir = _session_dir(session_id)
    path = session_dir / "structured_state.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(structured_state, f, ensure_ascii=False, indent=2)
