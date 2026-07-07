"""
Project 1 – RAG Knowledge Assistant
Query endpoint: streaming + non-streaming RAG
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.rag.chain import rag_chain

logger = logging.getLogger(__name__)
router = APIRouter()


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096, description="User question")
    tenant_id: str = Field(..., description="Tenant / namespace identifier")
    stream: bool = Field(False, description="Enable streaming response (SSE)")
    conversation_history: Optional[List[dict]] = Field(
        default=None, description="Previous messages for multi-turn"
    )


class QueryResponse(BaseModel):
    answer: str
    tenant_id: str
    query: str


async def _stream_generator(query: str, tenant_id: str, history: Optional[List[dict]]):
    async for chunk in rag_chain.query(query, tenant_id, history, stream=True):
        yield f"data: {json.dumps({'delta': chunk})}\n\n"
    yield "data: [DONE]\n\n"


@router.post("", response_model=None, summary="Query the knowledge base")
async def query_endpoint(request: QueryRequest):
    if request.stream:
        return StreamingResponse(
            _stream_generator(
                request.query, request.tenant_id, request.conversation_history
            ),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )
    # Non-streaming
    answer_parts = []
    async for chunk in rag_chain.query(
        request.query, request.tenant_id, request.conversation_history, stream=False
    ):
        answer_parts.append(chunk)
    return QueryResponse(
        answer="".join(answer_parts),
        tenant_id=request.tenant_id,
        query=request.query,
    )
