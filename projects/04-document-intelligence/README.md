# Project 4 — Real-time Document Intelligence Service

Streaming document processing pipeline using IBM Docling, Kafka (AMQ Streams), and RHOAI inference.

## Stack
- **Parsing**: IBM Docling (PDF/DOCX/PPTX/HTML)
- **Streaming**: Apache Kafka via AMQ Streams on OpenShift
- **NER**: Custom spaCy model served on RHOAI ModelMesh
- **Classification**: DeBERTa-v3 zero-shot classification
- **Storage**: PostgreSQL HA + OpenSearch

## Quick Start
```bash
cd projects/04-document-intelligence
pip install -r requirements.txt
docker-compose up -d kafka postgres opensearch
uvicorn app.main:app --reload
```

## Deploy on RHOAI
```bash
oc apply -k deploy/kustomize/overlays/production
```
