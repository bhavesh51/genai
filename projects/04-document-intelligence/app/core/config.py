"""
Project 4 – Document Intelligence
Core configuration
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SERVICE_NAME: str = "document-intelligence"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*"]

    # RHOAI inference (document Q&A + summarization)
    LLM_BASE_URL: str = "https://granite-vllm.rhoai-serving.svc.cluster.local/v1"
    LLM_API_KEY: str = "placeholder"
    LLM_MODEL_NAME: str = "ibm-granite/granite-3.1-8b-instruct"

    # NER model (RHOAI ModelMesh)
    NER_MODEL_URL: str = "https://ner-modelmesh.rhoai-serving.svc.cluster.local/v2/models/ner-model/infer"

    # Kafka (AMQ Streams)
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka-cluster-kafka-bootstrap.amq-streams.svc.cluster.local:9092"
    KAFKA_TOPIC_INGEST: str = "document-ingest"
    KAFKA_TOPIC_RESULTS: str = "document-results"
    KAFKA_CONSUMER_GROUP: str = "doc-intelligence-group"

    # ODF S3 (document storage)
    S3_ENDPOINT: str = "https://s3.openshift-storage.svc.cluster.local"
    S3_BUCKET_DOCUMENTS: str = "document-intelligence-raw"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # PostgreSQL HA
    DATABASE_URL: str = "postgresql://docuser:docpass@postgresql-ha.database.svc.cluster.local:5432/docdb"

    # OpenSearch
    OPENSEARCH_URL: str = "https://opensearch-cluster-master.opensearch.svc.cluster.local:9200"
    OPENSEARCH_INDEX: str = "documents"

    # Docling settings
    DOCLING_MAX_FILE_SIZE_MB: int = 100
    DOCLING_SUPPORTED_FORMATS: List[str] = ["pdf", "docx", "pptx", "html", "xlsx"]

    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://otel-collector.observability.svc.cluster.local:4317"
    OTEL_SERVICE_NAME: str = "document-intelligence"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
