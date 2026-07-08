# Project 7 — Legal Document Analysis & Contract Intelligence

AI-powered legal document analysis service deployed on Red Hat OpenShift AI 3.x.
Extracts clauses, scores risks across 15 categories, and answers natural-language
questions grounded in contract text using InLegalBERT embeddings and Llama 3 8B-Instruct.

## Architecture

```
POST /api/v1/documents              → Upload & analyse PDF/DOCX/TXT
GET  /api/v1/documents/{doc_id}     → Retrieve cached analysis result
GET  /api/v1/documents/{doc_id}/clauses → List all clauses for a document
POST /api/v1/qa                     → Answer questions about a contract
GET  /health                        → Liveness probe
GET  /ready                         → Readiness probe (Weaviate + Redis)
```

## Stack

| Component | Technology |
|---|---|
| **LLM (risk classification & Q&A)** | Meta Llama 3 8B-Instruct via RHOAI vLLM (AWQ 4-bit) |
| **Embeddings** | `law-ai/InLegalBERT` via RHOAI ModelMesh (768-dim) |
| **Vector store** | Weaviate v4 (HA cluster) |
| **Document cache** | Redis Cluster |
| **Relational DB** | PostgreSQL (document metadata via asyncpg) |
| **Document parsing** | pypdf (PDF), python-docx (DOCX), built-in (TXT) |
| **Framework** | FastAPI + asyncio |
| **Observability** | Prometheus + Grafana + OpenTelemetry |
| **Container base** | UBI9 Python 3.11 |

## Analysis Pipeline

```
Uploaded Document (PDF / DOCX / TXT)
    │
    ├── Parser (pypdf / python-docx) ──→ page chunks [{page, text}, …]
    │
    ├── Clause Extractor ──────────────→ segments on \n\n boundaries
    │       │                             min length 50 chars
    │       └── InLegalBERT Embeddings ─→ 768-dim vectors per clause
    │
    ├── Risk Scorer (Llama 3 8B) ──────→ 15-category classification
    │       │                             risk_score 0.0–1.0 per clause
    │       └── JSON mode response
    │
    ├── Weaviate upsert ───────────────→ clause + vector + metadata stored
    │
    └── Redis cache ───────────────────→ analysis result + clause list (TTL 24h)
```

## Risk Categories (15)

| # | Category |
|---|---|
| 1 | `indemnification` |
| 2 | `liability_cap` |
| 3 | `ip_ownership` |
| 4 | `termination` |
| 5 | `governing_law` |
| 6 | `dispute_resolution` |
| 7 | `confidentiality` |
| 8 | `data_protection` |
| 9 | `non_compete` |
| 10 | `force_majeure` |
| 11 | `limitation_of_liability` |
| 12 | `warranty` |
| 13 | `payment_terms` |
| 14 | `auto_renewal` |
| 15 | `assignment` |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/documents` | Upload + full analysis (PDF/DOCX/TXT, max 50 MB) |
| `GET` | `/api/v1/documents/{doc_id}` | Retrieve analysis from cache |
| `GET` | `/api/v1/documents/{doc_id}/clauses` | List all clauses with risk metadata |
| `POST` | `/api/v1/qa` | Answer a question about a contract |
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Readiness probe (Weaviate + Redis) |

## Quick Start (Local Dev)

```bash
cd projects/07-legal-document-analysis

# Start dependencies
docker run -d -p 8080:8080 semitechnologies/weaviate:1.25.0
docker run -d -p 6379:6379 redis:7-alpine

# Install and run
pip install -r requirements.txt
cp .env.example .env  # fill in RHOAI endpoint + API key
uvicorn app.main:app --reload --port 8000
```

### Example: upload and analyse a contract

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@/path/to/service_agreement.pdf"
```

**Response:**
```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "service_agreement.pdf",
  "clause_count": 42,
  "risk_summary": {
    "indemnification": 5,
    "liability_cap": 3,
    "ip_ownership": 4,
    "termination": 6,
    "governing_law": 2,
    "dispute_resolution": 2,
    "confidentiality": 7,
    "data_protection": 3,
    "non_compete": 2,
    "force_majeure": 1,
    "limitation_of_liability": 3,
    "warranty": 2,
    "payment_terms": 1,
    "auto_renewal": 0,
    "assignment": 1
  },
  "top_risks": [
    {
      "clause_id": "...",
      "text": "In no event shall either party be liable...",
      "risk_category": "limitation_of_liability",
      "risk_score": 0.92,
      "explanation": "Broad liability cap with no carve-outs for wilful misconduct.",
      "page": 7
    }
  ],
  "status": "analysed"
}
```

### Example: retrieve a previously analysed document

```bash
curl http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000
```

### Example: list all clauses

```bash
curl http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000/clauses
```

### Example: ask a question about the contract

```bash
curl -X POST http://localhost:8000/api/v1/qa \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "question": "What is the maximum liability cap and does it cover gross negligence?"
  }'
```

**Response:**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "What is the maximum liability cap and does it cover gross negligence?",
  "answer": "The liability cap is set at the total fees paid in the 12 months preceding the claim. The clause does not explicitly exclude gross negligence from the cap.",
  "source_clauses": [
    {
      "clause_id": "...",
      "text": "In no event shall either party's aggregate liability exceed...",
      "risk_category": "limitation_of_liability",
      "risk_score": 0.92,
      "page": 7,
      "distance": 0.08
    }
  ],
  "confidence": 0.87,
  "cached": false
}
```

## Deploy on RHOAI

```bash
# Production
oc apply -k deploy/kustomize/overlays/production
```

## File Structure

```
07-legal-document-analysis/
├── app/
│   ├── main.py                          # FastAPI app + lifespan
│   ├── api/v1/
│   │   ├── router.py
│   │   └── endpoints/
│   │       ├── documents.py             # POST /documents, GET /documents/{id}, GET /documents/{id}/clauses
│   │       └── qa.py                    # POST /qa
│   ├── core/
│   │   ├── config.py                    # pydantic-settings configuration
│   │   └── logging.py                   # structured JSON logging
│   ├── db/
│   │   ├── weaviate_client.py           # Weaviate v4 async wrapper
│   │   └── redis_client.py              # Redis async wrapper + doc cache
│   └── processing/
│       ├── parser.py                    # PDF/DOCX/TXT text extraction
│       ├── clause_extractor.py          # segmentation + InLegalBERT embeddings
│       └── risk_scorer.py               # 15-category LLM risk classification
├── deploy/kustomize/
│   ├── base/deployment.yaml             # Deployment, Service, Route, HPA, ConfigMap
│   └── overlays/production/
├── Dockerfile
├── requirements.txt
└── .env.example
```

## GPU Resource Allocation

| Model | Node | VRAM |
|---|---|---|
| Llama 3 8B-Instruct (AWQ 4-bit) | GPU node (A100 40 GB) | ~6 GB |
| InLegalBERT embeddings | CPU (ModelMesh) | N/A |

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `LLM_MODEL_NAME` | `meta-llama/Meta-Llama-3-8B-Instruct` | LLM for risk classification and Q&A |
| `EMBEDDING_MODEL_NAME` | `law-ai/InLegalBERT` | Legal domain embedding model (768-dim) |
| `WEAVIATE_CLASS` | `LegalClause` | Weaviate collection name |
| `REDIS_DOC_TTL` | `86400` | Document cache TTL in seconds (24 h) |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum file upload size |
| `MIN_CLAUSE_LENGTH` | `50` | Minimum characters for a clause to be indexed |
| `RISK_THRESHOLD` | `0.45` | Minimum risk score to flag a clause |

## Business KPIs

- 60% reduction in manual contract review time
- 95%+ clause extraction recall on standard commercial agreements
- < 5 s end-to-end analysis for a 20-page NDA
- < 1 s p99 Q&A latency (cached)
- < 15 s p99 Q&A latency (fresh, full LLM call)
