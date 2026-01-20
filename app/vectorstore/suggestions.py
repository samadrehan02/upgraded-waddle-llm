from typing import Dict, Any, List
from collections import Counter

# Reuse the same Chroma collection
from app.vectorstore.chroma_store import collection


# ----------------------------
# Helpers
# ----------------------------

def _normalize_list(value: Any) -> List[str]:
    """
    Convert anything into a list of strings.
    Never raises.
    """
    out: List[str] = []

    if value is None:
        return out

    if isinstance(value, list):
        for v in value:
            out.extend(_normalize_list(v))
        return out

    if isinstance(value, dict):
        for key in ("name", "value", "label"):
            if key in value and value[key]:
                out.append(str(value[key]))
                return out
        out.append(str(value))
        return out

    out.append(str(value))
    return out


def build_query_text(structured_state: Dict[str, Any]) -> str:
    """
    Build a conservative query using ONLY reliable signals.
    """
    parts: List[str] = []

    symptoms = _normalize_list(structured_state.get("symptoms"))
    if symptoms:
        parts.append("Symptoms: " + ", ".join(symptoms))

    investigations = _normalize_list(structured_state.get("investigations"))
    if investigations:
        parts.append("Investigations: " + ", ".join(investigations))

    if not parts:
        return ""

    return ". ".join(parts)


# ----------------------------
# Core suggestion engine
# ----------------------------

def generate_system_suggestions(
    structured_state: Dict[str, Any],
    top_k: int = 7,
) -> Dict[str, Any]:
    """
    Always returns a suggestion object.
    Never throws.
    """
    query_text = build_query_text(structured_state)

    # If we have nothing reliable to query with
    if not query_text.strip():
        return {
            "based_on_cases": 0,
            "diagnosis": [],
            "tests": [],
            "medications": [],
        }

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=top_k,
        )
    except Exception as e:
        print("[SUGGESTIONS] Chroma query failed:", e)
        return {
            "based_on_cases": 0,
            "diagnosis": [],
            "tests": [],
            "medications": [],
        }

    diagnosis_counter = Counter()
    tests_counter = Counter()
    meds_counter = Counter()

    metadatas = results.get("metadatas", [[]])
    if not metadatas or not metadatas[0]:
        return {
            "based_on_cases": 0,
            "diagnosis": [],
            "tests": [],
            "medications": [],
        }

    for meta in metadatas[0]:
        if not isinstance(meta, dict):
            continue

        if "diagnosis" in meta:
            diagnosis_counter.update(
                [d.strip() for d in meta["diagnosis"].split(",") if d.strip()]
            )

        if "tests" in meta:
            tests_counter.update(
                [t.strip() for t in meta["tests"].split(",") if t.strip()]
            )

        if "medications" in meta:
            meds_counter.update(
                [m.strip() for m in meta["medications"].split(",") if m.strip()]
            )

    return {
        "based_on_cases": len(metadatas[0]),
        "diagnosis": [
            {"name": k, "count": v}
            for k, v in diagnosis_counter.most_common(3)
        ],
        "tests": [
            {"name": k, "count": v}
            for k, v in tests_counter.most_common(3)
        ],
        "medications": [
            {"name": k, "count": v}
            for k, v in meds_counter.most_common(3)
        ],
    }
