"""
Project 4 – Document Intelligence
FastAPI application entry point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.kafka.producer import kafka_producer


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await kafka_producer.start()
    yield
    await kafka_producer.stop()


app = FastAPI(
    title="Real-time Document Intelligence Service",
    description="Streaming document processing with IBM Docling on RHOAI 3.x",
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
    return {"status": "healthy", "service": "document-intelligence"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}
