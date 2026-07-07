"""
Project 1 – RAG Knowledge Assistant
Core configuration using pydantic-settings
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service
    SERVICE_NAME: str = "rag-knowledge-assistant"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    # RHOAI Model Serving (vLLM endpoint)
    LLM_BASE_URL: str = "https://granite-vllm.rhoai-serving.svc.cluster.local/v1"
    LLM_API_KEY: str = "placeholder-replace-with-vault-secret"
    LLM_MODEL_NAME: str = "ibm-granite/granite-3.1-8b-instruct"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.1

    # Embedding model endpoint (RHOAI ModelMesh)
    EMBEDDING_BASE_URL: str = "https://embedding-modelmesh.rhoai-serving.svc.cluster.local/v1"
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # Milvus
    MILVUS_HOST: str = "milvus.milvus.svc.cluster.local"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = "root"
    MILVUS_PASSWORD: str = "milvus-secret"
    MILVUS_COLLECTION_PREFIX: str = "enterprise_rag"

    # Retrieval
    RETRIEVAL_TOP_K: int = 10
    RERANK_TOP_N: int = 4
    HYBRID_ALPHA: float = 0.7  # weight for dense vs sparse

    # ODF S3 (audit logging)
    S3_ENDPOINT: str = "https://s3.openshift-storage.svc.cluster.local"
    S3_BUCKET_AUDIT: str = "rag-audit-logs"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector.observability.svc.cluster.local:4317"
    OTEL_SERVICE_NAME: str = "rag-knowledge-assistant"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
