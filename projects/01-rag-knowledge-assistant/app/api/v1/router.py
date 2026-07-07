"""
Project 1 – RAG Knowledge Assistant
API v1 router
"""
from fastapi import APIRouter

from app.api.v1.endpoints import ingest, query

api_router = APIRouter()
api_router.include_router(query.router, prefix="/query", tags=["Query"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])
