"""
Project 8 – Educational Content Generator
Tutor endpoints
"""
import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.db.milvus_client import milvus_client
from app.db.redis_client import redis_client
from app.engine.tutor import socratic_tutor

router = APIRouter()


class TutorMessageRequest(BaseModel):
    session_id: str
    learner_id: str
    topic: str
    message: str


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


@router.post("/message")
async def send_tutor_message(request: TutorMessageRequest):
    query_embedding = await embed_text(request.topic)
    context_chunks = await milvus_client.search_curriculum(query_embedding, topic=request.topic)
    response = await socratic_tutor.respond(request.session_id, request.message, request.topic, context_chunks)
    return {"session_id": request.session_id, "response": response}


@router.delete("/session/{session_id}")
async def delete_tutor_session(session_id: str):
    await redis_client.delete(f"session:{session_id}")
    return {"status": "deleted", "session_id": session_id}
