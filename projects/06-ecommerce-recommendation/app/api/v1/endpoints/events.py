"""
Project 6 – E-commerce Product Recommendation Engine
Events endpoint: ingest real-time user behaviour events
(clicks, add-to-cart, purchases) to update the feature store.
"""
import logging
from enum import Enum
from typing import Optional

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.db.redis_client import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()


class EventType(str, Enum):
    click = "click"
    add_to_cart = "add_to_cart"
    purchase = "purchase"
    view = "view"
    wishlist = "wishlist"


class BehaviourEvent(BaseModel):
    user_id: str = Field(..., description="User who triggered the event")
    product_id: str = Field(..., description="Product involved in the event")
    event_type: EventType
    session_id: Optional[str] = None
    metadata: Optional[dict] = None


class EventResponse(BaseModel):
    status: str
    message: str


@router.post(
    "/events",
    response_model=EventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record a user behaviour event",
)
async def record_event(event: BehaviourEvent) -> EventResponse:
    """
    Stores the event in the user's Redis feature profile and invalidates
    any cached recommendations for that user.
    """
    features = await redis_client.get_user_features(event.user_id) or {
        "user_id": event.user_id,
        "recent_products": [],
        "recent_categories": [],
        "purchase_count": 0,
    }

    # Update interaction history (keep last 50 items)
    product_meta = await redis_client.get_product_features(event.product_id) or {}
    category = product_meta.get("category", "unknown")

    features["recent_products"] = (
        [event.product_id] + features.get("recent_products", [])
    )[:50]
    features["recent_categories"] = (
        [category] + features.get("recent_categories", [])
    )[:20]

    if event.event_type == EventType.purchase:
        features["purchase_count"] = features.get("purchase_count", 0) + 1

    # Rebuild a simple preference summary for the hybrid engine
    top_cats = list(dict.fromkeys(features["recent_categories"]))[:5]
    features["preference_summary"] = (
        f"Recently interacted with products in: {', '.join(top_cats) or 'various categories'}."
    )

    await redis_client.set_user_features(event.user_id, features)
    logger.info(
        "Recorded %s event for user=%s product=%s",
        event.event_type.value,
        event.user_id,
        event.product_id,
    )

    return EventResponse(status="accepted", message="Event recorded and user profile updated.")
