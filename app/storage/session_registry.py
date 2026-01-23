from typing import Dict
from app.core.session_models import SessionState

_sessions: Dict[str, SessionState] = {}

def register_session(session: SessionState):
    _sessions[session.session_id] = session

def get_session(session_id: str) -> SessionState:
    return _sessions[session_id]

def remove_session(session_id: str):
    _sessions.pop(session_id, None)