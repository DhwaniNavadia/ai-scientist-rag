"""ai_scientist/ingestion/ingest_pipeline.py — End-to-end ingestion pipeline.

Pipeline:
  arXiv API → filter AI domain → download PDF → parse sections
           → chunk + embed → upsert to Qdrant Cloud → update registry

Usage:
  python -m ai_scientist.ingestion.ingest_pipeline            # 5 papers (default)
  python -m ai_scientist.ingestion.ingest_pipeline --n 10     # 10 papers
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

from ai_scientist.config import validate_qdrant_config, OUTPUT_DIR
from ai_scientist.ingestion.arxiv_fetcher import (
    fetch_recent_papers,
    filter_ai_papers,
    download_pdf,
    ArxivPaper,
)
from ai_scientist.ingestion.domain_validator import validate_paper
from ai_scientist.ingestion.paper_registry import PaperRegistry
from ai_scientist.ingestion.pdf_parser import parse_pdf
from ai_scientist.rag.document_store import DocumentStore

# ---------------------------------------------------------------------------
# Ingestion search query (AI-domain only)
# ---------------------------------------------------------------------------

DEFAULT_QUERY = (
    "cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.CV OR cat:stat.ML"
)
DEFAULT_MAX_PAPERS = 5


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_ingestion(
    max_papers: int = DEFAULT_MAX_PAPERS,
    search_query: str = DEFAULT_QUERY,
) -> Dict:
    """
    Fetch, filter, parse, embed, and store AI papers in Qdrant Cloud.

    Args:
        max_papers:   Maximum number of papers to ingest per run.
        search_query: arXiv API search query string.

    Returns:
        Summary dict with keys: fetched, filtered, skipped_duplicate,
        failed, indexed, total_vectors.
    """
    summary = {
        "fetched": 0,
        "filtered": 0,
        "skipped_duplicate": 0,
        "failed": 0,
        "indexed": 0,
        "total_vectors": 0,
    }

    # ── 0. Validate Qdrant credentials ───────────────────────────────────────
    if not validate_qdrant_config():
        logger.error(
            "Qdrant Cloud credentials not set. "
            "Add QDRANT_URL and QDRANT_API_KEY to .env and retry."
        )
        return summary

    # ── 1. Init shared services ───────────────────────────────────────────────
    registry = PaperRegistry()
    store    = DocumentStore()

    # ── 2. Fetch papers from arXiv ────────────────────────────────────────────
    logger.info("Fetching up to %d papers from arXiv …", max_papers)
    all_papers  = fetch_recent_papers(search_query, max_results=max_papers * 3)
    summary["fetched"] = len(all_papers)
    logger.info("Fetched %d papers from arXiv", len(all_papers))

    # ── 3. Filter to AI domain ────────────────────────────────────────────────
    ai_papers = filter_ai_papers(all_papers)
    # Secondary domain validation (keyword fallback for papers without clean categories)
    ai_papers = [
        p for p in ai_papers
        if validate_paper(p.categories, p.title, p.abstract)[0]
    ]
    summary["filtered"] = len(ai_papers)
    logger.info("Filtered to %d AI-domain papers", len(ai_papers))

    # cap at max_papers
    ai_papers = ai_papers[:max_papers]

    # ── 4. Process each paper ─────────────────────────────────────────────────
    for paper in ai_papers:
        paper_id = paper.arxiv_id
        logger.info("Processing paper: %s — %s", paper_id, paper.title[:80])

        # Skip only successfully indexed papers; retry failures
        existing = registry.get(paper_id)
        if existing and existing.status == "indexed":
            logger.info("  SKIP (already indexed): %s", paper_id)
            summary["skipped_duplicate"] += 1
            continue

        registry.register(
            paper_id=paper_id,
            title=paper.title,
            arxiv_id=paper_id,
            categories=paper.categories,
        )

        try:
            # 4a. Download PDF
            logger.info("  Downloading PDF …")
            pdf_path = download_pdf(paper)

            # 4b. Parse PDF into sections
            logger.info("  Parsing PDF …")
            sections = parse_pdf(pdf_path)

            total_chars = sum(len(v) for v in sections.values())
            if total_chars < 500:
                logger.warning("  PDF parsed but text is very short (%d chars) — skipping", total_chars)
                registry.update_status(paper_id, "failed")
                summary["failed"] += 1
                continue

            # 4c. Chunk + embed + upsert with rich metadata
            logger.info("  Indexing into Qdrant …")
            n_vectors = store.index_paper_full(
                paper_id=paper_id,
                sections=sections,
                title=paper.title,
                categories=paper.categories,
                source="arxiv",
            )

            registry.update_status(paper_id, "indexed")
            summary["indexed"] += 1
            summary["total_vectors"] += n_vectors
            logger.info(
                "  ✓ Stored %d vectors in Qdrant for '%s'",
                n_vectors, paper_id,
            )

        except Exception as exc:
            logger.error("  ✗ Failed to ingest %s: %s", paper_id, exc)
            registry.update_status(paper_id, "failed")
            summary["failed"] += 1

    # ── 5. Summary ────────────────────────────────────────────────────────────
    logger.info(
        "Ingestion complete — fetched=%d filtered=%d indexed=%d "
        "skipped=%d failed=%d total_vectors=%d",
        summary["fetched"],
        summary["filtered"],
        summary["indexed"],
        summary["skipped_duplicate"],
        summary["failed"],
        summary["total_vectors"],
    )
    return summary


# ---------------------------------------------------------------------------
# Verification helper
# ---------------------------------------------------------------------------

def verify_qdrant(expected_min_vectors: int = 1) -> bool:
    """Check the Qdrant collection exists and has at least *expected_min_vectors*."""
    if not validate_qdrant_config():
        return False
    store = DocumentStore()
    try:
        # Use count() — works across all recent qdrant-client versions
        count_result = store.client.count(store.collection_name)
        count = count_result.count
        logger.info(
            "Qdrant collection '%s': %d vectors",
            store.collection_name, count,
        )
        if count >= expected_min_vectors:
            logger.info("  ✓ Verification passed")
            return True
        logger.warning("  ! Only %d vectors (expected >= %d)", count, expected_min_vectors)
        return False
    except Exception as exc:
        logger.error("Qdrant verification failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description="Run AI paper ingestion pipeline")
    parser.add_argument(
        "--n", type=int, default=DEFAULT_MAX_PAPERS,
        metavar="N", help=f"Max papers to ingest (default: {DEFAULT_MAX_PAPERS})",
    )
    parser.add_argument(
        "--query", type=str, default=DEFAULT_QUERY,
        help="arXiv API search query",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Only run Qdrant verification, skip ingestion",
    )
    args = parser.parse_args()

    if args.verify_only:
        ok = verify_qdrant()
        sys.exit(0 if ok else 1)

    summary = run_ingestion(max_papers=args.n, search_query=args.query)
    verify_qdrant(expected_min_vectors=summary["total_vectors"])
    sys.exit(0 if summary["indexed"] > 0 or summary["skipped_duplicate"] > 0 else 1)


if __name__ == "__main__":
    main()
