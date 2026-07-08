"""
Project 8 – Educational Content Generator
Mastery endpoints
"""
from fastapi import APIRouter

from app.core.config import settings
from app.db.redis_client import redis_client
from app.mastery.bkt import BayesianKnowledgeTracer

router = APIRouter()


@router.get("/{learner_id}")
async def get_mastery(learner_id: str):
    return {"learner_id": learner_id, "mastery": await redis_client.get_all_mastery(learner_id)}


@router.get("/{learner_id}/{topic}")
async def get_topic_mastery(learner_id: str, topic: str):
    tracer = BayesianKnowledgeTracer(
        p_init=settings.BKT_P_INIT,
        p_learn=settings.BKT_P_LEARN,
        p_forget=settings.BKT_P_FORGET,
        p_guess=settings.BKT_P_GUESS,
        p_slip=settings.BKT_P_SLIP,
    )
    mastery = await redis_client.get_topic_mastery(learner_id, topic)
    p_mastery = mastery if mastery is not None else settings.BKT_P_INIT
    return {"learner_id": learner_id, "topic": topic, "mastery": p_mastery, "difficulty": tracer.get_difficulty(p_mastery)}
