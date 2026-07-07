"""
Project 6 – E-commerce Product Recommendation Engine
FastAPI application entry point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.qdrant_client import qdrant_client
from app.db.redis_client import redis_client
from app.recommender.collaborative import collaborative_scorer


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await qdrant_client.connect()
    await redis_client.connect()
    # Load ALS model artefact (pre-downloaded to /tmp by init container)
    collaborative_scorer.load()
    yield
    await qdrant_client.close()
    await redis_client.close()


app = FastAPI(
    title="E-commerce Product Recommendation Engine",
    description=(
        "Hybrid AI-powered product recommendation service on Red Hat OpenShift AI 3.x. "
        "Combines ALS collaborative filtering, E5-large content embeddings, and Llama 3 8B reranking."
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
    qdrant_ok = qdrant_client.is_connected()
    redis_ok = redis_client.is_connected()
    ready = qdrant_ok and redis_ok
    return {
        "status": "ready" if ready else "not_ready",
        "qdrant": qdrant_ok,
        "redis": redis_ok,
    }
