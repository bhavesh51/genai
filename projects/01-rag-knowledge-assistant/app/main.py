"""
Project 1 – RAG Knowledge Assistant
FastAPI application entry point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.milvus_client import milvus_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await milvus_client.connect()
    yield
    await milvus_client.close()


app = FastAPI(
    title="Enterprise RAG Knowledge Assistant",
    description="Production RAG service on Red Hat OpenShift AI 3.x",
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
    return {"status": "healthy", "service": "rag-knowledge-assistant"}


@app.get("/ready")
async def ready():
    connected = milvus_client.is_connected()
    return {"status": "ready" if connected else "not_ready", "vector_db": connected}
