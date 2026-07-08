"""
Project 7 – Legal Document Analysis & Contract Intelligence
Core configuration using pydantic-settings
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service
    SERVICE_NAME: str = "legal-document-analysis"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    # RHOAI Model Serving – Llama 3 8B (vLLM)
    LLM_BASE_URL: str = "https://llama3-8b-vllm.rhoai-serving.svc.cluster.local/v1"
    LLM_API_KEY: str = "placeholder-replace-with-vault-secret"
    LLM_MODEL_NAME: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.1

    # RHOAI ModelMesh – InLegalBERT embeddings
    EMBEDDING_BASE_URL: str = "https://inlegalbert-modelmesh.rhoai-serving.svc.cluster.local/v1"
    EMBEDDING_MODEL_NAME: str = "law-ai/InLegalBERT"
    EMBEDDING_DIMENSION: int = 768

    # Weaviate (vector store for legal clauses)
    WEAVIATE_HOST: str = "weaviate.weaviate.svc.cluster.local"
    WEAVIATE_PORT: int = 8080
    WEAVIATE_API_KEY: str = ""
    WEAVIATE_CLASS: str = "LegalClause"

    # Redis (session + document analysis cache)
    REDIS_URL: str = "redis://redis.redis.svc.cluster.local:6379"
    REDIS_PASSWORD: str = ""
    REDIS_DOC_TTL: int = 86400   # 24 hours

    # PostgreSQL (document metadata)
    DATABASE_URL: str = "postgresql+asyncpg://legaluser:legalpass@postgres.postgres.svc.cluster.local:5432/legaldb"

    # ODF S3 (document storage)
    S3_ENDPOINT: str = "https://s3.openshift-storage.svc.cluster.local"
    S3_BUCKET_DOCS: str = "legal-documents"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector.observability.svc.cluster.local:4317"
    OTEL_SERVICE_NAME: str = "legal-document-analysis"

    # Upload / processing limits
    MAX_UPLOAD_SIZE_MB: int = 50
    MIN_CLAUSE_LENGTH: int = 50

    # Risk classification threshold
    RISK_THRESHOLD: float = 0.45


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
