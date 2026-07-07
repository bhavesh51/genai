# GenAI Platform — 10 Projects on Red Hat OpenShift AI 3.x

Production-grade GenAI microservices deployed on **Red Hat OpenShift AI (RHOAI) 3.x** using **NVIDIA A100 GPUs**.  
Each project is a self-contained FastAPI service with its own LLM stack, vector database, and Kustomize deployment manifests.

---

## Projects

| # | Project | Key Technologies | Status |
|---|---|---|---|
| 1 | [RAG-based Enterprise Knowledge Assistant](projects/01-rag-knowledge-assistant/) | Granite 3.1-8B · Milvus · LangChain | ✅ Complete |
| 2 | [Multi-Agent Platform](projects/02-multi-agent-platform/) | LangGraph · Redis · Tool-use agents | ✅ Complete |
| 3 | [LLM Fine-Tuning Pipeline](projects/03-llm-finetuning-pipeline/) | Kubeflow Pipelines · LoRA · QLoRA · S3 | ✅ Complete |
| 4 | [Document Intelligence](projects/04-document-intelligence/) | Docling · Kafka · async extraction | ✅ Complete |
| 5 | [Observability & Guardrails Proxy](projects/05-observability-guardrails/) | Prometheus · Grafana · content guardrails | ✅ Complete |
| 6 | [E-commerce Recommendation Engine](projects/06-ecommerce-recommendation/) | Llama 3 8B · E5-large · ALS · Qdrant · Redis | ✅ Complete |

> Projects 7–10 (Legal Analysis, Educational Content Generator, Supply Chain Optimization, Creative Content Platform) are defined in the [Architecture Plan](GenAI_Projects_Architecture_Plan.md) and will be implemented in subsequent iterations.

---

## Platform: Red Hat OpenShift AI 3.x

| Capability | Detail |
|---|---|
| **LLM Serving** | vLLM runtime (KServe) + ModelMesh for embeddings |
| **GPU** | NVIDIA A100 40 GB / 80 GB |
| **MLOps** | Kubeflow Pipelines, MLflow, Tekton CI/CD |
| **Storage** | OpenShift Data Foundation (ODF) S3-compatible |
| **Observability** | Prometheus · Grafana · OpenTelemetry · ELK |
| **Security** | RBAC · Istio service mesh · Vault secrets |

---

## Common Architecture

All services follow the same structural pattern:

```
projects/<NN>-<name>/
├── app/
│   ├── main.py                  # FastAPI app + lifespan
│   ├── core/config.py           # pydantic-settings
│   ├── core/logging.py          # structured JSON logging
│   ├── api/v1/                  # versioned API routers
│   └── <domain>/                # core ML / business logic
├── deploy/kustomize/
│   ├── base/deployment.yaml     # Deployment · Service · Route · HPA · ConfigMap
│   └── overlays/{dev,prod}/
├── Dockerfile                   # UBI9 Python 3.11 base
├── requirements.txt
└── .env.example
```

---

## Quick Start (any project)

```bash
cd projects/<NN>-<name>
pip install -r requirements.txt
cp .env.example .env          # fill in RHOAI endpoint + credentials
uvicorn app.main:app --reload
```

## Deploy to OpenShift

```bash
oc apply -k projects/<NN>-<name>/deploy/kustomize/overlays/production
```

---

## Architecture Plan

Detailed architecture, LLM selection rationale, training strategies, GPU optimization, and integration patterns for all 10 projects are documented in:

📄 [`GenAI_Projects_Architecture_Plan.md`](GenAI_Projects_Architecture_Plan.md)

---

## GPU Budget Summary

| Project | Model | VRAM per node |
|---|---|---|
| 1 – RAG Assistant | Granite 3.1-8B | ~16 GB |
| 2 – Multi-Agent | Granite 3.1-8B | ~16 GB |
| 3 – Fine-Tuning | Any (training) | 2× 40 GB |
| 4 – Document Intelligence | Layout model (CPU) | CPU only |
| 5 – Guardrails Proxy | Moderation model | ~8 GB |
| 6 – Recommendation Engine | Llama 3 8B (AWQ) | ~6 GB |

---

<sub>Red Hat OpenShift AI 3.x · NVIDIA A100 · Medium Enterprise Scale</sub>
