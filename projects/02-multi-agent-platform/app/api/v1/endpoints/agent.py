"""
Project 2 – Multi-Agent Platform
Agent execution endpoint
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.agents.graph import AgentState, agent_graph
from app.memory.redis_store import redis_store

logger = logging.getLogger(__name__)
router = APIRouter()


class AgentRunRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=8192)
    session_id: Optional[str] = Field(None, description="Existing session ID for continuation")


class AgentRunResponse(BaseModel):
    session_id: str
    status: str
    current_step: str
    final_output: Optional[str] = None
    requires_human_review: bool = False


@router.post("/run", response_model=AgentRunResponse, summary="Run the multi-agent pipeline")
async def run_agent(request: AgentRunRequest):
    session_id = request.session_id or str(uuid.uuid4())

    # Load existing state or create fresh
    existing = await redis_store.load_state(session_id)
    if existing and existing.get("current_step") == "complete":
        raise HTTPException(status_code=409, detail="Session already completed. Start a new session.")

    initial_state: AgentState = existing or {
        "session_id": session_id,
        "task": request.task,
        "messages": [],
        "research_output": None,
        "analysis_output": None,
        "final_output": None,
        "requires_human_review": False,
        "current_step": "init",
        "iterations": 0,
    }

    try:
        result = await agent_graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("Agent graph failed for session %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=f"Agent execution error: {exc}") from exc

    await redis_store.save_state(session_id, result)

    return AgentRunResponse(
        session_id=session_id,
        status="complete" if result["current_step"] == "complete" else "paused",
        current_step=result["current_step"],
        final_output=result.get("final_output"),
        requires_human_review=result.get("requires_human_review", False),
    )


@router.post("/approve/{session_id}", summary="Approve human-in-the-loop checkpoint")
async def approve_human_review(session_id: str):
    state = await redis_store.load_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    if state.get("current_step") != "awaiting_human_review":
        raise HTTPException(status_code=400, detail="Session is not awaiting human review")
    state["requires_human_review"] = False
    state["current_step"] = "research_done"  # Resume from analyst
    result = await agent_graph.ainvoke(state)
    await redis_store.save_state(session_id, result)
    return {"session_id": session_id, "status": "resumed", "current_step": result["current_step"]}
