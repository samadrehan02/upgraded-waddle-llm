from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.storage.session_registry import get_session
from app.core.session_models import (
    TranscriptEdit,
    StructuredEdit,
)

router = APIRouter(prefix="/sessions", tags=["edits"])


# ----------------------------
# Transcript edits
# ----------------------------

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
        session.transcript_edits.append(
            TranscriptEdit(
                edit_id=edit.edit_id,
                utterance_id=edit.utterance_id,
                field=edit.field,
                old_value=edit.old_value,
                new_value=edit.new_value,
                edited_by=edit.edited_by,
                edited_at=edit.edited_at or datetime.utcnow().isoformat(),
            )
        )

    return {"status": "ok"}


# ----------------------------
# Structured edits
# ----------------------------

@router.post("/{session_id}/structured-edits")
async def add_structured_edit(
    session_id: str,
    edit: StructuredEdit,
):
    try:
        session = get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

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
