"""
Project 5 – Observability & Guardrails
API v1 router
"""
from fastapi import APIRouter

from app.api.v1.endpoints import proxy, metrics

api_router = APIRouter()
api_router.include_router(proxy.router, prefix="/proxy", tags=["Guardrails Proxy"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
