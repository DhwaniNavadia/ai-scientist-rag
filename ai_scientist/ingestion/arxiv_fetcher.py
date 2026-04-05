"""ai_scientist/ingestion/arxiv_fetcher.py — Fetch recent AI papers from arXiv."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

from ai_scientist.config import DATA_DIR

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# arXiv category codes for AI / ML / NLP / CV
AI_CATEGORIES = {
    "cs.AI", "cs.CL", "cs.CV", "cs.LG", "cs.MA", "cs.NE",
    "stat.ML", "cs.IR", "cs.RO",
}

MAX_RESULTS = 50


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    abstract: str
    authors: List[str]
    categories: List[str]
    published: str
    pdf_url: str
    pdf_path: Optional[Path] = None


# ---------------------------------------------------------------------------
# Fetch + parse  (uses the `arxiv` SDK — more reliable than raw urllib)
# ---------------------------------------------------------------------------

def fetch_recent_papers(
    search_query: str = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL",
    max_results: int = MAX_RESULTS,
) -> List[ArxivPaper]:
    """Fetch recent papers from arXiv using the arxiv SDK.

    Returns:
        List of ArxivPaper objects (PDFs not yet downloaded).
    """
    import arxiv  # arxiv>=2.1.0

    client = arxiv.Client(page_size=min(max_results, 100), delay_seconds=3)
    search = arxiv.Search(
        query=search_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers: List[ArxivPaper] = []
    for result in client.results(search):
        # arxiv_id: strip version suffix (e.g. "2503.12345v1" → "2503.12345v1")
        raw_id = result.entry_id.split("/abs/")[-1]
        safe_id = raw_id.replace("/", "_")

        categories = [result.primary_category] + [
            c for c in result.categories if c != result.primary_category
        ]

        # Build PDF URL from entry id
        pdf_url = result.pdf_url or f"https://arxiv.org/pdf/{raw_id}.pdf"

        papers.append(ArxivPaper(
            arxiv_id=safe_id,
            title=result.title.strip(),
            abstract=result.summary.strip(),
            authors=[str(a) for a in result.authors],
            categories=categories,
            published=str(result.published),
            pdf_url=pdf_url,
        ))

    logger.info("Fetched %d papers from arXiv", len(papers))
    return papers


def filter_ai_papers(papers: List[ArxivPaper]) -> List[ArxivPaper]:
    """Keep only papers whose primary category is in AI_CATEGORIES."""
    kept = [p for p in papers if any(c in AI_CATEGORIES for c in p.categories)]
    logger.info("Filtered to %d AI-domain papers (from %d)", len(kept), len(papers))
    return kept


def download_pdf(paper: ArxivPaper, dest_dir: Path = DATA_DIR) -> Path:
    """Download the PDF for a single paper. Returns the local path."""
    import urllib.request

    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^\w\-.]", "_", paper.arxiv_id)
    pdf_path = dest_dir / f"{safe_id}.pdf"

    if pdf_path.exists() and pdf_path.stat().st_size > 1000:
        logger.debug("PDF already exists: %s", pdf_path)
        paper.pdf_path = pdf_path
        return pdf_path

    pdf_url = paper.pdf_url
    if not pdf_url:
        raise ValueError(f"No PDF URL for paper {paper.arxiv_id}")

    logger.info("Downloading %s → %s", pdf_url, pdf_path)
    req = urllib.request.Request(pdf_url, headers={"User-Agent": "ai-scientist/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        pdf_path.write_bytes(resp.read())

    if pdf_path.stat().st_size < 1000:
        pdf_path.unlink(missing_ok=True)
        raise IOError(f"Downloaded PDF is too small (likely error page): {paper.arxiv_id}")

    paper.pdf_path = pdf_path
    return pdf_path


# ---------------------------------------------------------------------------
# Convenience: fetch → filter → download
# ---------------------------------------------------------------------------

def fetch_and_download(
    search_query: str = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL",
    max_results: int = MAX_RESULTS,
    dest_dir: Path = DATA_DIR,
) -> List[ArxivPaper]:
    """End-to-end: fetch papers, filter to AI domain, download PDFs."""
    papers = fetch_recent_papers(search_query, max_results)
    ai_papers = filter_ai_papers(papers)

    for paper in ai_papers:
        try:
            download_pdf(paper, dest_dir)
        except Exception as exc:
            logger.warning("Failed to download %s: %s", paper.arxiv_id, exc)

    downloaded = [p for p in ai_papers if p.pdf_path and p.pdf_path.exists()]
    logger.info("Downloaded %d / %d papers", len(downloaded), len(ai_papers))
    return downloaded


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    results = fetch_and_download(max_results=5)
    for p in results:
        print(f"  {p.arxiv_id}: {p.title[:80]} → {p.pdf_path}")


# ---------------------------------------------------------------------------
# Convenience: fetch → filter → download
# ---------------------------------------------------------------------------

def fetch_and_download(
    search_query: str = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL",
    max_results: int = MAX_RESULTS,
    dest_dir: Path = DATA_DIR,
) -> List[ArxivPaper]:
    """End-to-end: fetch papers, filter to AI domain, download PDFs."""
    papers = fetch_recent_papers(search_query, max_results)
    ai_papers = filter_ai_papers(papers)

    for paper in ai_papers:
        try:
            download_pdf(paper, dest_dir)
        except Exception as exc:
            logger.warning("Failed to download %s: %s", paper.arxiv_id, exc)

    downloaded = [p for p in ai_papers if p.pdf_path and p.pdf_path.exists()]
    logger.info("Downloaded %d / %d papers", len(downloaded), len(ai_papers))
    return downloaded


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    results = fetch_and_download(max_results=5)
    for p in results:
        print(f"  {p.arxiv_id}: {p.title[:80]} → {p.pdf_path}")
