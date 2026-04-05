"""ai_scientist/ingestion/pdf_parser.py — Convert a PDF into sections.json."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore

from ai_scientist.config import OUTPUT_DIR, PAPER1_PATH

# ---------------------------------------------------------------------------
# Section heading detection
# ---------------------------------------------------------------------------

# Maps first-word of a heading to the canonical output section.
# None  → drop that section (references, appendix, etc.)
HEADING_CANONICAL: Dict[str, Optional[str]] = {
    "abstract":       "abstract",
    "introduction":   "introduction",
    "related":        "introduction",   # 2.1 Related Problems → introduction
    "background":     "introduction",
    "framework":      "introduction",   # Section 3 Framework → introduction
    "methodology":    "introduction",
    "method":         "introduction",
    "approach":       "introduction",
    "preliminaries":  "introduction",
    "evaluation":     "evaluation",
    "experiments":    "evaluation",
    "experimental":   "evaluation",
    "results":        "evaluation",
    "conclusion":     "conclusion",
    "conclusions":    "conclusion",
    "disclaimer":     "conclusion",
    "references":     None,
    "reference":      None,
    "appendix":       None,
    "acknowledgments": None,
    "acknowledgements": None,
}

OUTPUT_SECTIONS: List[str] = ["abstract", "introduction", "evaluation", "conclusion"]


def _is_page_number(line: str) -> bool:
    """Return True if the line is solely a page number."""
    return bool(re.match(r"^\s*\d{1,4}\s*$", line))


def _detect_heading(line: str, next_line: str = "") -> Optional[str]:
    """
    Return the canonical section name if *line* (or *line* + *next_line*)
    constitutes a top-level section heading. Return '__skip__' for sections to
    drop. Return None if the line is ordinary content.

    Handles these PDF patterns:
      • "Abstract"
      • "2 Introduction",  "4 Evaluation"   (number + name on same line)
      • "2" / "Introduction"                 (number on one line, name on next)
    Subsections like "2.1 Related Problems" are treated as content (decimal).
    """
    stripped = line.strip()
    if not stripped:
        return None

    # ------- Pattern A: standalone keyword -------
    low = stripped.lower()
    if low in HEADING_CANONICAL:
        canonical = HEADING_CANONICAL[low]
        return "__skip__" if canonical is None else canonical

    # ------- Pattern B: "N keyword" or "N. keyword" (no decimal section #) -------
    m = re.match(r"^(\d+)[.\s]\s*(.+)$", stripped)
    if m and "." not in m.group(1):          # skip subsection numbers like 2.1
        first_word = m.group(2).strip().lower().split()[0]
        if first_word in HEADING_CANONICAL:
            canonical = HEADING_CANONICAL[first_word]
            return "__skip__" if canonical is None else canonical

    # ------- Pattern C: standalone section number, peek at next line -------
    if re.match(r"^\d{1,2}\s*$", stripped) and next_line.strip():
        first_word = next_line.strip().lower().split()[0]
        if first_word in HEADING_CANONICAL:
            canonical = HEADING_CANONICAL[first_word]
            return "__skip__" if canonical is None else canonical

    return None


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_pdf(path: Path) -> Dict[str, str]:
    """
    Extract text from *path* and return a dict mapping canonical section names
    to their full text content.  The four output keys are always present:
    ``abstract``, ``introduction``, ``evaluation``, ``conclusion``.
    """
    if PdfReader is None:
        raise ImportError("pypdf is required: pip install 'pypdf>=3.0.0'")

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    logger.info("Parsing PDF: %s", path)

    # Extract all lines from all pages
    reader = PdfReader(str(path))
    raw_lines: List[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        raw_lines.extend(text.splitlines())

    # ------------------------------------------------------------------
    # Two-pass approach:
    #   Pass 1 – detect section boundaries
    #   Pass 2 – bucket lines into sections
    # ------------------------------------------------------------------
    buckets: Dict[str, List[str]] = {s: [] for s in OUTPUT_SECTIONS}
    current: str = "abstract"        # default section before first heading

    n = len(raw_lines)
    i = 0
    while i < n:
        line = raw_lines[i]

        if _is_page_number(line):
            i += 1
            continue

        next_line = raw_lines[i + 1] if i + 1 < n else ""
        heading = _detect_heading(line, next_line)

        if heading is not None:
            current = heading          # change active section (or '__skip__')
            # Include the heading line in the section bucket (matches existing schema)
            if current != "__skip__":
                buckets[current].append(line.strip())
            i += 1
            continue

        if current == "__skip__":
            i += 1
            continue

        stripped = line.strip()
        if stripped:
            buckets[current].append(stripped)
        i += 1

    # Build section text, warn on empty
    sections: Dict[str, str] = {}
    for sec in OUTPUT_SECTIONS:
        lines = buckets[sec]
        if not lines:
            logger.warning("Section '%s' is empty after parsing — check heading detection", sec)
        sections[sec] = "\n".join(lines)

    logger.info(
        "Parsed %d sections: %s",
        len(sections),
        ", ".join(f"{k}={len(v)} chars" for k, v in sections.items()),
    )
    return sections


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run(paper_path: Path = PAPER1_PATH) -> Dict[str, str]:
    """Parse *paper_path* and write ``outputs/sections.json``. Returns the dict."""
    sections = parse_pdf(paper_path)

    out_path = OUTPUT_DIR / "sections.json"
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sections, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(out_path))

    logger.info("Wrote %s", out_path)
    return sections


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run()
