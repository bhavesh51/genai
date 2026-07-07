# Project 6 — E-commerce Product Recommendation Engine

Hybrid AI-powered product recommendation service deployed on Red Hat OpenShift AI 3.x.

## Architecture

```
POST /api/v1/recommend      → Hybrid pipeline (ALS + content + LLM)
GET  /api/v1/recommend/:id  → Quick recs using stored user profile
POST /api/v1/products       → Ingest single product (embed → Qdrant)
POST /api/v1/products/bulk  → Bulk product ingestion
POST /api/v1/events         → Record user behaviour (click/cart/purchase)
GET  /api/v1/products/:id   → Lookup product metadata from Redis
GET  /health                → Liveness probe
GET  /ready                 → Readiness probe (Qdrant + Redis)
```

## Stack

| Component | Technology |
|---|---|
| **LLM (reranking)** | Meta Llama 3 8B-Instruct via RHOAI vLLM (AWQ 4-bit) |
| **Embeddings** | `intfloat/e5-large-v2` via RHOAI ModelMesh (1024-dim) |
| **Collaborative filtering** | ALS (`implicit` library, factors=128) |
| **Vector store** | Qdrant HA (3 replicas) |
| **Feature cache** | Redis Cluster |
| **Relational DB** | PostgreSQL (catalogue + orders) |
| **Event streaming** | Apache Kafka |
| **Framework** | FastAPI + asyncio |
| **Observability** | Prometheus + Grafana + OpenTelemetry |

## Recommendation Pipeline

```
User Request
    │
    ├── ALS Collaborative Filter ──→ top-50 candidate IDs (user–item matrix)
    │
    ├── Content-Based (E5-large)  ──→ top-50 semantic candidates (Qdrant)
    │
    ├── Hybrid Blend ──────────────→ weighted score (ALS 40% + Content 35%)
    │
    ├── LLM Reranker (Llama 3 8B) ──→ semantic reorder + rationale
    │
    └── Diversity Filter (MMR) ───→ final N recommendations
```

## Weights & Config

| Parameter | Default |
|---|---|
| `COLLAB_WEIGHT` | 0.40 |
| `CONTENT_WEIGHT` | 0.35 |
| `LLM_WEIGHT` | 0.25 |
| `DIVERSITY_PENALTY` | 0.15 |
| `REC_TOP_K` | 20 |
| `REC_FINAL_N` | 10 |

All weights are overridable via environment variables.

## Quick Start (Local Dev)

```bash
cd projects/06-ecommerce-recommendation

# Start dependencies
docker run -d -p 6333:6333 qdrant/qdrant
docker run -d -p 6379:6379 redis:7-alpine

# Install and run
pip install -r requirements.txt
cp .env.example .env  # fill in RHOAI endpoint + API key
uvicorn app.main:app --reload --port 8080
```

### Example: ingest a product

```bash
curl -X POST http://localhost:8080/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "sku-001",
    "title": "Wireless Noise-Cancelling Headphones",
    "description": "Premium over-ear headphones with 30h battery and ANC.",
    "category": "Electronics",
    "attributes": {"brand": "SoundX", "color": "black", "connectivity": "Bluetooth 5.3"},
    "price": 199.99
  }'
```

### Example: record a user event

```bash
curl -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u-123", "product_id": "sku-001", "event_type": "view"}'
```

### Example: get recommendations

```bash
curl -X POST http://localhost:8080/api/v1/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u-123",
    "user_profile": "Interested in wireless audio and home office gadgets. Budget-conscious.",
    "category_filter": "Electronics",
    "final_n": 5
  }'
```

## Deploy on RHOAI

```bash
# Production
oc apply -k deploy/kustomize/overlays/production

# Development
oc apply -k deploy/kustomize/overlays/dev
```

## File Structure

```
06-ecommerce-recommendation/
├── app/
│   ├── main.py                        # FastAPI app + lifespan
│   ├── api/v1/
│   │   ├── router.py
│   │   └── endpoints/
│   │       ├── recommendations.py     # POST /recommend, GET /recommend/:id
│   │       ├── products.py            # POST /products, POST /products/bulk
│   │       └── events.py              # POST /events
│   ├── core/
│   │   ├── config.py                  # pydantic-settings configuration
│   │   └── logging.py                 # structured JSON logging
│   ├── db/
│   │   ├── qdrant_client.py           # Qdrant async wrapper
│   │   └── redis_client.py            # Redis async wrapper + feature store
│   └── recommender/
│       ├── collaborative.py           # ALS scorer
│       ├── content_based.py           # E5-large embedding + Qdrant retrieval
│       ├── llm_recommender.py         # Llama 3 8B reranker
│       └── hybrid.py                  # Blend + diversity filter
├── deploy/kustomize/
│   ├── base/deployment.yaml           # Deployment, Service, Route, HPA, ConfigMap
│   └── overlays/{dev,production}/
├── Dockerfile
├── requirements.txt
└── .env.example
```

## GPU Resource Allocation

| Model | Node | VRAM |
|---|---|---|
| Llama 3 8B (AWQ 4-bit) | GPU node (A100 40 GB) | ~6 GB |
| E5-large embeddings | CPU (ModelMesh) | N/A |
| ALS collaborative model | CPU | N/A |

## Business KPIs

- 35% increase in conversion rate
- 50% increase in average order value
- 25% reduction in cart abandonment
- < 100 ms p99 recommendation latency (cached)
- < 500 ms p99 recommendation latency (fresh, no LLM)
- < 2 s p99 recommendation latency (with LLM reranking)
