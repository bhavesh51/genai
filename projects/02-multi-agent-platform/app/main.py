"""
Project 2 – Multi-Agent Platform
FastAPI application entry point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.memory.redis_store import redis_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await redis_store.connect()
    yield
    await redis_store.close()


app = FastAPI(
    title="Multi-Agent Orchestration Platform",
    description="LangGraph-based multi-agent platform on RHOAI 3.x",
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
    return {"status": "healthy", "service": "multi-agent-platform"}


@app.get("/ready")
async def ready():
    connected = redis_store.is_connected()
    return {"status": "ready" if connected else "not_ready", "memory_store": connected}
