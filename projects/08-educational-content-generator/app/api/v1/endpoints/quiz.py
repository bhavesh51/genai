"""
Project 8 – Educational Content Generator
Quiz endpoints
"""
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.db.redis_client import redis_client
from app.engine.quiz_generator import quiz_generator
from app.mastery.bkt import BayesianKnowledgeTracer

router = APIRouter()


class QuizGenerateRequest(BaseModel):
    topic: str
    learner_id: str
    num_questions: int = 5


class QuizSubmitRequest(BaseModel):
    quiz_id: str
    learner_id: str
    answers: list[int]


@router.post("/generate")
async def generate_quiz(request: QuizGenerateRequest):
    mastery = await redis_client.get_topic_mastery(request.learner_id, request.topic)
    tracer = BayesianKnowledgeTracer(
        p_init=settings.BKT_P_INIT,
        p_learn=settings.BKT_P_LEARN,
        p_forget=settings.BKT_P_FORGET,
        p_guess=settings.BKT_P_GUESS,
        p_slip=settings.BKT_P_SLIP,
    )
    difficulty = tracer.get_difficulty(mastery if mastery is not None else settings.BKT_P_INIT)
    questions = await quiz_generator.generate_quiz(request.topic, difficulty, request.num_questions)
    quiz_id = str(uuid.uuid4())
    quiz_payload = {"topic": request.topic, "learner_id": request.learner_id, "questions": questions}
    await redis_client.set_json(f"quiz:{quiz_id}", quiz_payload, settings.REDIS_QUIZ_TTL)
    return {"quiz_id": quiz_id, "questions": questions}


@router.post("/submit")
async def submit_quiz(request: QuizSubmitRequest):
    quiz = await redis_client.get_json(f"quiz:{request.quiz_id}")
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz["learner_id"] != request.learner_id:
        raise HTTPException(status_code=403, detail="Quiz does not belong to learner")

    questions = quiz["questions"]
    correct_flags = []
    score = 0
    mastery = await redis_client.get_topic_mastery(request.learner_id, quiz["topic"])
    tracer = BayesianKnowledgeTracer(
        p_init=settings.BKT_P_INIT,
        p_learn=settings.BKT_P_LEARN,
        p_forget=settings.BKT_P_FORGET,
        p_guess=settings.BKT_P_GUESS,
        p_slip=settings.BKT_P_SLIP,
    )
    p_mastery = mastery if mastery is not None else settings.BKT_P_INIT

    for index, question in enumerate(questions):
        is_correct = index < len(request.answers) and request.answers[index] == question["correct_index"]
        correct_flags.append(is_correct)
        if is_correct:
            score += 1
        p_mastery = tracer.update(p_mastery, is_correct)

    await redis_client.set_topic_mastery(request.learner_id, quiz["topic"], p_mastery)
    return {
        "score": score,
        "total": len(questions),
        "correct": correct_flags,
        "updated_mastery": p_mastery,
        "new_difficulty": tracer.get_difficulty(p_mastery),
    }
