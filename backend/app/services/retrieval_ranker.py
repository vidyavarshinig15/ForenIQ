"""
Phase 10 — Retrieval Ranker & Hybrid Fusion

Combines lexical keyword candidates and semantic vector candidates into a unified,
deduplicated, ranked evidence candidate list. Exposes retrieval explanations and match types
without drawing subjective investigative conclusions.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from backend.app.core.config import get_settings
from backend.app.schemas.search import SearchResultItem

logger = logging.getLogger(__name__)


class RetrievalRanker:
    """
    Hybrid retrieval ranker combining lexical BM25/ILIKE matches and dense vector similarity.
    Supports weighted linear combination, Reciprocal Rank Fusion (RRF), exact match boosting,
    and deduplication.
    """

    def __init__(
        self,
        semantic_weight: Optional[float] = None,
        lexical_weight: Optional[float] = None,
        exact_boost: Optional[float] = None,
    ):
        settings = get_settings()
        self.semantic_weight = semantic_weight if semantic_weight is not None else settings.DEFAULT_SEMANTIC_WEIGHT
        self.lexical_weight = lexical_weight if lexical_weight is not None else settings.DEFAULT_LEXICAL_WEIGHT
        self.exact_boost = exact_boost if exact_boost is not None else settings.EXACT_MATCH_BOOST

    def rank_hybrid(
        self,
        lexical_items: List[SearchResultItem],
        semantic_items: List[SearchResultItem],
        query: str,
        top_k: int = 50,
    ) -> List[SearchResultItem]:
        """
        Merge and rank lexical and semantic results into a single deduplicated list.
        
        Scoring algorithm:
          1. Lexical rank score = 1.0 / (60 + lexical_rank)
          2. Semantic score = similarity_score (or 1.0 / (60 + semantic_rank))
          3. Exact match boost applied if exact identifier matches
          4. Combined score = (lexical_weight * norm_lex) + (semantic_weight * norm_sem) + boost
        """
        item_map: Dict[str, SearchResultItem] = {}
        lex_scores: Dict[str, float] = {}
        sem_scores: Dict[str, float] = {}
        is_exact: Dict[str, bool] = {}

        # 1. Process Lexical Candidates
        for rank, item in enumerate(lexical_items):
            item_id = str(item.id)
            item_map[item_id] = item
            # RRF lexical score component
            lex_scores[item_id] = 1.0 / (60.0 + rank + 1.0)
            if item.match_type == "EXACT_MATCH":
                is_exact[item_id] = True

        # 2. Process Semantic Candidates
        for rank, item in enumerate(semantic_items):
            item_id = str(item.id)
            if item_id not in item_map:
                item_map[item_id] = item
            # Semantic score uses direct cosine similarity score
            sim = getattr(item, "similarity_score", None)
            if sim is None or sim <= 0:
                sim = 1.0 / (60.0 + rank + 1.0)
            sem_scores[item_id] = float(sim)

        # Normalize score sets to [0, 1] range for fair weighted combination
        max_lex = max(lex_scores.values()) if lex_scores else 1.0
        max_sem = max(sem_scores.values()) if sem_scores else 1.0

        scored_items: List[Tuple[float, SearchResultItem]] = []

        for item_id, item in item_map.items():
            norm_lex = (lex_scores.get(item_id, 0.0) / max_lex) if max_lex > 0 else 0.0
            norm_sem = (sem_scores.get(item_id, 0.0) / max_sem) if max_sem > 0 else 0.0

            has_lex = item_id in lex_scores
            has_sem = item_id in sem_scores
            boost = self.exact_boost if is_exact.get(item_id, False) else 0.0

            combined_score = (self.lexical_weight * norm_lex) + (self.semantic_weight * norm_sem) + boost

            # Annotate item metadata
            if has_lex and has_sem:
                item.match_type = "HYBRID_MATCH"
                item.retrieval_explanation = f"Matched via Hybrid: Lexical relevance ({norm_lex:.2f}) + Semantic similarity ({norm_sem:.2f})"
            elif has_sem:
                item.match_type = "SEMANTIC_MATCH"
                item.retrieval_explanation = f"Matched via Semantic vector similarity ({norm_sem:.2f})"
            elif is_exact.get(item_id, False):
                item.match_type = "EXACT_MATCH"
                item.retrieval_explanation = "Matched via Exact record/identifier match"
            else:
                item.match_type = "TEXT_MATCH"
                item.retrieval_explanation = "Matched via Lexical text/keyword filter"

            item.similarity_score = round(combined_score, 4)
            scored_items.append((combined_score, item))

        # Sort descending by combined score
        scored_items.sort(key=lambda x: x[0], reverse=True)

        return [item for _, item in scored_items[:top_k]]
