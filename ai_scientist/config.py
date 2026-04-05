"""ai_scientist/config.py — Centralised paths and environment variables."""

import logging
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

ROOT_DIR   = Path(__file__).parent.parent
DATA_DIR   = ROOT_DIR / "data" / "papers"
OUTPUT_DIR = ROOT_DIR / "outputs"

# Legacy paper paths — kept for backward compatibility with cross_paper modules
# Prefer using PaperRegistry for new code.
PAPER1_PATH = DATA_DIR / "paper1.pdf"
PAPER2_PATH = DATA_DIR / "paper2.pdf"
PAPER3_PATH = DATA_DIR / "paper3.pdf"

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")

# ── Qdrant Cloud ─────────────────────────────────────────────────────────────
QDRANT_URL      = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY  = os.getenv("QDRANT_API_KEY", "")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ai_scientist")

OUTPUT_DIR.mkdir(exist_ok=True)


def validate_qdrant_config() -> bool:
    """Return True if Qdrant Cloud credentials are configured."""
    if not QDRANT_URL or not QDRANT_API_KEY:
        logger.warning(
            "QDRANT_URL and QDRANT_API_KEY are not set. "
            "RAG indexing/retrieval will be unavailable. "
            "Get credentials from https://cloud.qdrant.io"
        )
        return False
    return True
