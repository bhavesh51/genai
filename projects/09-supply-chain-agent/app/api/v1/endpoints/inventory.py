"""
Project 9 – Supply Chain Optimization Agent
Inventory, demand forecast, and supplier-risk endpoints
"""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.tools import get_demand_forecast, get_inventory, get_supplier_risk

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Request / Response models ─────────────────────────────────────────────────

class SupplierRiskRequest(BaseModel):
    supplier_ids: List[str] = Field(..., description="List of supplier identifiers to assess")


class InventoryResponse(BaseModel):
    sku: str
    quantity: int
    reorder_point: int
    unit_cost: float


class ForecastResponse(BaseModel):
    sku: str
    forecast_units: List[int]
    confidence: float


class SupplierRiskResponse(BaseModel):
    results: List[Dict[str, Any]]


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/{sku}",
    response_model=InventoryResponse,
    summary="Get current inventory levels for a SKU",
)
async def get_inventory_endpoint(sku: str):
    """
    Return real-time inventory data for a given stock-keeping unit.

    Data is sourced from the ``get_inventory`` tool (mock in non-production).
    """
    if not sku.strip():
        raise HTTPException(status_code=422, detail="SKU must be a non-empty string")
    result = await get_inventory.ainvoke({"sku": sku})
    return InventoryResponse(**result)


@router.get(
    "/{sku}/forecast",
    response_model=ForecastResponse,
    summary="Get 30-day demand forecast for a SKU",
)
async def get_forecast_endpoint(sku: str, days: int = 30):
    """
    Return a day-by-day demand forecast for a given SKU over the specified horizon.

    ``days`` defaults to 30 and must be between 1 and 365.
    """
    if not sku.strip():
        raise HTTPException(status_code=422, detail="SKU must be a non-empty string")
    if not (1 <= days <= 365):
        raise HTTPException(status_code=422, detail="days must be between 1 and 365")
    result = await get_demand_forecast.ainvoke({"sku": sku, "days": days})
    return ForecastResponse(**result)


@router.post(
    "/supplier-risk",
    response_model=SupplierRiskResponse,
    summary="Get risk scores for a list of suppliers",
)
async def get_supplier_risk_endpoint(request: SupplierRiskRequest):
    """
    Retrieve risk assessments for multiple suppliers in a single call.

    Each entry contains a composite risk score (0–1) and contributing factors.
    """
    if not request.supplier_ids:
        raise HTTPException(status_code=422, detail="supplier_ids must not be empty")

    results: List[Dict[str, Any]] = []
    for supplier_id in request.supplier_ids:
        risk = await get_supplier_risk.ainvoke({"supplier_id": supplier_id})
        results.append(risk)
        logger.debug("Assessed risk for supplier %s: score=%s", supplier_id, risk.get("risk_score"))

    return SupplierRiskResponse(results=results)
