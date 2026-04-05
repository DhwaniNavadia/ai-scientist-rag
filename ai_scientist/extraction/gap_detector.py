"""ai_scientist/extraction/gap_detector.py — Detect research gaps from sections."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

from ai_scientist.config import OUTPUT_DIR

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GAP_SIGNALS: List[str] = [
    "limitation", "future work", "open problem", "challenge",
    "not yet", "remains unclear", "however", "despite", "unfortunately",
    "difficult to", "hard to", "need to address", "beyond the scope",
    "not scalable", "intractable", "require substantial", "may be infeasible",
    "does not", "cannot", "fail to", "would be poor", "may not",
]

GAP_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "data_quality":    ["ground truth", "annotation", "labeling", "data quality",
                        "noisy data", "low-quality", "floor plan quality", "resolution"],
    "human_alignment": ["human preference", "human judgment", "user study",
                        "subjective", "alignment", "human-evaluated",
                        "human decision", "human evaluator"],
    "scalability":     ["scale", "large-scale", "computational cost", "efficiency",
                        "real-world deployment", "intractable", "not scalable",
                        "scalability", "computational complexity", "runtime"],
    "manual_effort":   ["manual", "hand-crafted", "labor-intensive", "expert",
                        "annotation cost", "manual editing", "manually"],
}

DIRECTION_TEMPLATES: Dict[str, str] = {
    "data_quality":    "Develop robust preprocessing or augmentation techniques to handle imperfect input data",
    "human_alignment": "Incorporate human feedback mechanisms and preference-aware constraints into the optimisation",
    "scalability":     "Investigate decomposition, approximation, or distributed methods to scale to larger instances",
    "manual_effort":   "Design automated or self-supervised procedures to reduce reliance on manual intervention",
}

MAX_ACTIONABLE = 16

# Metadata patterns that should never appear in legitimate gap sentences
_METADATA_BLOCKLIST = [
    "@", "arxiv", ".com", ".edu", ".org", "university", "institute",
    "department of", "proceedings", "conference", "journal of",
    "copyright", "license", "abstract", "keywords:",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> List[str]:
    """Sentence-split section text."""
    text = re.sub(r"-\s*\n", "", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 30]


def _is_garbage_text(text: str) -> bool:
    """Return True if text is PDF metadata/boilerplate rather than a real sentence."""
    low = text.lower()

    # Contains email addresses or institutional affiliations
    if any(bl in low for bl in _METADATA_BLOCKLIST):
        return True

    # More than 3 capitalised proper nouns in a row (author list)
    words = text.split()
    consecutive_caps = 0
    max_caps = 0
    for w in words:
        if w[0:1].isupper() and len(w) > 1 and not w.isupper():
            consecutive_caps += 1
            max_caps = max(max_caps, consecutive_caps)
        else:
            consecutive_caps = 0
    if max_caps >= 5:
        return True

    # Very short or mostly non-alphabetic
    alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
    if alpha_ratio < 0.5:
        return True

    # Sentence doesn't end with punctuation (likely truncated metadata)
    if not text.rstrip().endswith(('.', '!', '?', ')', ']')):
        return True

    return False


def _classify_gap_type(text: str) -> str:
    low = text.lower()
    for gap_type, keywords in GAP_TYPE_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return gap_type
    return "scalability"


def _generate_direction(gap_text: str, gap_type: str) -> str:
    """Derive a concise actionable direction from the gap sentence."""
    low = gap_text.lower()
    if "manual" in low or "editing" in low:
        return "Automate the manual steps to reduce human effort in the pipeline"
    if "scalab" in low or "large" in low or "intractable" in low:
        return "Extend the approach to handle large-scale instances efficiently"
    if "quality" in low or "noisy" in low or "low-quality" in low:
        return "Improve robustness to variations in input data quality"
    if "human" in low or "preference" in low or "alignment" in low:
        return "Incorporate human preference learning into the objective function"
    if "represent" in low or "sparse" in low:
        return "Develop automated representation learning to replace manual feature engineering"
    return DIRECTION_TEMPLATES.get(gap_type, "Investigate techniques to address this research challenge")


def _jaccard(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two strings."""
    s1 = set(a.lower().split())
    s2 = set(b.lower().split())
    union = s1 | s2
    if not union:
        return 0.0
    return len(s1 & s2) / len(union)


def _deduplicate(gaps: List[Dict], threshold: float = 0.7) -> List[Dict]:
    """Remove near-duplicate gaps (Jaccard > threshold)."""
    unique: List[Dict] = []
    for gap in gaps:
        if not any(_jaccard(gap["gap_text"], u["gap_text"]) > threshold for u in unique):
            unique.append(gap)
    return unique


# ---------------------------------------------------------------------------
# Core detector
# ---------------------------------------------------------------------------

def detect_gaps(sections: Dict[str, str]) -> Tuple[List[Dict], List[Dict]]:
    """
    Scan *sections* for research-gap sentences.

    Returns:
        (raw_gaps, actionable_gaps)
        raw_gaps       — every matched sentence, no curation
        actionable_gaps — deduplicated, typed, with actionable directions, IDs G1..G16
    """
    raw: List[Dict] = []

    for section_name, text in sections.items():
        sentences = _split_sentences(text)
        for sent in sentences:
            if _is_garbage_text(sent):
                continue
            low = sent.lower()
            if any(sig in low for sig in GAP_SIGNALS):
                raw.append({
                    "source_section": section_name,
                    "gap_text":       sent,
                    "gap_type":       _classify_gap_type(sent),
                })

    logger.info("Found %d raw gap sentences", len(raw))

    # Curate: deduplicate → trim → assign IDs + directions
    deduped = _deduplicate(raw)
    deduped = deduped[:MAX_ACTIONABLE]

    actionable: List[Dict] = []
    for i, item in enumerate(deduped, start=1):
        actionable.append({
            "gap_id":              f"G{i}",
            "gap_type":            item["gap_type"],
            "gap_text":            item["gap_text"],
            "source_section":      item["source_section"],
            "actionable_direction": _generate_direction(item["gap_text"], item["gap_type"]),
        })

    logger.info("Curated %d actionable gaps", len(actionable))
    return raw, actionable


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run() -> Tuple[List[Dict], List[Dict]]:
    """Load sections.json, detect gaps, write gaps_rulebased.json + gaps_actionable.json."""
    sections_path = OUTPUT_DIR / "sections.json"
    if not sections_path.exists():
        raise FileNotFoundError(f"sections.json not found — run pdf_parser first: {sections_path}")

    sections = json.loads(sections_path.read_text(encoding="utf-8"))
    raw, actionable = detect_gaps(sections)

    for filename, data in [("gaps_rulebased.json", raw), ("gaps_actionable.json", actionable)]:
        out_path = OUTPUT_DIR / filename
        tmp = out_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(out_path))
        logger.info("Wrote %d items to %s", len(data), out_path)

    return raw, actionable


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run()
