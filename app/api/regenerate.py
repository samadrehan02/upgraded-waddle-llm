from fastapi import APIRouter, HTTPException
from datetime import datetime
import asyncio

from app.storage.session_registry import get_session
from app.llm.gemini import generate_report_from_state
from app.storage.session_store import store_pdf_report, get_suggestions

router = APIRouter(prefix="/sessions", tags=["regenerate"])

@router.post("/{session_id}/regenerate")
async def regenerate_report(session_id: str):
    try:
        session = get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    async with session.lock:
        structured_state = session.final_structured_state

    loop = asyncio.get_running_loop()

    llm_result = await loop.run_in_executor(
        None,
        generate_report_from_state,
        structured_state,
    )

    clinical_report = (
        llm_result.get("data", {}).get("clinical_report", "")
        if isinstance(llm_result, dict)
        else ""
    )

    pdf_path = store_pdf_report(
        session.session_id,
        session.session_date,
        structured_state,
        clinical_report,
    )

    async with session.lock:
        session.final_clinical_report = clinical_report

    return {
        "status": "ok",
        "pdf": f"/data/sessions/{session.session_date}/{session.session_id}/clinical_report.pdf",
        "clinical_report": clinical_report,
    }

@router.get("/{session_id}/suggestions")
async def fetch_suggestions(session_id: str):
    """
    Return the vector-store suggestions (similar cases) for the session.
    """
    data = get_suggestions(session_id)
    return data