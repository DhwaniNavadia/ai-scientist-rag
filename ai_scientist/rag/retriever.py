"""ai_scientist/rag/retriever.py — Semantic search over Qdrant-indexed papers."""

import logging
from collections import Counter
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class RetrievalDiversityError(Exception):
    """Raised when retrieval cannot satisfy the minimum paper diversity requirement."""
    pass


class RAGRetriever:
    """
    Wraps DocumentStore to provide semantic search over indexed paper chunks.
    """

    def __init__(self, store) -> None:
        """
        Args:
            store: a DocumentStore instance (already initialised).
        """
        self.store = store

    # ------------------------------------------------------------------
    # Core retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        paper_id: Optional[str] = None,
        section_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Embed *query*, search Qdrant, and return top-k matching chunks.

        Args:
            query:          Natural-language query string.
            top_k:          Number of results to return.
            paper_id:       If set, restrict results to this paper.
            section_filter: If set, restrict results to this section name.

        Returns:
            List of dicts: {score, paper_id, section, chunk_index, text}
        """
        query_vec = self.store.embed([query])[0]

        query_filter = self._build_filter(paper_id, section_filter)

        # qdrant-client >= 1.12 uses query_points() instead of search()
        response = self.store.client.query_points(
            collection_name=self.store.collection_name,
            query=query_vec,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            {"score": r.score, **r.payload}
            for r in response.points
        ]

    # ------------------------------------------------------------------
    # MMR retrieval (Maximal Marginal Relevance)
    # ------------------------------------------------------------------

    def retrieve_mmr(
        self,
        query: str,
        top_k: int = 5,
        candidates: int = 20,
        lambda_param: float = 0.5,
        min_papers: int = 2,
        paper_id: Optional[str] = None,
        section_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Diversity-aware retrieval using Maximal Marginal Relevance.

        Fetches *candidates* from Qdrant, then iteratively selects *top_k*
        results that balance relevance (to the query) and diversity (from
        already-selected results).

        After initial selection, checks paper-level diversity. If a single paper
        dominates (>60% of results and <3 papers represented), re-runs with
        lambda_mult=0.3. Raises RetrievalDiversityError if min_papers cannot
        be satisfied after retry.

        Args:
            query:         Natural-language query string.
            top_k:         Number of results to return.
            candidates:    Size of initial candidate pool from Qdrant (top_k * 4).
            lambda_param:  Trade-off: 1.0 = pure relevance, 0.0 = pure diversity.
            min_papers:    Minimum number of distinct paper_ids required.
            paper_id:      If set, restrict results to this paper.
            section_filter: If set, restrict to this section name.

        Returns:
            List of dicts: {score, paper_id, section, chunk_index, text}

        Raises:
            RetrievalDiversityError: If min_papers cannot be met after retry.
        """
        # Use top_k * 4 as candidate pool if default candidates is too small
        actual_candidates = max(candidates, top_k * 4)

        selected = self._mmr_select(
            query, top_k, actual_candidates, lambda_param, paper_id, section_filter
        )

        if not selected:
            return []

        # If filtering to a single paper, skip diversity check
        if paper_id:
            return selected

        # Paper-level diversity check
        paper_counts = Counter(r["paper_id"] for r in selected)
        dominant = max(paper_counts.values())
        total = len(selected)

        if dominant / total > 0.6 and len(paper_counts) < 3:
            logger.info(
                "MMR diversity re-run: dominant paper has %d/%d chunks, only %d papers",
                dominant, total, len(paper_counts),
            )
            selected = self._mmr_select(
                query, top_k, actual_candidates, 0.3, paper_id, section_filter
            )
            paper_counts = Counter(r["paper_id"] for r in selected)

        if len(paper_counts) < min_papers:
            logger.warning(
                "MMR could only retrieve from %d paper(s) (need %d)",
                len(paper_counts), min_papers,
            )
            raise RetrievalDiversityError(
                f"Could not satisfy min_papers={min_papers}: "
                f"only {len(paper_counts)} paper(s) available in results"
            )

        return selected

    def _mmr_select(
        self,
        query: str,
        top_k: int,
        candidates: int,
        lambda_param: float,
        paper_id: Optional[str],
        section_filter: Optional[str],
    ) -> List[Dict]:
        """Internal MMR selection logic."""
        query_vec = np.array(self.store.embed([query])[0], dtype=np.float32)
        query_filter = self._build_filter(paper_id, section_filter)

        response = self.store.client.query_points(
            collection_name=self.store.collection_name,
            query=query_vec.tolist(),
            limit=candidates,
            query_filter=query_filter,
            with_payload=True,
        )

        if not response.points:
            return []

        # Build candidate matrix: relevance scores + embeddings
        cand_scores = []
        cand_payloads = []
        cand_texts = []
        for r in response.points:
            cand_scores.append(r.score)
            cand_payloads.append(r.payload)
            cand_texts.append(r.payload.get("text", ""))

        # Embed candidate texts to compute inter-candidate similarity
        cand_vecs = np.array(self.store.embed(cand_texts), dtype=np.float32)

        # Normalise query and candidate vectors for cosine similarity
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        norms = np.linalg.norm(cand_vecs, axis=1, keepdims=True) + 1e-10
        cand_normed = cand_vecs / norms

        # Relevance: cosine(query, candidate)
        relevances = cand_normed @ query_norm

        # Greedy MMR selection
        selected_indices: List[int] = []
        remaining = set(range(len(cand_scores)))

        for _ in range(min(top_k, len(cand_scores))):
            best_idx = -1
            best_mmr = -float("inf")

            for idx in remaining:
                rel = float(relevances[idx])

                # Max similarity to already-selected
                if selected_indices:
                    sims = [
                        float(cand_normed[idx] @ cand_normed[s])
                        for s in selected_indices
                    ]
                    max_sim = max(sims)
                else:
                    max_sim = 0.0

                mmr = lambda_param * rel - (1 - lambda_param) * max_sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = idx

            if best_idx < 0:
                break
            selected_indices.append(best_idx)
            remaining.discard(best_idx)

        return [
            {"score": cand_scores[i], **cand_payloads[i]}
            for i in selected_indices
        ]

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def retrieve_for_gap(self, gap_text: str, gap_id: str = "") -> List[Dict]:
        """Retrieve top-5 diverse chunks most relevant to a research gap (uses MMR).

        Returns list of dicts with keys: paper_id, section, score, text, gap_id.
        """
        try:
            results = self.retrieve_mmr(gap_text, top_k=5, lambda_param=0.5, min_papers=2)
        except RetrievalDiversityError:
            logger.warning("Diversity requirement not met for gap retrieval; returning best-effort")
            results = self._mmr_select(gap_text, 5, 20, 0.3, None, None)
        for r in results:
            r["gap_id"] = gap_id
        return results

    def retrieve_for_hypothesis(self, hypothesis_text: str, hypothesis_id: str = "") -> List[Dict]:
        """Retrieve top-5 diverse chunks that may support or contradict a hypothesis (uses MMR).

        Returns list of dicts with keys: paper_id, section, score, text, hypothesis_id.
        """
        try:
            results = self.retrieve_mmr(hypothesis_text, top_k=5, lambda_param=0.5, min_papers=2)
        except RetrievalDiversityError:
            logger.warning("Diversity requirement not met for hypothesis retrieval; returning best-effort")
            results = self._mmr_select(hypothesis_text, 5, 20, 0.3, None, None)
        for r in results:
            r["hypothesis_id"] = hypothesis_id
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_filter(
        self, paper_id: Optional[str], section_filter: Optional[str]
    ):
        """Build a Qdrant Filter for optional paper_id / section constraints."""
        if not paper_id and not section_filter:
            return None

        from qdrant_client.models import FieldCondition, Filter, MatchValue

        conditions = []
        if paper_id:
            conditions.append(
                FieldCondition(key="paper_id", match=MatchValue(value=paper_id))
            )
        if section_filter:
            conditions.append(
                FieldCondition(key="section", match=MatchValue(value=section_filter))
            )

        return Filter(must=conditions)
