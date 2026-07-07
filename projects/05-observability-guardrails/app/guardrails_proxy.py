"""
Project 5 – Observability & Guardrails
FastAPI guardrails proxy entry point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.guardrails.engine import guardrails_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await guardrails_engine.load()
    yield
    await guardrails_engine.unload()


app = FastAPI(
    title="GenAI Observability & Guardrails Platform",
    description="Inline guardrails proxy and TrustyAI integration on RHOAI 3.x",
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
    return {"status": "healthy", "service": "observability-guardrails"}


@app.get("/ready")
async def ready():
    loaded = guardrails_engine.is_loaded()
    return {"status": "ready" if loaded else "loading", "guardrails": loaded}
