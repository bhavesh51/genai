"""
Project 2 – Multi-Agent Platform
Core configuration
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SERVICE_NAME: str = "multi-agent-platform"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    # RHOAI vLLM (Mistral)
    LLM_BASE_URL: str = "https://mistral-vllm.rhoai-serving.svc.cluster.local/v1"
    LLM_API_KEY: str = "placeholder"
    LLM_MODEL_NAME: str = "mistralai/Mistral-7B-Instruct-v0.3"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 8192

    # Redis (shared agent memory)
    REDIS_URL: str = "redis://:password@redis-cluster.redis.svc.cluster.local:6379/0"
    REDIS_TTL_SECONDS: int = 86400  # 24 hours

    # Celery (async task queue)
    CELERY_BROKER_URL: str = "redis://:password@redis-cluster.redis.svc.cluster.local:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://:password@redis-cluster.redis.svc.cluster.local:6379/2"

    # Agent config
    MAX_AGENT_ITERATIONS: int = 15
    AGENT_TIMEOUT_SECONDS: int = 300
    ENABLE_HUMAN_IN_THE_LOOP: bool = True

    # Tool integrations
    SERPAPI_KEY: str = ""
    CODE_SANDBOX_URL: str = "http://code-sandbox.sandbox.svc.cluster.local:8888"
    DATABASE_URL: str = "postgresql://user:pass@postgresql-ha.database.svc.cluster.local:5432/agentdb"

    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector.observability.svc.cluster.local:4317"
    OTEL_SERVICE_NAME: str = "multi-agent-platform"
    JAEGER_ENDPOINT: str = "http://jaeger-collector.observability.svc.cluster.local:14268/api/traces"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
