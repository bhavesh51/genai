"""
Project 5 – Observability & Guardrails
Core configuration
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SERVICE_NAME: str = "observability-guardrails"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    # Guardrails thresholds
    PII_DETECTION_THRESHOLD: float = 0.85
    TOXICITY_THRESHOLD: float = 0.75
    PROMPT_INJECTION_THRESHOLD: float = 0.90
    HALLUCINATION_SCORE_THRESHOLD: float = 0.70

    # Upstream LLM proxy target (routes to appropriate RHOAI endpoint)
    UPSTREAM_LLM_URL: str = "https://granite-vllm.rhoai-serving.svc.cluster.local/v1"
    UPSTREAM_LLM_API_KEY: str = "placeholder"

    # TrustyAI
    TRUSTYAI_SERVICE_URL: str = "http://trustyai-service.rhoai.svc.cluster.local:8080"

    # PII model (RHOAI ModelMesh)
    PII_MODEL_URL: str = "https://pii-modelmesh.rhoai-serving.svc.cluster.local/v2/models/pii-detector/infer"

    # Toxicity model
    TOXICITY_MODEL_URL: str = "https://toxicity-modelmesh.rhoai-serving.svc.cluster.local/v2/models/toxicity-classifier/infer"

    # Prometheus metrics push
    PROMETHEUS_PUSHGATEWAY: str = "http://prometheus-pushgateway.monitoring.svc.cluster.local:9091"

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector.observability.svc.cluster.local:4317"
    OTEL_SERVICE_NAME: str = "observability-guardrails"

    # Alertmanager webhook
    ALERTMANAGER_URL: str = "http://alertmanager.monitoring.svc.cluster.local:9093"

    # Cost tracking
    GPU_COST_PER_HOUR_USD: float = 3.06  # A100 on-demand approx
    TOKEN_COST_PER_1K: float = 0.0001


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
