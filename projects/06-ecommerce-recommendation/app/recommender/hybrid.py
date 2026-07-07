"""
Project 6 – E-commerce Product Recommendation Engine
Hybrid recommendation engine: blends ALS, content-based, and LLM reranking
with configurable weights and intra-list diversity filtering.
"""
import logging
from typing import Dict, List, Optional

from app.core.config import settings
from app.recommender.collaborative import collaborative_scorer
from app.recommender.content_based import content_scorer
from app.recommender.llm_recommender import llm_reranker

logger = logging.getLogger(__name__)


def _apply_diversity_penalty(
    candidates: List[dict],
    selected: List[dict],
    penalty: float,
) -> List[dict]:
    """
    MMR-style diversity: penalise candidates in the same category as
    already-selected items.
    """
    selected_categories = {s.get("category") for s in selected}
    for c in candidates:
        if c.get("category") in selected_categories:
            c["hybrid_score"] = c["hybrid_score"] * (1.0 - penalty)
    return sorted(candidates, key=lambda x: x["hybrid_score"], reverse=True)


class HybridRecommender:
    """
    Orchestrates the full recommendation pipeline:
      1. Gather candidates from ALS + content-based retrieval
      2. Blend scores with configured weights
      3. Optionally rerank the top slice with the LLM
      4. Apply diversity filter
    """

    async def recommend(
        self,
        user_id: str,
        user_profile: str,
        category_filter: Optional[str] = None,
        purchased_ids: Optional[List[str]] = None,
        use_llm: bool = True,
        top_k: int = None,
        final_n: int = None,
    ) -> Dict:
        top_k = top_k or settings.REC_TOP_K
        final_n = final_n or settings.REC_FINAL_N
        purchased_ids = purchased_ids or []

        # ── 1. Collaborative candidates ────────────────────────────────────
        collab_ids = collaborative_scorer.get_top_candidates(user_id, top_k=top_k)
        collab_scores = collaborative_scorer.score(user_id, collab_ids)

        # ── 2. Content-based candidates ────────────────────────────────────
        content_candidates = await content_scorer.get_candidates(
            preference_text=user_profile,
            top_k=top_k,
            category_filter=category_filter,
            exclude_ids=purchased_ids,
        )
        content_map: Dict[str, dict] = {c["product_id"]: c for c in content_candidates}
        content_scores: Dict[str, float] = {
            c["product_id"]: c["content_score"] for c in content_candidates
        }

        # ── 3. Merge candidate pool ────────────────────────────────────────
        all_ids = list({*collab_ids, *content_map.keys()} - set(purchased_ids))

        # Also score any collab-only IDs with content scorer
        missing_content = [pid for pid in collab_ids if pid not in content_scores]
        if missing_content:
            extra_scores = await content_scorer.score_candidates(user_profile, missing_content)
            content_scores.update(extra_scores)

        # ── 4. Hybrid blend ────────────────────────────────────────────────
        merged: List[dict] = []
        for pid in all_ids:
            c_score = collab_scores.get(pid, 0.0) * settings.COLLAB_WEIGHT
            cb_score = content_scores.get(pid, 0.0) * settings.CONTENT_WEIGHT
            hybrid = c_score + cb_score

            product_meta = content_map.get(pid, {"product_id": pid, "title": "", "category": ""})
            merged.append({**product_meta, "hybrid_score": hybrid})

        # Sort by hybrid score
        merged.sort(key=lambda x: x["hybrid_score"], reverse=True)
        top_candidates = merged[:top_k]

        # ── 5. LLM rerank (optional) ───────────────────────────────────────
        rationale = "Recommended based on your activity."
        if use_llm:
            llm_result = await llm_reranker.rerank(
                user_profile=user_profile,
                candidates=top_candidates,
                top_n=final_n,
            )
            ranked_ids = llm_result.get("ranked_ids", [])
            rationale = llm_result.get("rationale", rationale)
            # Re-order top_candidates according to LLM ranking
            id_to_item = {c["product_id"]: c for c in top_candidates}
            reranked = [id_to_item[pid] for pid in ranked_ids if pid in id_to_item]
            # Append any missing items at the end
            seen = set(ranked_ids)
            reranked += [c for c in top_candidates if c["product_id"] not in seen]
            top_candidates = reranked

        # ── 6. Diversity pass ──────────────────────────────────────────────
        selected: List[dict] = []
        remaining = list(top_candidates)
        for _ in range(final_n):
            if not remaining:
                break
            # Pick top by current hybrid_score
            pick = remaining.pop(0)
            selected.append(pick)
            # Re-penalise remaining
            remaining = _apply_diversity_penalty(remaining, selected, settings.DIVERSITY_PENALTY)

        return {
            "user_id": user_id,
            "recommendations": selected[:final_n],
            "rationale": rationale,
            "strategy": "hybrid-als-content-llm",
        }


hybrid_recommender = HybridRecommender()
