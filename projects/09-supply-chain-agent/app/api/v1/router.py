"""
Project 9 – Supply Chain Optimization Agent
API v1 router – assembles agent and inventory sub-routers
"""
from fastapi import APIRouter

from app.api.v1.endpoints import agent, inventory

api_router = APIRouter()
api_router.include_router(agent.router, prefix="/agent", tags=["Agent"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
