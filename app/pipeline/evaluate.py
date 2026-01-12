from typing import Dict, Any, List
from app.models import TranscriptLine
from app.pipeline.trust import decide_trust

def build_evaluation_record(transcript, llm_result):
    accepted = "data" in llm_result

    llm_status = "accepted" if accepted else "rejected"
    llm_output = llm_result.get("data")

    trust = decide_trust(
        transcript=transcript,
        llm_output=llm_output,
        llm_status=llm_status,
    )

    return {
        "raw_transcript": transcript,
        "llm_status": llm_status,
        "llm_error": None if accepted else llm_result.get("error"),
        "llm_output": llm_output,
        "trust_decision": trust["trust_decision"],
        "trust_reasons": trust["trust_reasons"],
        "notes": [],
    }
