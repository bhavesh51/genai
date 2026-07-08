"""
Project 10 – Creative Content Generation Platform
Core configuration using pydantic-settings
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service
    SERVICE_NAME: str = "creative-content-platform"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    # RHOAI Model Serving – Llama 3 8B (vLLM)
    LLM_BASE_URL: str = "https://llama3-8b-vllm.rhoai-serving.svc.cluster.local/v1"
    LLM_API_KEY: str = "placeholder-replace-with-vault-secret"
    LLM_MODEL_NAME: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.7

    # RHOAI ModelMesh – E5-large embeddings
    EMBEDDING_BASE_URL: str = "https://e5-large-modelmesh.rhoai-serving.svc.cluster.local/v1"
    EMBEDDING_MODEL_NAME: str = "intfloat/e5-large-v2"
    EMBEDDING_DIMENSION: int = 1024

    # RHOAI ModelMesh – NLLB-200 translation
    TRANSLATION_BASE_URL: str = "https://nllb-modelmesh.rhoai-serving.svc.cluster.local/v1"
    TRANSLATION_MODEL_NAME: str = "facebook/nllb-200-distilled-600M"

    # Weaviate (vector store for brand guidelines + creative assets)
    WEAVIATE_HOST: str = "weaviate.weaviate.svc.cluster.local"
    WEAVIATE_PORT: int = 8080
    WEAVIATE_API_KEY: str = ""
    WEAVIATE_BRAND_CLASS: str = "BrandGuideline"
    WEAVIATE_ASSET_CLASS: str = "CreativeAsset"

    # Redis (asset cache + job status)
    REDIS_URL: str = "redis://redis.redis.svc.cluster.local:6379"
    REDIS_PASSWORD: str = ""
    REDIS_ASSET_TTL: int = 604800  # 7 days

    # PostgreSQL (metadata store)
    DATABASE_URL: str = "postgresql+asyncpg://contentuser:contentpass@postgres.postgres.svc.cluster.local:5432/creative"

    # ODF S3 (asset binary storage)
    S3_ENDPOINT: str = "https://s3.openshift-storage.svc.cluster.local"
    S3_BUCKET_ASSETS: str = "creative-assets"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector.observability.svc.cluster.local:4317"
    OTEL_SERVICE_NAME: str = "creative-content-platform"

    # Compliance
    COMPLIANCE_THRESHOLD: float = 0.8


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
