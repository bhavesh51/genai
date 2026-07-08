"""
Project 8 – Educational Content Generator
FastAPI application entry point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.milvus_client import milvus_client
from app.db.redis_client import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await milvus_client.connect()
    await redis_client.connect()
    yield
    await redis_client.close()
    await milvus_client.close()


app = FastAPI(
    title="Educational Content Generator & Adaptive Tutor",
    description="Production educational content generation and adaptive tutoring service",
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


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME}


@app.get("/ready")
async def ready():
    milvus_ready = milvus_client.is_connected()
    redis_ready = redis_client.is_connected()
    return {
        "status": "ready" if milvus_ready and redis_ready else "not_ready",
        "vector_db": milvus_ready,
        "cache": redis_ready,
    }
