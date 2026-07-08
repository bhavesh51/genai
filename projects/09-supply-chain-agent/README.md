# Project 9 — Supply Chain Optimization Agent

Production-grade LangGraph multi-agent system for real-time supply chain optimisation on Red Hat OpenShift AI 3.x.

---

## Stack

| Layer | Technology |
|---|---|
| **API** | FastAPI (async, Pydantic v2) |
| **Agent orchestration** | LangGraph stateful state-machine |
| **LLM backend** | vLLM · Llama 3 8B Instruct via RHOAI KServe |
| **Vector store** | Qdrant (supplier knowledge base) |
| **Session cache** | Redis (async, hiredis) |
| **Streaming / events** | Apache Kafka (aiokafka) |
| **Database** | PostgreSQL (asyncpg / SQLAlchemy 2 async) |
| **Observability** | OpenTelemetry + Prometheus |
| **Deploy** | Kustomize on OpenShift |
| **Base image** | UBI9 Python 3.11 |

---

## Agent Flow

```
                    ┌──────────────────────────────┐
                    │         POST /agent/run       │
                    │  { session_id, task, skus }   │
                    └──────────────┬───────────────┘
                                   │  ainvoke(initial_state)
                                   ▼
                         ┌─────────────────┐
                         │  planner_node   │  ← get_inventory() × N skus
                         │  (Llama 3 8B)   │    identifies reorder needs
                         └────────┬────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │  forecaster_node     │  ← get_demand_forecast() × N
                       │  (Llama 3 8B)        │    30-day unit projections
                       └──────────┬───────────┘
                                  │    [guard: iterations ≥ MAX → END]
                                  ▼
                        ┌──────────────────────┐
                        │    risk_node         │  ← get_supplier_risk() × N
                        │  (Llama 3 8B)        │    flags risk_score ≥ 0.7
                        └──────────┬───────────┘
                                   │    [guard: iterations ≥ MAX → END]
                                   ▼
                        ┌──────────────────────┐
                        │   executor_node      │  ← create_purchase_order()
                        │  (Llama 3 8B)        │    generates final report
                        └──────────┬───────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    Redis state persisted      │
                    │  { final_report, actions }   │
                    └──────────────────────────────┘
```

### State fields

| Field | Type | Description |
|---|---|---|
| `session_id` | `str` | Unique run identifier |
| `task` | `str` | Natural-language optimisation task |
| `messages` | `list` | Per-node LLM message history |
| `inventory_data` | `dict` | SKU → inventory snapshot |
| `forecast_data` | `dict` | SKU → 30-day forecast |
| `risk_scores` | `dict` | supplier_id → risk assessment |
| `recommended_actions` | `list` | Planner output + created POs |
| `final_report` | `str` | Executive summary from executor |
| `current_step` | `str` | Last completed node name |
| `iterations` | `int` | Iteration counter (max 5) |

---

## API Endpoints

### Agent

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/agent/run` | Run the full 4-node agent pipeline |
| `GET` | `/api/v1/agent/session/{session_id}` | Retrieve persisted session state |

### Inventory

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/inventory/{sku}` | Current inventory levels for a SKU |
| `GET` | `/api/v1/inventory/{sku}/forecast` | 30-day demand forecast for a SKU |
| `POST` | `/api/v1/inventory/supplier-risk` | Batch supplier risk assessment |

### Ops

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Readiness probe (Redis + Qdrant) |

---

## Quick Start (Local Dev)

```bash
cd projects/09-supply-chain-agent

# 1 – copy and edit environment variables
cp .env.example .env

# 2 – start dependencies
docker run -d --name redis -p 6379:6379 redis:7-alpine
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# 3 – install Python deps
pip install -r requirements.txt

# 4 – run the service
uvicorn app.main:app --reload --port 8080
```

---

## Example curl Requests

### Run the agent

```bash
curl -s -X POST http://localhost:8080/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-demo-001",
    "task": "Optimise inventory for Q4 peak season, ensure no stock-outs on high-velocity SKUs",
    "skus": ["SKU-A100", "SKU-B200", "SKU-C300"]
  }' | jq .
```

### Retrieve a previous session

```bash
curl -s http://localhost:8080/api/v1/agent/session/sess-demo-001 | jq .
```

### Get inventory for a SKU

```bash
curl -s http://localhost:8080/api/v1/inventory/SKU-A100 | jq .
```

### Get 30-day forecast

```bash
curl -s "http://localhost:8080/api/v1/inventory/SKU-A100/forecast?days=30" | jq .
```

### Batch supplier risk assessment

```bash
curl -s -X POST http://localhost:8080/api/v1/inventory/supplier-risk \
  -H "Content-Type: application/json" \
  -d '{"supplier_ids": ["SUP-001", "SUP-002", "SUP-003"]}' | jq .
```

---

## Deploy on RHOAI / OpenShift

```bash
# Apply production overlay (3 replicas, HPA 3–8)
oc apply -k deploy/kustomize/overlays/production

# Tail logs
oc logs -l app=supply-chain-agent -f -n supply-chain-agent
```

---

## Configuration Reference

All settings are read from environment variables (or `.env`).
See [`.env.example`](.env.example) for the full list with localhost defaults.

| Variable | Default | Description |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:8000/v1` | vLLM endpoint |
| `LLM_MODEL_NAME` | `meta-llama/Meta-Llama-3-8B-Instruct` | Model name |
| `LLM_MAX_TOKENS` | `2048` | Max completion tokens |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature |
| `QDRANT_HOST` | `localhost` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant gRPC/HTTP port |
| `QDRANT_COLLECTION` | `supplier_knowledge` | Collection name |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_SESSION_TTL` | `86400` | Session TTL (seconds) |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka brokers |
| `MAX_AGENT_ITERATIONS` | `5` | Hard iteration cap |
| `RISK_ALERT_THRESHOLD` | `0.7` | Supplier risk flag threshold |
