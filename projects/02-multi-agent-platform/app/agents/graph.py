"""
Project 2 – Multi-Agent Platform
LangGraph multi-agent state machine definition
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.core.config import settings
from app.agents.tools import (
    search_web_tool,
    run_sql_query_tool,
    run_code_tool,
)

logger = logging.getLogger(__name__)


# ─── State ────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    session_id: str
    task: str
    messages: List[Dict[str, Any]]
    research_output: Optional[str]
    analysis_output: Optional[str]
    final_output: Optional[str]
    requires_human_review: bool
    current_step: str
    iterations: int


# ─── LLM ──────────────────────────────────────────────────────────────────────

def _get_llm(temperature: float = 0.3):
    return ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL_NAME,
        temperature=temperature,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=True,
    )


# ─── Nodes ────────────────────────────────────────────────────────────────────

RESEARCH_SYSTEM = (
    "You are an expert researcher. Given a task, search for relevant information "
    "using available tools and produce a comprehensive research summary."
)

ANALYST_SYSTEM = (
    "You are a senior analyst. Given research notes, produce a structured analysis "
    "with key insights, risks, and recommendations."
)

WRITER_SYSTEM = (
    "You are a professional writer. Given an analysis, write a clear, concise, "
    "and well-structured final report targeted at enterprise decision makers."
)


async def research_node(state: AgentState) -> AgentState:
    llm = _get_llm(temperature=0.2).bind_tools([search_web_tool])
    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM},
        {"role": "user", "content": f"Task: {state['task']}"},
    ]
    response = await llm.ainvoke(messages)
    state["research_output"] = response.content
    state["current_step"] = "research_done"
    state["iterations"] += 1
    logger.info("Research step completed for session %s", state["session_id"])
    return state


async def analyst_node(state: AgentState) -> AgentState:
    llm = _get_llm(temperature=0.1).bind_tools([run_sql_query_tool])
    messages = [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": f"Research:\n{state['research_output']}\n\nTask: {state['task']}"},
    ]
    response = await llm.ainvoke(messages)
    state["analysis_output"] = response.content
    state["current_step"] = "analysis_done"
    state["iterations"] += 1
    return state


async def writer_node(state: AgentState) -> AgentState:
    llm = _get_llm(temperature=0.4)
    messages = [
        {"role": "system", "content": WRITER_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Analysis:\n{state['analysis_output']}\n\n"
                f"Write the final report for task: {state['task']}"
            ),
        },
    ]
    response = await llm.ainvoke(messages)
    state["final_output"] = response.content
    state["current_step"] = "complete"
    state["iterations"] += 1
    return state


async def human_review_node(state: AgentState) -> AgentState:
    """Checkpoint: pause for human approval if configured."""
    state["requires_human_review"] = True
    state["current_step"] = "awaiting_human_review"
    logger.info("Pausing for human review: session=%s", state["session_id"])
    return state


def route_after_research(state: AgentState) -> str:
    if state["iterations"] >= settings.MAX_AGENT_ITERATIONS:
        return "writer"
    if settings.ENABLE_HUMAN_IN_THE_LOOP and state.get("requires_human_review"):
        return "human_review"
    return "analyst"


def route_after_analyst(state: AgentState) -> str:
    return "writer"


# ─── Graph ────────────────────────────────────────────────────────────────────

def build_agent_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("research", research_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("writer", writer_node)
    builder.add_node("human_review", human_review_node)

    builder.set_entry_point("research")

    builder.add_conditional_edges("research", route_after_research, {
        "analyst": "analyst",
        "writer": "writer",
        "human_review": "human_review",
    })
    builder.add_conditional_edges("analyst", route_after_analyst, {
        "writer": "writer",
    })
    builder.add_edge("writer", END)
    builder.add_edge("human_review", END)  # Resumed externally

    return builder.compile()


agent_graph = build_agent_graph()
