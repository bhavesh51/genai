"""
Project 9 – Supply Chain Optimization Agent
Core configuration using pydantic-settings
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SERVICE_NAME: str = "supply-chain-agent"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    # RHOAI vLLM (Llama 3 8B)
    LLM_BASE_URL: str = "https://llama3-vllm.rhoai-serving.svc.cluster.local/v1"
    LLM_API_KEY: str = "placeholder"
    LLM_MODEL_NAME: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.2

    # Qdrant (supplier knowledge base)
    QDRANT_HOST: str = "qdrant.qdrant.svc.cluster.local"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "supplier_knowledge"

    # Redis (session / agent state cache)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""
    REDIS_SESSION_TTL: int = 86400  # 24 hours

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka.kafka.svc.cluster.local:9092"
    KAFKA_TOPIC_INVENTORY: str = "supply.inventory"
    KAFKA_TOPIC_ORDERS: str = "supply.orders"

    # Database
    DATABASE_URL: str = "postgresql://user:pass@postgresql.database.svc.cluster.local:5432/supplydb"

    # Agent behaviour
    MAX_AGENT_ITERATIONS: int = 5
    RISK_ALERT_THRESHOLD: float = 0.7

    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector.observability.svc.cluster.local:4317"
    OTEL_SERVICE_NAME: str = "supply-chain-agent"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
