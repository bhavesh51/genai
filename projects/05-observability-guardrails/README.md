# Project 5 — GenAI Observability & Guardrails Platform

Central observability and guardrails proxy for all GenAI services on RHOAI 3.x.

## Stack
- **Observability**: OpenTelemetry Collector + Prometheus + Grafana + Jaeger
- **Guardrails**: NeMo Guardrails / llm-guard proxy sidecar
- **TrustyAI**: RHOAI built-in bias detection and drift monitoring
- **Alerting**: Alertmanager → Slack / PagerDuty
- **Cost Tracking**: Per-namespace GPU/token metering

## Quick Start
```bash
cd projects/05-observability-guardrails
pip install -r requirements.txt
docker-compose up -d otel-collector prometheus grafana
uvicorn app.guardrails_proxy:app --reload --port 8080
```

## Deploy on RHOAI
```bash
oc apply -k deploy/kustomize/overlays/production
```
