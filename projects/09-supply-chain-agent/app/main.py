"""
Project 9 – Supply Chain Optimization Agent
FastAPI application entry point with lifespan, CORS, health, and ready probes
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.redis_client import redis_client
from app.db.qdrant_client import qdrant_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await redis_client.connect()
    await qdrant_client.connect()
    yield
    await qdrant_client.close()
    await redis_client.close()


app = FastAPI(
    title="Supply Chain Optimization Agent",
    description="LangGraph-based supply chain optimisation agent on Red Hat OpenShift AI 3.x",
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


@app.get("/health", tags=["Ops"])
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME}


@app.get("/ready", tags=["Ops"])
async def ready():
    redis_ok = redis_client.is_connected()
    qdrant_ok = qdrant_client.is_connected()
    ready_status = redis_ok and qdrant_ok
    return {
        "status": "ready" if ready_status else "not_ready",
        "redis": redis_ok,
        "qdrant": qdrant_ok,
    }
