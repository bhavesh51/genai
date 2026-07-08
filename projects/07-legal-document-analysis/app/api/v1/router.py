"""
Project 7 – Legal Document Analysis & Contract Intelligence
APIRouter aggregating all v1 endpoints
"""
from fastapi import APIRouter

from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.qa import router as qa_router

api_router = APIRouter()

api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(qa_router, tags=["qa"])
