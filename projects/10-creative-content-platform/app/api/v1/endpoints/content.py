"""
Project 10 – Creative Content Generation Platform
Content generation endpoints:
  POST /content/copy          – generate long-form marketing copy
  POST /content/social-post   – generate social media post (Twitter/LinkedIn/Instagram)
  POST /content/translate     – translate an existing asset to a target language
"""
import logging
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.db.redis_client import redis_client
from app.db.weaviate_client import weaviate_client
from app.generator.compliance_checker import compliance_checker
from app.generator.copy_generator import copy_generator
from app.generator.social_post_generator import social_post_generator
from app.generator.translator import translator

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response models ──────────────────────────────────────────────────

class CopyRequest(BaseModel):
    brief: str = Field(..., description="Creative brief describing the copy goal", max_length=2000)
    content_type: Literal["blog", "email", "ad", "landing"] = Field(
        ..., description="Type of marketing copy to generate"
    )
    tone: Literal["formal", "casual", "playful", "professional"] = Field(
        ..., description="Desired tone of voice"
    )
    brand_id: str = Field(..., description="Brand identifier used to fetch guidelines from Weaviate")


class CopyResponse(BaseModel):
    asset_id: str
    content: str
    compliance: dict
    word_count: int


class SocialPostRequest(BaseModel):
    brief: str = Field(..., description="Creative brief for the social post", max_length=1000)
    platform: Literal["twitter", "linkedin", "instagram"] = Field(
        ..., description="Target social media platform"
    )
    tone: Literal["formal", "casual", "playful", "professional"] = Field(
        ..., description="Desired tone of voice"
    )
    brand_id: str = Field(..., description="Brand identifier used to fetch guidelines from Weaviate")


class SocialPostResponse(BaseModel):
    asset_id: str
    platform: str
    post_text: str
    hashtags: list
    char_count: int
    cta: str
    compliance: dict


class TranslateRequest(BaseModel):
    asset_id: str = Field(..., description="ID of an existing asset stored in Redis")
    target_language: str = Field(
        ..., description="Target language name (e.g. 'french') or FLORES-200 code (e.g. 'fra_Latn')"
    )


class TranslateResponse(BaseModel):
    asset_id: str
    original_language: str = "en"
    target_language: str
    translated_text: str


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _fetch_brand_context(brand_id: str, brief: str) -> list:
    """
    Retrieve top-5 brand guideline chunks from Weaviate using a simple
    keyword embedding approximation. Returns text strings for prompt injection.
    Falls back to an empty list if Weaviate is unavailable or brand not found.
    """
    try:
        # Use a zero-vector placeholder when no embedding service is wired locally.
        # In production the embedding service is called here to get a real query vector.
        from app.core.config import settings as cfg
        dummy_vector = [0.0] * cfg.EMBEDDING_DIMENSION
        chunks = await weaviate_client.search_brand_guidelines(
            brand_id=brand_id,
            query_vector=dummy_vector,
            top_k=5,
        )
        return [c["text"] for c in chunks if c.get("text")]
    except Exception as exc:
        logger.warning("Brand context fetch failed for brand_id=%s: %s", brand_id, exc)
        return []


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/content/copy",
    response_model=CopyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate on-brand marketing copy",
)
async def generate_copy(req: CopyRequest) -> CopyResponse:
    """
    Fetches brand guidelines from Weaviate, generates long-form copy with Llama 3 8B,
    runs a compliance check, caches the asset in Redis, and returns the result.
    """
    brand_context = await _fetch_brand_context(req.brand_id, req.brief)

    try:
        content = await copy_generator.generate(
            brief=req.brief,
            content_type=req.content_type,
            tone=req.tone,
            brand_context=brand_context,
        )
    except RuntimeError as exc:
        logger.exception("Copy generation failed for brand_id=%s", req.brand_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    compliance = compliance_checker.check(content)
    asset_id = str(uuid.uuid4())

    asset_payload = {
        "asset_id": asset_id,
        "brand_id": req.brand_id,
        "content_type": req.content_type,
        "tone": req.tone,
        "content": content,
        "compliance": compliance,
        "approved": False,
        "asset_kind": "copy",
    }
    await redis_client.set_asset(asset_id, asset_payload)

    return CopyResponse(
        asset_id=asset_id,
        content=content,
        compliance=compliance,
        word_count=len(content.split()),
    )


@router.post(
    "/content/social-post",
    response_model=SocialPostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an on-brand social media post",
)
async def generate_social_post(req: SocialPostRequest) -> SocialPostResponse:
    """
    Fetches brand guidelines, generates a structured social post with JSON mode,
    runs compliance check, stores the asset in Redis, and returns all metadata.
    """
    brand_context = await _fetch_brand_context(req.brand_id, req.brief)

    try:
        post = await social_post_generator.generate(
            brief=req.brief,
            platform=req.platform,
            tone=req.tone,
            brand_context=brand_context,
        )
    except RuntimeError as exc:
        logger.exception("Social post generation failed for brand_id=%s", req.brand_id)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    combined_text = post["post_text"] + " " + " ".join(post.get("hashtags", []))
    compliance = compliance_checker.check(combined_text)
    asset_id = str(uuid.uuid4())

    asset_payload = {
        "asset_id": asset_id,
        "brand_id": req.brand_id,
        "content_type": "social-post",
        "platform": post["platform"],
        "tone": req.tone,
        "content": post["post_text"],
        "hashtags": post.get("hashtags", []),
        "char_count": post.get("char_count", len(post["post_text"])),
        "cta": post.get("cta", ""),
        "compliance": compliance,
        "approved": False,
        "asset_kind": "social-post",
    }
    await redis_client.set_asset(asset_id, asset_payload)

    return SocialPostResponse(
        asset_id=asset_id,
        platform=post["platform"],
        post_text=post["post_text"],
        hashtags=post.get("hashtags", []),
        char_count=post.get("char_count", len(post["post_text"])),
        cta=post.get("cta", ""),
        compliance=compliance,
    )


@router.post(
    "/content/translate",
    response_model=TranslateResponse,
    status_code=status.HTTP_200_OK,
    summary="Translate an existing asset to a target language",
)
async def translate_asset(req: TranslateRequest) -> TranslateResponse:
    """
    Retrieves an asset from Redis by asset_id, translates its content using NLLB-200,
    and returns the translated text.
    """
    asset = await redis_client.get_asset(req.asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{req.asset_id}' not found in cache.",
        )

    source_text = asset.get("content", "")
    if not source_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Asset has no translatable content field.",
        )

    translated_text = await translator.translate(
        text=source_text,
        target_language=req.target_language,
    )

    return TranslateResponse(
        asset_id=req.asset_id,
        original_language="en",
        target_language=req.target_language,
        translated_text=translated_text,
    )
