"""
Project 9 – Supply Chain Optimization Agent
LangGraph multi-agent state machine: planner → forecaster → risk → executor
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.agents.tools import (
    create_purchase_order,
    get_demand_forecast,
    get_inventory,
    get_supplier_risk,
)

logger = logging.getLogger(__name__)


# ─── State ────────────────────────────────────────────────────────────────────

class SupplyChainState(TypedDict):
    session_id: str
    task: str
    messages: List[Dict[str, Any]]
    inventory_data: Dict[str, Any]
    forecast_data: Dict[str, Any]
    risk_scores: Dict[str, Any]
    recommended_actions: List[Dict[str, Any]]
    final_report: Optional[str]
    current_step: str
    iterations: int


# ─── LLM factory ──────────────────────────────────────────────────────────────

def _get_llm(temperature: float | None = None) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL_NAME,
        temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=False,
    )


# ─── System prompts ────────────────────────────────────────────────────────────

PLANNER_SYSTEM = (
    "You are an expert supply chain planner. Given a task and SKU list, "
    "analyse inventory levels using the get_inventory tool, identify which SKUs "
    "are below their reorder point, and produce a prioritised list of recommended "
    "replenishment actions. Output a structured JSON with 'recommended_actions' "
    "as a list of objects containing 'sku', 'action', and 'suggested_quantity'."
)

FORECASTER_SYSTEM = (
    "You are a demand forecasting specialist. Given inventory data and a task, "
    "retrieve 30-day demand forecasts using the get_demand_forecast tool for each "
    "SKU that requires attention. Summarise the expected demand and adjust the "
    "suggested order quantities based on the forecast data."
)

RISK_SYSTEM = (
    "You are a supply chain risk analyst. Given recommended actions and supplier "
    "data, assess supplier risk using the get_supplier_risk tool for each relevant "
    "supplier. Flag any suppliers whose risk_score exceeds the alert threshold and "
    "propose alternative suppliers where risk is unacceptable."
)

EXECUTOR_SYSTEM = (
    "You are a supply chain execution agent. Given the final recommended actions "
    "with risk assessments, create purchase orders using the create_purchase_order "
    "tool for all approved replenishment actions. Then produce a concise executive "
    "summary of all actions taken, orders created, and risk flags raised."
)


# ─── Nodes ────────────────────────────────────────────────────────────────────

async def planner_node(state: SupplyChainState) -> SupplyChainState:
    """
    Planner: calls get_inventory for every SKU in the task and populates
    inventory_data plus an initial set of recommended_actions.
    """
    llm = _get_llm().bind_tools([get_inventory])
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Task: {state['task']}\n"
                f"Current inventory snapshot:\n{state['inventory_data']}"
            ),
        },
    ]
    response = await llm.ainvoke(messages)

    # Parse tool calls if the LLM invoked get_inventory
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            if tc["name"] == "get_inventory":
                sku = tc["args"].get("sku", "")
                result = await get_inventory.ainvoke(tc["args"])
                state["inventory_data"][sku] = result

    # Store LLM recommendations in state; default to empty list if not parsed
    state["recommended_actions"] = state.get("recommended_actions") or []
    state["messages"].append({"role": "planner", "content": response.content})
    state["current_step"] = "planner_done"
    state["iterations"] += 1
    logger.info("Planner node completed for session %s", state["session_id"])
    return state


async def forecaster_node(state: SupplyChainState) -> SupplyChainState:
    """
    Forecaster: calls get_demand_forecast for SKUs identified by the planner
    and enriches forecast_data.
    """
    llm = _get_llm().bind_tools([get_demand_forecast])
    skus = list(state["inventory_data"].keys())
    messages = [
        {"role": "system", "content": FORECASTER_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Task: {state['task']}\n"
                f"SKUs requiring forecast: {skus}\n"
                f"Inventory data:\n{state['inventory_data']}"
            ),
        },
    ]
    response = await llm.ainvoke(messages)

    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            if tc["name"] == "get_demand_forecast":
                sku = tc["args"].get("sku", "")
                result = await get_demand_forecast.ainvoke(tc["args"])
                state["forecast_data"][sku] = result

    state["messages"].append({"role": "forecaster", "content": response.content})
    state["current_step"] = "forecaster_done"
    state["iterations"] += 1
    logger.info("Forecaster node completed for session %s", state["session_id"])
    return state


async def risk_node(state: SupplyChainState) -> SupplyChainState:
    """
    Risk analyst: calls get_supplier_risk for every supplier referenced in
    recommended_actions and populates risk_scores.
    """
    llm = _get_llm().bind_tools([get_supplier_risk])
    messages = [
        {"role": "system", "content": RISK_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Task: {state['task']}\n"
                f"Recommended actions:\n{state['recommended_actions']}\n"
                f"Forecast data:\n{state['forecast_data']}\n"
                f"Risk alert threshold: {settings.RISK_ALERT_THRESHOLD}"
            ),
        },
    ]
    response = await llm.ainvoke(messages)

    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            if tc["name"] == "get_supplier_risk":
                supplier_id = tc["args"].get("supplier_id", "")
                result = await get_supplier_risk.ainvoke(tc["args"])
                state["risk_scores"][supplier_id] = result

    state["messages"].append({"role": "risk_analyst", "content": response.content})
    state["current_step"] = "risk_done"
    state["iterations"] += 1
    logger.info("Risk node completed for session %s", state["session_id"])
    return state


async def executor_node(state: SupplyChainState) -> SupplyChainState:
    """
    Executor: calls create_purchase_order for each recommended replenishment,
    then generates the final executive-summary report.
    """
    llm = _get_llm().bind_tools([create_purchase_order])
    messages = [
        {"role": "system", "content": EXECUTOR_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Task: {state['task']}\n"
                f"Recommended actions:\n{state['recommended_actions']}\n"
                f"Risk scores:\n{state['risk_scores']}\n"
                f"Forecast data:\n{state['forecast_data']}\n"
                "Create purchase orders for all approved actions, "
                "then write the final executive report."
            ),
        },
    ]
    response = await llm.ainvoke(messages)

    created_orders: List[Dict[str, Any]] = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            if tc["name"] == "create_purchase_order":
                result = await create_purchase_order.ainvoke(tc["args"])
                created_orders.append(result)

    # Append order summaries to recommended_actions for downstream visibility
    if created_orders:
        state["recommended_actions"].extend(
            [{"type": "purchase_order", **o} for o in created_orders]
        )

    state["final_report"] = response.content or (
        f"Supply chain optimisation complete. "
        f"Created {len(created_orders)} purchase order(s). "
        f"Risk flags: {[s for s, r in state['risk_scores'].items() if r.get('risk_score', 0) >= settings.RISK_ALERT_THRESHOLD]}."
    )
    state["messages"].append({"role": "executor", "content": state["final_report"]})
    state["current_step"] = "complete"
    state["iterations"] += 1
    logger.info("Executor node completed for session %s", state["session_id"])
    return state


# ─── Routing ──────────────────────────────────────────────────────────────────

def route_after_forecaster(state: SupplyChainState) -> str:
    if state["iterations"] >= settings.MAX_AGENT_ITERATIONS:
        logger.warning(
            "Max iterations (%d) reached for session %s – short-circuiting to END",
            settings.MAX_AGENT_ITERATIONS,
            state["session_id"],
        )
        return END
    return "risk"


def route_after_risk(state: SupplyChainState) -> str:
    if state["iterations"] >= settings.MAX_AGENT_ITERATIONS:
        logger.warning(
            "Max iterations (%d) reached for session %s – short-circuiting to END",
            settings.MAX_AGENT_ITERATIONS,
            state["session_id"],
        )
        return END
    return "executor"


# ─── Graph builder ─────────────────────────────────────────────────────────────

def build_agent_graph() -> StateGraph:
    builder = StateGraph(SupplyChainState)

    builder.add_node("planner", planner_node)
    builder.add_node("forecaster", forecaster_node)
    builder.add_node("risk", risk_node)
    builder.add_node("executor", executor_node)

    builder.set_entry_point("planner")

    # planner → forecaster (unconditional – planner is step 1)
    builder.add_edge("planner", "forecaster")

    # forecaster → risk | END (guard)
    builder.add_conditional_edges(
        "forecaster",
        route_after_forecaster,
        {"risk": "risk", END: END},
    )

    # risk → executor | END (guard)
    builder.add_conditional_edges(
        "risk",
        route_after_risk,
        {"executor": "executor", END: END},
    )

    builder.add_edge("executor", END)

    return builder.compile()


agent_graph = build_agent_graph()
