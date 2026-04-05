"""ai_scientist/ingestion/domain_validator.py — AI-domain validation gate for papers."""

import logging
import re
from typing import List, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed arXiv category codes (AI / ML / NLP / CV / Robotics)
# ---------------------------------------------------------------------------

ALLOWED_CATEGORIES: Set[str] = {
    "cs.AI", "cs.CL", "cs.CV", "cs.LG", "cs.MA", "cs.NE",
    "stat.ML", "cs.IR", "cs.RO",
}

# ---------------------------------------------------------------------------
# Keyword-based heuristic for papers without arXiv metadata
# ---------------------------------------------------------------------------

AI_KEYWORDS: List[str] = [
    "machine learning", "deep learning", "neural network", "transformer",
    "attention mechanism", "reinforcement learning", "natural language processing",
    "computer vision", "generative model", "large language model", "llm",
    "graph neural network", "gnn", "convolutional neural network", "cnn",
    "recurrent neural network", "rnn", "diffusion model", "self-supervised",
    "contrastive learning", "foundation model", "prompt tuning", "fine-tuning",
    "pre-training", "multi-agent", "autonomous agent", "knowledge graph",
    "embedding", "semantic search", "retrieval-augmented", "rag",
]

MIN_KEYWORD_HITS = 3  # at least 3 keyword matches to pass heuristic


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def validate_by_category(categories: List[str]) -> Tuple[bool, str]:
    """Check whether any of the paper's arXiv categories are in the allowed set.

    Returns:
        (passed, reason)
    """
    if not categories:
        return False, "No arXiv categories provided"

    matched = [c for c in categories if c in ALLOWED_CATEGORIES]
    if matched:
        return True, f"Matched categories: {', '.join(matched)}"
    return False, f"Categories {categories} not in allowed set"


def validate_by_keywords(text: str) -> Tuple[bool, str]:
    """Heuristic: check whether the paper title + abstract mentions enough AI keywords.

    Args:
        text: Concatenation of title and abstract (or full paper text).

    Returns:
        (passed, reason)
    """
    if not text:
        return False, "No text provided for keyword validation"

    lower = text.lower()
    hits = [kw for kw in AI_KEYWORDS if kw in lower]

    if len(hits) >= MIN_KEYWORD_HITS:
        return True, f"Keyword hits ({len(hits)}): {', '.join(hits[:5])}"
    return False, f"Only {len(hits)} keyword hits (need {MIN_KEYWORD_HITS}): {hits}"


def validate_paper(
    categories: List[str] = None,
    title: str = "",
    abstract: str = "",
) -> Tuple[bool, str]:
    """Combined validation: category-first, then keyword fallback.

    Args:
        categories: arXiv category codes (e.g. ["cs.LG", "cs.AI"]).
        title:      Paper title.
        abstract:   Paper abstract text.

    Returns:
        (passed, reason)
    """
    # 1. Try category validation first (most reliable)
    if categories:
        passed, reason = validate_by_category(categories)
        if passed:
            logger.debug("Paper passed category validation: %s", reason)
            return True, reason
        logger.debug("Category validation failed: %s — trying keyword fallback", reason)

    # 2. Fall back to keyword heuristic
    combined_text = f"{title} {abstract}"
    passed, reason = validate_by_keywords(combined_text)
    if passed:
        logger.debug("Paper passed keyword validation: %s", reason)
        return True, reason

    logger.info("Paper REJECTED by domain validator: %s", reason)
    return False, reason


if __name__ == "__main__":  # pragma: no cover
    # Quick test
    ok, msg = validate_paper(
        categories=["cs.LG"],
        title="Attention Is All You Need",
        abstract="We propose a new simple network architecture, the Transformer.",
    )
    print(f"Passed: {ok}  Reason: {msg}")
