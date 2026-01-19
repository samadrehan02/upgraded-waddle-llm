import chromadb
from chromadb.config import Settings
from typing import Dict, Any
import json

client = chromadb.Client(
    Settings(
        persist_directory="data/chroma",
        anonymized_telemetry=False,
    )
)

collection = client.get_or_create_collection(
    name="clinical_knowledge"
)

def build_document(structured_state: Dict[str, Any]) -> str:
    parts = []

    if structured_state.get("diagnosis"):
        parts.append("Diagnosis: " + ", ".join(structured_state["diagnosis"]))

    if structured_state.get("medications"):
        meds = [
            m["name"] + (f" {m['dosage']}" if m.get("dosage") else "")
            for m in structured_state["medications"]
        ]
        parts.append("Medications: " + ", ".join(meds))

    if structured_state.get("tests"):
        parts.append("Tests advised: " + ", ".join(structured_state["tests"]))

    if structured_state.get("symptoms"):
        parts.append(
            "Symptoms: " + ", ".join(s["name"] for s in structured_state["symptoms"])
        )

    return ". ".join(parts)

def store_consultation(
    session_id: str,
    structured_state: Dict[str, Any],
):
    document = build_document(structured_state)

    if not document.strip():
        return  # nothing useful

    metadata = {
        "diagnosis": structured_state.get("diagnosis", []),
        "tests": structured_state.get("tests", []),
        "timestamp": structured_state.get("timestamp"),
        "source": "ai_scribe_v1",
    }

    collection.add(
        ids=[session_id],
        documents=[document],
        metadatas=[metadata],
    )

    client.persist()
