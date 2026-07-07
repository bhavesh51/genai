"""
Project 4 – Document Intelligence
Async Kafka consumer – processes ingest events
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime

from aiokafka import AIOKafkaConsumer
from openai import AsyncOpenAI

from app.core.config import settings
from app.processing.parser import document_parser

logger = logging.getLogger(__name__)


class DocumentConsumer:
    def __init__(self):
        self._consumer: AIOKafkaConsumer = None
        self._llm = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )

    async def start(self):
        self._consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC_INGEST,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        await self._consumer.start()
        logger.info("Kafka consumer started: topic=%s", settings.KAFKA_TOPIC_INGEST)
        await self._consume_loop()

    async def stop(self):
        if self._consumer:
            await self._consumer.stop()

    async def _consume_loop(self):
        async for msg in self._consumer:
            event = msg.value
            try:
                await self._process_event(event)
                await self._consumer.commit()
            except Exception as exc:
                logger.exception("Error processing document event %s: %s", event.get("document_id"), exc)

    async def _process_event(self, event: dict):
        doc_id = event.get("document_id", str(uuid.uuid4()))
        s3_key = event.get("s3_key")
        filename = event.get("filename", "unknown")
        logger.info("Processing document: %s (%s)", doc_id, filename)

        # Download from S3 (simplified)
        import boto3, os, tempfile
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        with tempfile.NamedTemporaryFile(suffix=f"_{filename}", delete=False) as tmp:
            s3.download_fileobj(settings.S3_BUCKET_DOCUMENTS, s3_key, tmp)
            tmp_path = tmp.name

        # Parse
        text = document_parser.parse(tmp_path, filename)

        # Summarize via RHOAI LLM
        summary_resp = await self._llm.chat.completions.create(
            model=settings.LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": "Summarize the document concisely in 3-5 sentences."},
                {"role": "user", "content": text[:8000]},
            ],
            max_tokens=512,
        )
        summary = summary_resp.choices[0].message.content

        # Persist result (simplified – in prod write to PostgreSQL)
        result = {
            "document_id": doc_id,
            "filename": filename,
            "summary": summary,
            "processed_at": datetime.utcnow().isoformat(),
            "char_count": len(text),
        }
        logger.info("Processed document %s: %d chars, summary generated", doc_id, len(text))
        return result


document_consumer = DocumentConsumer()
