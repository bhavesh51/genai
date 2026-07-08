"""
Project 8 – Educational Content Generator
API v1 router
"""
from fastapi import APIRouter

from app.api.v1.endpoints import content, mastery, quiz, tutor

api_router = APIRouter()
api_router.include_router(content.router, prefix="/content", tags=["Content"])
api_router.include_router(quiz.router, prefix="/quiz", tags=["Quiz"])
api_router.include_router(tutor.router, prefix="/tutor", tags=["Tutor"])
api_router.include_router(mastery.router, prefix="/mastery", tags=["Mastery"])
