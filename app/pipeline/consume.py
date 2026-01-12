from typing import Dict, Any


def consume_evaluation(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decide what output is allowed to be surfaced to the user.
    """

    decision = evaluation.get("trust_decision")

    if decision == "use_llm":
        return {
            "status": "ok",
            "clinical_report": evaluation["llm_output"]["clinical_report"],
        }

    if decision == "partial_llm":
        return {
            "status": "partial",
            "extracted_facts": {
                "symptoms": evaluation["llm_output"].get("symptoms", []),
            },
            "message": (
                "Preliminary information extracted. "
                "Doctor review required for diagnosis and treatment."
            ),
        }

    return {
        "status": "blocked",
        "message": (
            "Clinical report could not be generated automatically. "
            "Please consult a doctor."
        ),
    }

