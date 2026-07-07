"""
Project 2 – Multi-Agent Platform
API v1 router
"""
from fastapi import APIRouter

from app.api.v1.endpoints import agent, sessions

api_router = APIRouter()
api_router.include_router(agent.router, prefix="/agent", tags=["Agent"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
