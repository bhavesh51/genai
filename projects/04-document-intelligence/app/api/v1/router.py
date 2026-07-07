"""
Project 4 – Document Intelligence
API v1 router
"""
from fastapi import APIRouter

from app.api.v1.endpoints import documents

api_router = APIRouter()
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
