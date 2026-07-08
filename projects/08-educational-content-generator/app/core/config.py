"""
Project 8 – Educational Content Generator
Core configuration using pydantic-settings
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SERVICE_NAME: str = "educational-content-generator"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    LLM_BASE_URL: str = "http://localhost:8001/v1"
    LLM_API_KEY: str = "local-dev-api-key"
    LLM_MODEL_NAME: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.5

    EMBEDDING_BASE_URL: str = "http://localhost:8002/v1"
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-mpnet-base-v2"
    EMBEDDING_DIMENSION: int = 768

    MILVUS_HOST: str = "milvus.milvus.svc.cluster.local"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = "root"
    MILVUS_PASSWORD: str = "milvus-secret"
    MILVUS_COLLECTION: str = "curriculum_chunks"

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""
    REDIS_SESSION_TTL: int = 7200
    REDIS_MASTERY_TTL: int = 604800
    REDIS_QUIZ_TTL: int = 3600

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/education"

    BKT_P_INIT: float = 0.3
    BKT_P_LEARN: float = 0.2
    BKT_P_FORGET: float = 0.05
    BKT_P_GUESS: float = 0.25
    BKT_P_SLIP: float = 0.1

    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "educational-content-generator"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
