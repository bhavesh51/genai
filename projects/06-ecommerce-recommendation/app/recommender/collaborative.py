"""
Project 6 – E-commerce Product Recommendation Engine
Collaborative filtering scorer using a pre-trained ALS (implicit) model
loaded from ODF S3 at startup.
"""
import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

# Path where the ALS model artefact is mounted / downloaded
_MODEL_PATH = Path("/tmp/als_model.pkl")


class CollaborativeFilterScorer:
    """
    Wraps an `implicit.als.AlternatingLeastSquares` trained model to produce
    per-user item scores.  Falls back gracefully when the model is not loaded.
    """

    def __init__(self) -> None:
        self._model = None
        self._user_index: Dict[str, int] = {}
        self._item_index: Dict[str, int] = {}
        self._item_ids: List[str] = []

    def load(self, model_path: Path = _MODEL_PATH) -> None:
        if not model_path.exists():
            logger.warning("ALS model not found at %s – collaborative scores will be zero", model_path)
            return
        with open(model_path, "rb") as fh:
            artefact = pickle.load(fh)
        self._model = artefact["model"]
        self._user_index = artefact.get("user_index", {})
        self._item_index = artefact.get("item_index", {})
        self._item_ids = artefact.get("item_ids", [])
        logger.info("ALS model loaded from %s (%d items)", model_path, len(self._item_ids))

    def score(self, user_id: str, candidate_ids: List[str]) -> Dict[str, float]:
        """
        Return a dict {product_id: score} for each candidate.
        Score is the dot product of the user latent vector and each item latent vector.
        """
        if self._model is None or user_id not in self._user_index:
            return {pid: 0.0 for pid in candidate_ids}

        user_idx = self._user_index[user_id]
        user_vec = self._model.user_factors[user_idx]  # shape (factors,)

        scores: Dict[str, float] = {}
        for pid in candidate_ids:
            if pid in self._item_index:
                item_idx = self._item_index[pid]
                item_vec = self._model.item_factors[item_idx]
                scores[pid] = float(np.dot(user_vec, item_vec))
            else:
                scores[pid] = 0.0

        # Min-max normalise to [0, 1]
        values = list(scores.values())
        min_v, max_v = min(values), max(values)
        if max_v > min_v:
            scores = {k: (v - min_v) / (max_v - min_v) for k, v in scores.items()}
        return scores

    def get_top_candidates(self, user_id: str, top_k: int = 50) -> List[str]:
        """Return top-K item IDs from the ALS model for a user (cold-start returns empty)."""
        if self._model is None or user_id not in self._user_index:
            return []
        user_idx = self._user_index[user_id]
        user_vec = self._model.user_factors[user_idx]
        # Compute scores for all items
        scores = self._model.item_factors @ user_vec  # shape (n_items,)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [self._item_ids[i] for i in top_indices if i < len(self._item_ids)]


collaborative_scorer = CollaborativeFilterScorer()
