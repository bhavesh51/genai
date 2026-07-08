"""
Project 8 – Educational Content Generator
Content endpoints
"""
import uuid

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.db.milvus_client import milvus_client
from app.db.redis_client import redis_client
from app.engine.content_generator import content_generator
from app.mastery.bkt import BayesianKnowledgeTracer

router = APIRouter()


class ContentGenerateRequest(BaseModel):
    topic: str
    learner_id: str
    subject: str


class ContentIngestRequest(BaseModel):
    chunk_id: str
    subject: str
    topic: str
    text: str


async def embed_text(text: str) -> list[float]:
    payload = {"model": settings.EMBEDDING_MODEL_NAME, "input": text}
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/embeddings",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
    return data["data"][0]["embedding"]


@router.post("/generate")
async def generate_content(request: ContentGenerateRequest):
    mastery = await redis_client.get_topic_mastery(request.learner_id, request.topic)
    tracer = BayesianKnowledgeTracer(
        p_init=settings.BKT_P_INIT,
        p_learn=settings.BKT_P_LEARN,
        p_forget=settings.BKT_P_FORGET,
        p_guess=settings.BKT_P_GUESS,
        p_slip=settings.BKT_P_SLIP,
    )
    p_mastery = mastery if mastery is not None else settings.BKT_P_INIT
    difficulty = tracer.get_difficulty(p_mastery)
    query_embedding = await embed_text(f"{request.subject} {request.topic}")
    context_chunks = await milvus_client.search_curriculum(query_embedding, request.subject, request.topic)
    lesson = await content_generator.generate_lesson(request.topic, difficulty, context_chunks)
    return {
        "lesson_id": str(uuid.uuid4()),
        "topic": request.topic,
        "difficulty": difficulty,
        "content": lesson,
        "word_count": len(lesson.split()),
    }


@router.post("/ingest")
async def ingest_content(request: ContentIngestRequest):
    embedding = await embed_text(request.text)
    await milvus_client.upsert_chunk(request.chunk_id, request.subject, request.topic, request.text, embedding)
    return {"status": "ingested", "chunk_id": request.chunk_id, "subject": request.subject, "topic": request.topic}
