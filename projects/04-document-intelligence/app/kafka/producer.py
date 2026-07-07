"""
Project 4 – Document Intelligence
Async Kafka producer
"""
import json
import logging
from typing import Any, Dict

from aiokafka import AIOKafkaProducer

from app.core.config import settings

logger = logging.getLogger(__name__)


class KafkaDocumentProducer:
    def __init__(self):
        self._producer: AIOKafkaProducer = None

    async def start(self):
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            compression_type="gzip",
            acks="all",
            enable_idempotence=True,
            max_request_size=10 * 1024 * 1024,  # 10 MB
        )
        await self._producer.start()
        logger.info("Kafka producer started: %s", settings.KAFKA_BOOTSTRAP_SERVERS)

    async def stop(self):
        if self._producer:
            await self._producer.stop()

    async def send_document(self, document_event: Dict[str, Any]) -> None:
        """Publish a document event to the ingest topic."""
        await self._producer.send_and_wait(
            settings.KAFKA_TOPIC_INGEST,
            value=document_event,
        )
        logger.debug("Published document event: %s", document_event.get("document_id"))


kafka_producer = KafkaDocumentProducer()
