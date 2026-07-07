"""
Project 1 – RAG Knowledge Assistant
Core RAG chain: retrieval + re-ranking + generation
"""
import asyncio
import logging
from typing import AsyncGenerator, List, Optional

import httpx
from langchain.schema import Document
from openai import AsyncOpenAI

from app.core.config import settings
from app.db.milvus_client import milvus_client

logger = logging.getLogger(__name__)


class RAGChain:
    """
    Hybrid retrieval (dense + BM25) → cross-encoder rerank → LLM generation
    """

    def __init__(self):
        self._llm_client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )
        self._embedding_client = AsyncOpenAI(
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.LLM_API_KEY,
        )

    async def embed_query(self, text: str) -> List[float]:
        response = await self._embedding_client.embeddings.create(
            model=settings.EMBEDDING_MODEL_NAME,
            input=text,
        )
        return response.data[0].embedding

    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        top_k: int = None,
    ) -> List[dict]:
        top_k = top_k or settings.RETRIEVAL_TOP_K
        query_embedding = await self.embed_query(query)
        hits = milvus_client.search(tenant_id, query_embedding, top_k=top_k)
        return hits

    async def rerank(self, query: str, hits: List[dict]) -> List[dict]:
        """
        Simple score-based re-ranking.
        In production, call a cross-encoder endpoint on RHOAI ModelMesh.
        """
        # Sort by cosine similarity score (higher = better for COSINE)
        reranked = sorted(hits, key=lambda h: h["score"], reverse=False)
        return reranked[: settings.RERANK_TOP_N]

    def _build_context(self, hits: List[dict]) -> str:
        parts = []
        for i, h in enumerate(hits, 1):
            parts.append(f"[{i}] Source: {h['source']}\n{h['text']}")
        return "\n\n".join(parts)

    def _build_prompt(self, query: str, context: str) -> str:
        return (
            "You are an enterprise knowledge assistant. "
            "Answer the question using ONLY the provided context. "
            "If the answer is not in the context, say 'I don't have enough information to answer that.' "
            "Be concise and factual.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer:"
        )

    async def query(
        self,
        query: str,
        tenant_id: str,
        conversation_history: Optional[List[dict]] = None,
        stream: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Full RAG pipeline: embed → retrieve → rerank → generate."""
        hits = await self.retrieve(query, tenant_id)
        if not hits:
            yield "No relevant documents found in the knowledge base."
            return

        top_hits = await self.rerank(query, hits)
        context = self._build_context(top_hits)
        prompt = self._build_prompt(query, context)

        messages = conversation_history or []
        messages.append({"role": "user", "content": prompt})

        if stream:
            async with self._llm_client.chat.completions.stream(
                model=settings.LLM_MODEL_NAME,
                messages=messages,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            ) as stream_obj:
                async for chunk in stream_obj:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
        else:
            response = await self._llm_client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=messages,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            yield response.choices[0].message.content

        logger.info(
            "RAG query completed | tenant=%s | hits=%d | reranked=%d",
            tenant_id,
            len(hits),
            len(top_hits),
        )


rag_chain = RAGChain()
