from typing import Dict, Any, List
from app.models import TranscriptLine


def decide_trust(
    transcript: List[TranscriptLine],
    llm_output: Dict[str, Any] | None,
    llm_status: str,
) -> Dict[str, Any]:
    """
    Decide whether LLM output can be trusted.

    Returns:
    - trust_decision: use_llm | partial_llm | ignore_llm
    - trust_reasons: list of reasons
    """

    reasons: List[str] = []

    # Rule 1: LLM must be accepted
    if llm_status != "accepted":
        return {
            "trust_decision": "ignore_llm",
            "trust_reasons": ["llm_not_accepted"],
        }

    reasons.append("llm_output_accepted")

    # Speaker presence checks
    has_patient = any(e["speaker"] == "patient" for e in transcript)
    has_doctor = any(e["speaker"] == "doctor" for e in transcript)

    if not has_patient:
        return {
            "trust_decision": "ignore_llm",
            "trust_reasons": ["no_patient_speech"],
        }

    # --- PARTIAL TRUST PATH (patient present, doctor missing) ---
    if has_patient and not has_doctor:
        return {
            "trust_decision": "partial_llm",
            "trust_reasons": [
                "llm_output_accepted",
                "patient_present",
                "doctor_missing",
            ],
        }

    # From here onward, doctor IS present
    reasons.append("doctor_present")

    # Medication grounding rule
    meds = llm_output.get("medications", []) if llm_output else []
    if meds:
        reasons.append("medications_grounded")

    # Symptom grounding rule (strict, conservative)
    patient_text = " ".join(
        e["text"] for e in transcript if e["speaker"] == "patient"
    ).lower()

    for symptom in llm_output.get("symptoms", []):
        if symptom["name"].lower() not in patient_text:
            return {
                "trust_decision": "ignore_llm",
                "trust_reasons": ["symptom_not_grounded"],
            }

    reasons.append("symptoms_grounded")

    # All checks passed → full trust
    return {
        "trust_decision": "use_llm",
        "trust_reasons": reasons,
    }
