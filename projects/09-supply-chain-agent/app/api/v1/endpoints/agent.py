"""
Project 9 – Supply Chain Optimization Agent
Agent execution and session retrieval endpoints
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.graph import SupplyChainState, agent_graph
from app.db.redis_client import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Request / Response models ─────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    task: str = Field(..., min_length=1, max_length=8192, description="Natural-language supply chain task")
    skus: List[str] = Field(..., description="List of SKU identifiers to analyse")


class AgentRunResponse(BaseModel):
    session_id: str
    final_report: Optional[str]
    recommended_actions: List[Dict[str, Any]]
    status: str


class SessionResponse(BaseModel):
    session_id: str
    state: Optional[Dict[str, Any]]


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/run",
    response_model=AgentRunResponse,
    summary="Run the supply chain optimisation agent pipeline",
)
async def run_agent(request: AgentRunRequest):
    """
    Invoke the LangGraph supply chain agent for the given task and SKU list.

    The pipeline executes four sequential nodes: planner → forecaster → risk → executor.
    The final state is persisted to Redis under the provided ``session_id`` so it can
    be retrieved later via ``GET /agent/session/{session_id}``.
    """
    existing = await redis_client.load_agent_state(request.session_id)
    if existing and existing.get("current_step") == "complete":
        raise HTTPException(
            status_code=409,
            detail="Session already completed. Retrieve results or use a new session_id.",
        )

    # Pre-seed inventory_data with the requested SKUs as empty dicts;
    # the planner node will populate them via the get_inventory tool.
    initial_inventory: Dict[str, Any] = {sku: {} for sku in request.skus}

    initial_state: SupplyChainState = {
        "session_id": request.session_id,
        "task": request.task,
        "messages": [],
        "inventory_data": initial_inventory,
        "forecast_data": {},
        "risk_scores": {},
        "recommended_actions": [],
        "final_report": None,
        "current_step": "init",
        "iterations": 0,
    }

    try:
        result: SupplyChainState = await agent_graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("Agent graph failed for session %s: %s", request.session_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution error: {exc}",
        ) from exc

    await redis_client.save_agent_state(request.session_id, result)

    return AgentRunResponse(
        session_id=request.session_id,
        final_report=result.get("final_report"),
        recommended_actions=result.get("recommended_actions", []),
        status="complete" if result.get("current_step") == "complete" else "partial",
    )


@router.get(
    "/session/{session_id}",
    response_model=SessionResponse,
    summary="Retrieve a previous agent session result from Redis",
)
async def get_session(session_id: str):
    """
    Return the persisted agent state for an existing session.

    Raises 404 when the session does not exist or has expired.
    """
    state = await redis_client.load_agent_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found or has expired")
    return SessionResponse(session_id=session_id, state=state)
