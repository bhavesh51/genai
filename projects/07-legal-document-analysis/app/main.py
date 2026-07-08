"""
Project 7 – Legal Document Analysis & Contract Intelligence
FastAPI application entry point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.weaviate_client import weaviate_client
from app.db.redis_client import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await weaviate_client.connect()
    await redis_client.connect()
    yield
    await weaviate_client.close()
    await redis_client.close()


app = FastAPI(
    title="Legal Document Analysis & Contract Intelligence",
    description=(
        "AI-powered legal document analysis service on Red Hat OpenShift AI 3.x. "
        "Extracts clauses, scores risks across 15 categories, and answers natural-language "
        "questions using InLegalBERT embeddings and Llama 3 8B-Instruct."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME}


@app.get("/ready", tags=["ops"])
async def ready():
    weaviate_ok = weaviate_client.is_connected()
    redis_ok = redis_client.is_connected()
    ready = weaviate_ok and redis_ok
    return {
        "status": "ready" if ready else "not_ready",
        "weaviate": weaviate_ok,
        "redis": redis_ok,
    }
