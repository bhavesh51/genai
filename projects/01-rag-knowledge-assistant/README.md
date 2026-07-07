# Project 1 — RAG-based Enterprise Knowledge Assistant

Enterprise-grade Retrieval-Augmented Generation service deployed on Red Hat OpenShift AI 3.x.

## Stack
- **LLM**: IBM Granite 3.1-8B-Instruct via RHOAI vLLM serving runtime
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (RHOAI ModelMesh)
- **Vector DB**: Milvus HA cluster (3 replicas)
- **Framework**: LangChain + FastAPI
- **Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2`

## Quick Start (Local Dev)
```bash
cd projects/01-rag-knowledge-assistant
pip install -r requirements.txt
cp .env.example .env  # fill in RHOAI endpoint + API key
uvicorn app.main:app --reload
```

## Deploy on RHOAI
```bash
oc apply -k deploy/kustomize/overlays/production
```
