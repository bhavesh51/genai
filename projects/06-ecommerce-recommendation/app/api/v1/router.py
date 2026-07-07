"""
Project 6 – E-commerce Product Recommendation Engine
APIRouter aggregating all v1 endpoints
"""
from fastapi import APIRouter

from app.api.v1.endpoints.events import router as events_router
from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.recommendations import router as recommendations_router

api_router = APIRouter()

api_router.include_router(recommendations_router, tags=["recommendations"])
api_router.include_router(products_router, tags=["products"])
api_router.include_router(events_router, tags=["events"])
