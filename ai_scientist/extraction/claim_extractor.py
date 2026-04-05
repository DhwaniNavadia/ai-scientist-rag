"""ai_scientist/extraction/claim_extractor.py — Extract claims from sections.json."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

from ai_scientist.config import OUTPUT_DIR
from ai_scientist.llm.llm_client import generate as llm_generate, has_keys, strip_code_fences

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLAIM_CUES: List[str] = [
    "we propose", "we introduce", "we present", "we develop", "we show",
    "our approach", "our model", "our method", "this paper presents",
    "this work introduces", "we demonstrate", "we achieve", "we outperform",
    "we improve", "we validate", "we evaluate",
]

MAX_CLAIMS = 10

# Minimum claim length in characters — reject very short or fragmentary claims
MIN_CLAIM_LENGTH = 40

# Prefixes that indicate metadata, not genuine claims
METADATA_PREFIXES = [
    "table ", "figure ", "fig.", "tab.", "appendix ", "supplementary ",
    "http", "arxiv:", "doi:", "isbn:", "@", "copyright",
]

# Minimum confidence to keep after post-filtering
MIN_CONFIDENCE = 0.5

# Regex-based noise patterns for _is_valid_claim
NOISE_PATTERNS = [
    r"^(figure|table|section|appendix|algorithm|eq\.|equation)\s+\d",
    r"^\[?\d+\]",           # reference markers: [1], 1.
    r"^et al",
    r"@",                   # email addresses
    r"^\s*http",            # URLs
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> List[str]:
    """Split *text* into individual sentences, preserving full stops."""
    # Normalise newlines, then split on sentence boundaries
    text = re.sub(r"-\s*\n", "", text)          # de-hyphenate PDF line-breaks
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def _has_quantitative(text: str) -> bool:
    """Return True if the sentence contains a numeric result (%, decimals, etc.)."""
    return bool(re.search(r"\d+(?:\.\d+)?\s*%|\b\d{2,}\b", text))


def _tail_sentences(sentences: List[str], idx: int, n: int = 2) -> str:
    """Return up to *n* sentences following index *idx* as evidence context."""
    tail = sentences[idx + 1: idx + 1 + n]
    return " ".join(tail)


# ---------------------------------------------------------------------------
# LLM-based claim extraction (FIX 7)
# ---------------------------------------------------------------------------

LLM_CLAIM_PROMPT = (
    "You are a precise scientific claim extractor. Given a section of a research paper, "
    "identify the key contribution claims. Return ONLY valid JSON: a list of objects with "
    'keys "claim_text" (the verbatim or paraphrased claim) and "evidence_text" '
    "(supporting sentence). Max 5 claims per section. If no claims, return []."
)


def _llm_extract_claims(section_name: str, text: str) -> List[Dict]:
    """Use OpenAI to extract claims from a section. Returns list of claim dicts."""
    if not has_keys():
        return []

    # Truncate very long sections to avoid token limits
    truncated = text[:4000]

    try:
        raw = llm_generate(
            prompt=f"Section: {section_name}\n\n{truncated}",
            system_prompt=LLM_CLAIM_PROMPT,
            temperature=0.2,
            max_tokens=500,
        )
        raw = strip_code_fences(raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            results = []
            for item in parsed:
                if isinstance(item, dict) and "claim_text" in item:
                    results.append({
                        "section": section_name,
                        "claim_text": item["claim_text"],
                        "evidence_text": item.get("evidence_text", ""),
                        "confidence": 0.85,
                    })
            return results
        return []
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("LLM claim extraction failed for %s: %s", section_name, exc)
        return []


# ---------------------------------------------------------------------------
# Noise filter: _is_valid_claim
# ---------------------------------------------------------------------------

def _is_valid_claim(text: str) -> bool:
    """Return True if *text* looks like a genuine scientific claim, not noise."""
    if not (20 <= len(text) <= 300):
        return False
    text_lower = text.lower().strip()
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, text_lower):
            return False
    return True


# ---------------------------------------------------------------------------
# Post-filter: quality checks on extracted claims
# ---------------------------------------------------------------------------

def _post_filter_claims(claims: List[Dict], section_name: str = "") -> List[Dict]:
    """Apply quality filters to remove low-quality, fragmentary, or metadata claims."""
    filtered = []
    for c in claims:
        text = c.get("claim_text", "").strip()

        # Regex-based noise pattern filter
        if not _is_valid_claim(text):
            logger.debug("Post-filter DROP (noise pattern or length): %s", text[:60])
            continue

        # Length filter (stricter: use MIN_CLAIM_LENGTH)
        if len(text) < MIN_CLAIM_LENGTH:
            logger.debug("Post-filter DROP (too short, %d chars): %s", len(text), text[:60])
            continue

        # Metadata prefix filter
        text_lower = text.lower()
        if any(text_lower.startswith(prefix) for prefix in METADATA_PREFIXES):
            logger.debug("Post-filter DROP (metadata prefix): %s", text[:60])
            continue

        # Confidence threshold filter
        if c.get("confidence", 1.0) < MIN_CONFIDENCE:
            logger.debug("Post-filter DROP (low confidence %.2f): %s",
                         c.get("confidence", 0), text[:60])
            continue

        # Reject claims that are mostly numeric (table rows that slipped through)
        alpha_chars = sum(1 for ch in text if ch.isalpha())
        if len(text) > 0 and alpha_chars / len(text) < 0.4:
            logger.debug("Post-filter DROP (too numeric): %s", text[:60])
            continue

        filtered.append(c)

    dropped = len(claims) - len(filtered)
    if dropped:
        label = f" from section {section_name}" if section_name else ""
        logger.info("Filtered %d noisy claims%s (kept %d)", dropped, label, len(filtered))
    return filtered


# ---------------------------------------------------------------------------
# Core extractor
# ---------------------------------------------------------------------------

def extract_claims(sections: Dict[str, str]) -> List[Dict]:
    """
    Extract key contribution claims from *sections* dict.
    Combines keyword-based and LLM-based extraction, deduplicates, and ranks.

    Returns a list of dicts with keys:
        claim_id, section, claim_text, evidence_text, confidence
    """
    raw: List[Dict] = []

    # --- Keyword-based extraction ---
    for section_name, text in sections.items():
        sentences = _split_sentences(text)
        for idx, sent in enumerate(sentences):
            low = sent.lower()
            if any(cue in low for cue in CLAIM_CUES):
                confidence = 0.9 if _has_quantitative(sent) else 0.75
                raw.append({
                    "section":       section_name,
                    "claim_text":    sent,
                    "evidence_text": _tail_sentences(sentences, idx),
                    "confidence":    confidence,
                })

    # --- LLM-based extraction (FIX 7, graceful fallback) ---
    llm_claims: List[Dict] = []
    if has_keys():
        for section_name, text in sections.items():
            try:
                llm_results = _llm_extract_claims(section_name, text)
                llm_claims.extend(llm_results)
            except Exception as exc:
                logger.warning("LLM extraction failed for %s, using keyword-only: %s",
                               section_name, exc)

    if llm_claims:
        logger.info("LLM extraction added %d claims", len(llm_claims))
        raw.extend(llm_claims)
    else:
        logger.info("Using keyword-only claim extraction")

    # Sort: confidence descending, then length descending (longer = more specific)
    raw.sort(key=lambda c: (c["confidence"], len(c["claim_text"])), reverse=True)

    # Deduplicate near-identical claim texts (keep first occurrence)
    seen: set = set()
    unique: List[Dict] = []
    for item in raw:
        key = item["claim_text"].lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    # Post-filter: remove low-quality, fragmentary, metadata claims
    unique = _post_filter_claims(unique)

    top = unique[:MAX_CLAIMS]

    # Apply sequential IDs
    claims = []
    for i, item in enumerate(top, start=1):
        claims.append({
            "claim_id":     f"C{i}",
            "section":      item["section"],
            "claim_text":   item["claim_text"],
            "evidence_text": item["evidence_text"],
            "confidence":   item["confidence"],
        })

    logger.info("Extracted %d claims", len(claims))
    return claims


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run() -> List[Dict]:
    """Load sections.json, extract claims, write claims.json. Returns list."""
    sections_path = OUTPUT_DIR / "sections.json"
    if not sections_path.exists():
        raise FileNotFoundError(f"sections.json not found — run pdf_parser first: {sections_path}")

    sections = json.loads(sections_path.read_text(encoding="utf-8"))
    claims = extract_claims(sections)

    out_path = OUTPUT_DIR / "claims.json"
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(claims, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(out_path))

    logger.info("Wrote %d claims to %s", len(claims), out_path)
    return claims


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run()
