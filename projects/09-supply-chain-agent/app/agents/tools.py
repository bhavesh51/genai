"""
Project 9 – Supply Chain Optimization Agent
Agent tools: inventory, demand forecasting, purchase orders, supplier risk
"""
import logging
import random
from uuid import uuid4

from langchain.tools import tool

logger = logging.getLogger(__name__)


@tool
async def get_inventory(sku: str) -> dict:
    """
    Return current inventory levels for a given SKU.

    Parameters
    ----------
    sku: Stock-keeping unit identifier.

    Returns a dict with quantity on hand, reorder point, and unit cost.
    """
    logger.debug("get_inventory called: sku=%s", sku)
    return {
        "sku": sku,
        "quantity": random.randint(0, 1000),
        "reorder_point": 100,
        "unit_cost": round(random.uniform(5.0, 500.0), 2),
    }


@tool
async def get_demand_forecast(sku: str, days: int = 30) -> dict:
    """
    Return a day-by-day demand forecast for a given SKU.

    Parameters
    ----------
    sku:  Stock-keeping unit identifier.
    days: Number of forecast days (default 30).

    Returns a dict containing per-day unit forecasts and a confidence score.
    """
    logger.debug("get_demand_forecast called: sku=%s days=%d", sku, days)
    return {
        "sku": sku,
        "forecast_units": [random.randint(10, 200) for _ in range(days)],
        "confidence": 0.85,
    }


@tool
async def create_purchase_order(sku: str, quantity: int, supplier_id: str) -> dict:
    """
    Create a purchase order for a given SKU and supplier.

    Parameters
    ----------
    sku:         Stock-keeping unit to order.
    quantity:    Number of units to order.
    supplier_id: Identifier of the chosen supplier.

    Returns a dict with the generated PO id and initial approval status.
    """
    po_id = f"PO-{uuid4().hex[:8].upper()}"
    logger.info(
        "create_purchase_order: po_id=%s sku=%s quantity=%d supplier_id=%s",
        po_id,
        sku,
        quantity,
        supplier_id,
    )
    return {
        "po_id": po_id,
        "sku": sku,
        "quantity": quantity,
        "supplier_id": supplier_id,
        "status": "pending_approval",
    }


@tool
async def get_supplier_risk(supplier_id: str) -> dict:
    """
    Return a risk assessment for a given supplier.

    Parameters
    ----------
    supplier_id: Supplier identifier.

    Returns a dict with a composite risk score (0–1) and contributing factors.
    """
    logger.debug("get_supplier_risk called: supplier_id=%s", supplier_id)
    return {
        "supplier_id": supplier_id,
        "risk_score": round(random.uniform(0.0, 1.0), 2),
        "risk_factors": ["lead_time_variability", "financial_stability"],
    }
