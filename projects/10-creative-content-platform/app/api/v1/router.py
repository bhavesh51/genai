"""
Project 10 – Creative Content Generation Platform
APIRouter aggregating all v1 endpoints
"""
from fastapi import APIRouter

from app.api.v1.endpoints.assets import router as assets_router
from app.api.v1.endpoints.brand import router as brand_router
from app.api.v1.endpoints.content import router as content_router

api_router = APIRouter()

api_router.include_router(content_router, tags=["content"])
api_router.include_router(assets_router, tags=["assets"])
api_router.include_router(brand_router, tags=["brand"])
