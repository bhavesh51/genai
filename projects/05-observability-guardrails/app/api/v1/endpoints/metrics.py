"""
Project 5 – Observability & Guardrails
Metrics endpoint: expose Prometheus metrics
"""
from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter()


@router.get("", summary="Prometheus metrics endpoint")
async def prometheus_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
