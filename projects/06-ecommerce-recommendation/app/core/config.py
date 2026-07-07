"""
Project 6 – E-commerce Product Recommendation Engine
Core configuration using pydantic-settings
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service
    SERVICE_NAME: str = "ecommerce-recommendation"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    # RHOAI Model Serving – Llama 3 8B (vLLM)
    LLM_BASE_URL: str = "https://llama3-8b-vllm.rhoai-serving.svc.cluster.local/v1"
    LLM_API_KEY: str = "placeholder-replace-with-vault-secret"
    LLM_MODEL_NAME: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.3

    # RHOAI ModelMesh – E5-large embeddings
    EMBEDDING_BASE_URL: str = "https://e5-large-modelmesh.rhoai-serving.svc.cluster.local/v1"
    EMBEDDING_MODEL_NAME: str = "intfloat/e5-large-v2"
    EMBEDDING_DIMENSION: int = 1024

    # Qdrant (vector store for product embeddings)
    QDRANT_HOST: str = "qdrant.qdrant.svc.cluster.local"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "product_embeddings"

    # Redis (session + feature cache)
    REDIS_URL: str = "redis://redis.redis.svc.cluster.local:6379"
    REDIS_PASSWORD: str = ""
    REDIS_USER_TTL: int = 3600       # 1 hour
    REDIS_PRODUCT_TTL: int = 21600   # 6 hours

    # PostgreSQL (product catalogue + order history)
    DATABASE_URL: str = "postgresql+asyncpg://recuser:recpass@postgres.postgres.svc.cluster.local:5432/ecommerce"

    # Kafka (behaviour event streaming)
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka.kafka.svc.cluster.local:9092"
    KAFKA_TOPIC_EVENTS: str = "ecommerce.events"
    KAFKA_TOPIC_CATALOGUE: str = "ecommerce.catalogue"
    KAFKA_CONSUMER_GROUP: str = "recommendation-engine"

    # ODF S3 (model artefact storage)
    S3_ENDPOINT: str = "https://s3.openshift-storage.svc.cluster.local"
    S3_BUCKET_MODELS: str = "rec-engine-models"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # Recommendation settings
    REC_TOP_K: int = 20           # candidates to retrieve
    REC_FINAL_N: int = 10         # final recommendations to return
    COLLAB_WEIGHT: float = 0.40   # ALS score weight in hybrid blend
    CONTENT_WEIGHT: float = 0.35  # content-based score weight
    LLM_WEIGHT: float = 0.25      # LLM rerank weight
    DIVERSITY_PENALTY: float = 0.15  # intra-list diversity penalty

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector.observability.svc.cluster.local:4317"
    OTEL_SERVICE_NAME: str = "ecommerce-recommendation"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
