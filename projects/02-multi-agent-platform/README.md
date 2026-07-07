# Project 2 — Multi-Agent Orchestration Platform

Production multi-agent system using LangGraph on Red Hat OpenShift AI 3.x.

## Stack
- **Orchestration**: LangGraph (stateful agent graph)
- **LLM Backend**: vLLM Mistral-7B-Instruct via RHOAI KServe
- **Memory**: Redis Cluster (HA) on OpenShift
- **Task Queue**: Celery + Redis
- **API**: FastAPI with WebSocket support

## Quick Start (Local Dev)
```bash
cd projects/02-multi-agent-platform
pip install -r requirements.txt
docker-compose up -d redis
uvicorn app.main:app --reload
```

## Deploy on RHOAI
```bash
oc apply -k deploy/kustomize/overlays/production
```
