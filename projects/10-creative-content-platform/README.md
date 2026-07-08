# Project 10 — Creative Content Generation Platform

AI-powered creative content generation service deployed on Red Hat OpenShift AI 3.x.
Generates on-brand marketing copy, social media posts, and multi-language creative assets
using Llama 3 8B with brand guideline RAG, term-based compliance checking, and NLLB-200 translation.

---

## Stack

| Component | Technology |
|---|---|
| **LLM (content generation)** | Meta Llama 3 8B-Instruct via RHOAI vLLM (AWQ 4-bit) |
| **Embeddings** | `intfloat/e5-large-v2` via RHOAI ModelMesh (1024-dim) |
| **Translation** | `facebook/nllb-200-distilled-600M` via RHOAI ModelMesh (200 languages) |
| **Vector store** | Weaviate v4 (brand guidelines + creative assets) |
| **Asset cache** | Redis (7-day TTL, async hiredis) |
| **Relational DB** | PostgreSQL (asset metadata, audit trail) |
| **Framework** | FastAPI + asyncio |
| **Config** | pydantic-settings (env / `.env` file) |
| **Observability** | Prometheus + Grafana + OpenTelemetry |
| **Deployment** | OpenShift + Kustomize (HPA 2–12 replicas) |

---

## Content Pipeline

```
                        ┌──────────────────────────────────┐
  POST /content/copy    │  1. Fetch brand_id → Weaviate RAG │
  POST /content/        │     (top-5 guideline chunks)       │
       social-post      │                                    │
                        │  2. Inject chunks into system msg  │
                        │     (brand voice, tone, limits)    │
                        │                                    │
                        │  3. Call Llama 3 8B (vLLM)         │
                        │     ├── copy: free-form text        │
                        │     └── social: JSON mode           │
                        │                                    │
                        │  4. ComplianceChecker.check()       │
                        │     (prohibited terms scan)         │
                        │                                    │
                        │  5. Store asset in Redis (7d TTL)  │
                        │                                    │
                        │  6. Return {asset_id, content,     │
                        │     compliance, word_count / meta} │
                        └──────────────────────────────────┘

  POST /content/translate
       │
       ├── Fetch asset from Redis by asset_id
       ├── Call NLLB-200 via ModelMesh (httpx, falls back to source)
       └── Return {asset_id, original_language, target_language, translated_text}
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Readiness probe (Weaviate + Redis) |
| `POST` | `/api/v1/content/copy` | Generate long-form marketing copy |
| `POST` | `/api/v1/content/social-post` | Generate structured social media post |
| `POST` | `/api/v1/content/translate` | Translate an existing asset |
| `GET` | `/api/v1/assets/{asset_id}` | Retrieve asset from Redis |
| `GET` | `/api/v1/assets/search?q=...` | Semantic search over creative assets |
| `POST` | `/api/v1/assets/{asset_id}/approve` | Approve a creative asset |
| `DELETE` | `/api/v1/assets/{asset_id}` | Remove an asset from cache |
| `POST` | `/api/v1/brand/ingest` | Ingest brand guideline chunk into Weaviate |
| `GET` | `/api/v1/brand/{brand_id}/guidelines` | Retrieve top-5 guideline chunks |

---

## Quick Start (Local Dev)

```bash
cd projects/10-creative-content-platform

# Start dependencies
docker run -d -p 8080:8080 semitechnologies/weaviate:latest
docker run -d -p 6379:6379 redis:7-alpine

# Install and run
pip install -r requirements.txt
cp .env.example .env          # fill in LLM and embedding endpoint URLs
uvicorn app.main:app --reload --port 8080
```

### Ingest a brand guideline

```bash
curl -X POST http://localhost:8080/api/v1/brand/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "brand_id": "acme-corp",
    "content_type": "tone-of-voice",
    "text": "ACME Corp speaks with confidence and warmth. We avoid jargon, never use hyperbole, and always back claims with evidence."
  }'
```

### Generate marketing copy

```bash
curl -X POST http://localhost:8080/api/v1/content/copy \
  -H "Content-Type: application/json" \
  -d '{
    "brief": "Announce our new eco-friendly packaging initiative to existing customers.",
    "content_type": "email",
    "tone": "professional",
    "brand_id": "acme-corp"
  }'
```

### Generate a LinkedIn post

```bash
curl -X POST http://localhost:8080/api/v1/content/social-post \
  -H "Content-Type: application/json" \
  -d '{
    "brief": "Celebrate reaching 100,000 customers with a thank-you message.",
    "platform": "linkedin",
    "tone": "casual",
    "brand_id": "acme-corp"
  }'
```

### Translate an asset to French

```bash
curl -X POST http://localhost:8080/api/v1/content/translate \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "<asset_id from previous response>",
    "target_language": "french"
  }'
```

### Approve an asset

```bash
curl -X POST http://localhost:8080/api/v1/assets/<asset_id>/approve
```

### Search assets

```bash
curl "http://localhost:8080/api/v1/assets/search?q=eco+packaging&top_k=5&brand_id=acme-corp"
```

---

## Deploy on RHOAI

```bash
# Production
oc apply -k deploy/kustomize/overlays/production
```

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `SERVICE_NAME` | `creative-content-platform` | Service identifier for logging |
| `LLM_BASE_URL` | `https://.../v1` | vLLM OpenAI-compatible endpoint |
| `LLM_MODEL_NAME` | `meta-llama/Meta-Llama-3-8B-Instruct` | LLM model path |
| `LLM_MAX_TOKENS` | `2048` | Max generation tokens |
| `LLM_TEMPERATURE` | `0.7` | Sampling temperature |
| `EMBEDDING_MODEL_NAME` | `intfloat/e5-large-v2` | Embedding model |
| `EMBEDDING_DIMENSION` | `1024` | Embedding vector size |
| `TRANSLATION_BASE_URL` | `https://.../v1` | NLLB-200 ModelMesh endpoint |
| `WEAVIATE_HOST` | `weaviate.weaviate.svc.cluster.local` | Weaviate hostname |
| `WEAVIATE_BRAND_CLASS` | `BrandGuideline` | Weaviate class for brand data |
| `WEAVIATE_ASSET_CLASS` | `CreativeAsset` | Weaviate class for assets |
| `REDIS_ASSET_TTL` | `604800` | Redis TTL for assets (7 days) |
| `COMPLIANCE_THRESHOLD` | `0.8` | Minimum compliance score |

---

## File Structure

```
10-creative-content-platform/
├── app/
│   ├── main.py                           # FastAPI app + lifespan (Weaviate + Redis)
│   ├── api/v1/
│   │   ├── router.py                     # Aggregates content, assets, brand routers
│   │   └── endpoints/
│   │       ├── content.py                # POST /content/copy, social-post, translate
│   │       ├── assets.py                 # GET/POST/DELETE /assets/...
│   │       └── brand.py                  # POST /brand/ingest, GET /brand/{id}/guidelines
│   ├── core/
│   │   ├── config.py                     # pydantic-settings configuration
│   │   └── logging.py                    # structured JSON logging
│   ├── db/
│   │   ├── weaviate_client.py            # Weaviate v4 async wrapper
│   │   └── redis_client.py               # Redis async wrapper + asset/job cache
│   └── generator/
│       ├── copy_generator.py             # CopyGenerator (Llama 3 8B, RAG)
│       ├── social_post_generator.py      # SocialPostGenerator (JSON mode, platform limits)
│       ├── compliance_checker.py         # Term scan + LLM tone check
│       └── translator.py                 # NLLB-200 translation via httpx
├── deploy/kustomize/
│   ├── base/deployment.yaml              # Deployment, Service, Route, HPA, ConfigMap
│   └── overlays/production/
├── Dockerfile                            # UBI9 Python 3.11, EXPOSE 8080
├── requirements.txt
└── .env.example
```

---

## Compliance

The `ComplianceChecker` runs two independent checks:

1. **Term scan** (synchronous) — scans for 10 prohibited marketing terms including
   `"guaranteed returns"`, `"risk-free"`, `"miracle"`, `"cure"`, `"free money"`, etc.
   Returns a score of `1.0` (fully compliant) reduced by `0.1` per violation.

2. **Tone check** (async, LLM) — calls Llama 3 8B to verify the detected tone matches
   the requested tone. Returns `{"tone_match": bool, "detected_tone": str, "confidence": float}`.

Assets below `COMPLIANCE_THRESHOLD` (default `0.8`) are flagged and must be reviewed
before approval via `POST /assets/{asset_id}/approve`.
