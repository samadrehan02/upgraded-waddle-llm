from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.storage.session_registry import get_session
from app.core.session_models import (
    TranscriptEdit,
    StructuredEdit,
)
from app.api.websocket import apply_structured_edits

router = APIRouter(prefix="/sessions", tags=["edits"])

@router.post("/{session_id}/transcript-edits")
async def add_transcript_edit(
    session_id: str,
    edit: TranscriptEdit,
):
    try:
        session = get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    async with session.lock:
        applied = StructuredEdit(
            edit_id=edit.edit_id,
            section=edit.section,
            action=edit.action,
            value=edit.value,
            edited_by=edit.edited_by,
            edited_at=edit.edited_at or datetime.utcnow().isoformat(),
        )

        session.structured_edits.append(applied)

        session.final_structured_state = apply_structured_edits(
            session.final_structured_state,
            [applied],
        )

    return {"status": "ok"}

@router.post("/{session_id}/structured-edits")
async def add_structured_edit(
    session_id: str,
    edit: StructuredEdit,
):
    try:
        session = get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
# half these fucking things dont render but the system dosent work without all of them, i shouldve never taken this job.
    async with session.lock:
        session.structured_edits.append(
            StructuredEdit(
                edit_id=edit.edit_id,
                section=edit.section,
                action=edit.action,
                value=edit.value,
                edited_by=edit.edited_by,
                edited_at=edit.edited_at or datetime.utcnow().isoformat(),
            )
        )

    return {"status": "ok"}
