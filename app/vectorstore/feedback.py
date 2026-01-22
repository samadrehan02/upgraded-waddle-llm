from typing import Literal
import uuid
from app.vectorstore.chroma_store import collection

def store_feedback(
    session_id: str,
    feedback: Literal["like", "dislike"],
):
    collection.add(
        ids=[f"feedback_{session_id}_{uuid.uuid4().hex}"],
        documents=[f"user feedback: {feedback}"],
        metadatas=[{
            "feedback": feedback,
            "session_id": session_id,
            "source": "ui_feedback_v1",
        }],
    )
