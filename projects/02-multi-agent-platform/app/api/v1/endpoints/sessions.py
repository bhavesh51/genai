"""
Project 2 – Multi-Agent Platform
Session management endpoint
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.memory.redis_store import redis_store

router = APIRouter()


class SessionResponse(BaseModel):
    session_id: str
    state: Optional[Dict[str, Any]]
    history: List[Dict[str, Any]]


@router.get("/{session_id}", response_model=SessionResponse, summary="Get session state and history")
async def get_session(session_id: str):
    state = await redis_store.load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    history = await redis_store.get_history(session_id)
    return SessionResponse(session_id=session_id, state=state, history=history)


@router.delete("/{session_id}", summary="Delete a session")
async def delete_session(session_id: str):
    await redis_store.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}
