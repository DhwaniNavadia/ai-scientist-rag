"""
ai_scientist/cross_paper/claims_sectioned.py
Section-aware claim extractor for paper2 / paper3 (moved from cross_paper_claims_sectioned.py).

Now includes LLM-powered multi-paper synthesis that compares claims across papers
and produces a structured cross-paper analysis.

Fixes applied:
  • Dataset names (cora, citeseer, pubmed, ppi) are NOT filtered — they appear in
    legitimate result sentences.
  • looks_like_table_or_figure only rejects structurally table-like lines (starts
    with "figure/table N", pipe-separated, or heavy numeric columns), NOT lines that
    simply *mention* those keywords.
  • sentence_split minimum length lowered to 15; any sentence with a % number is kept
    regardless of length.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from ai_scientist.config import OUTPUT_DIR, PAPER2_PATH, PAPER3_PATH
from ai_scientist.llm.llm_client import generate as llm_generate, has_keys, strip_code_fences

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OUT_PATH = OUTPUT_DIR / "cross_paper_claims.json"

KEEP_SECTIONS: List[str] = [
    "experiment", "experiments", "experimental",
    "evaluation", "results", "discussion", "conclusion", "conclusions",
    "analysis", "ablation", "limitations",
]

DROP_SECTIONS: List[str] = [
    "related work", "background", "preliminaries", "references",
    "appendix", "supplementary", "acknowledgments", "acknowledgements",
]

CLAIM_CUES: List[str] = [
    "outperform", "outperforms", "improve", "improves", "improved",
    "achieve", "achieves", "achieved", "state-of-the-art", "sota",
    "we show", "we demonstrate", "we find", "results show", "results indicate",
    "significant", "consistent", "robust", "scalable", "efficient", "linear",
    "accuracy", "f1", "auc", "error", "loss", "runtime", "time", "memory",
    "attention", "convolution", "graph", "node classification",
]

# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("Missing dependency: pypdf.  Run: pip install pypdf")
        return ""

    try:
        reader = PdfReader(str(pdf_path))
        chunks: List[str] = []
        for page in reader.pages:
            txt = page.extract_text() or ""
            if txt.strip():
                chunks.append(txt)
        return "\n".join(chunks)
    except Exception as exc:
        logger.error("Failed to read PDF %s: %s", pdf_path, exc)
        return ""


def read_first_existing(paths: List[str]) -> str:
    for p in paths:
        pp = Path(p)
        if pp.exists():
            if pp.suffix.lower() == ".pdf":
                return extract_pdf_text(pp)
            return pp.read_text(encoding="utf-8", errors="ignore")
    return ""


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def is_heading(line: str) -> bool:
    l = line.strip()
    if len(l) < 3:
        return False
    if re.match(r"^\d+(\.\d+)*\s+[A-Za-z][A-Za-z \-]{2,}$", l):
        return True
    if l.isupper() and len(l) <= 60 and any(c.isalpha() for c in l):
        return True
    if len(l) <= 40 and re.match(r"^[A-Z][A-Za-z \-]{2,}$", l) and "." not in l:
        return True
    return False


def heading_name(line: str) -> str:
    l = line.strip()
    l = re.sub(r"^\d+(\.\d+)*\s+", "", l)
    return l.strip().lower()


def looks_like_table_or_figure(line: str) -> bool:
    """
    Return True only for lines that are *structurally* table rows or figure
    captions — NOT for lines that merely mention dataset or figure names.
    """
    s  = line.strip()
    s2 = normalize(s)

    # Conference paper boilerplate
    if "published as a conference paper" in s2:
        return True
    if "iclr" in s2 and "published as" in s2:
        return True

    # True figure / table captions (start with "Figure N" or "Table N")
    # NOT just any sentence containing "figure" or "table"
    if re.match(r"^\s*(figure|table)\s*\d", s2):
        return True

    # Known dataset table headers (multi-keyword, table-like)
    if any(h in s2 for h in ["nodes edges classes", "dataset type nodes",
                               "label rate", "# nodes", "# edges"]):
        return True

    # Very numeric — likely a table row (≥ 8 numbers)
    nums = re.findall(r"\d+(?:\.\d+)?%?", s2)
    if len(nums) >= 8:
        return True

    # Pipe-separated (markdown / latex table)
    if "|" in s and len(re.findall(r"\|", s)) >= 2:
        return True

    # Many short tokens — table column-like
    tokens = re.split(r"\s+", s)
    if len(tokens) >= 12:
        short = sum(1 for t in tokens if len(t) <= 3)
        if short / max(1, len(tokens)) > 0.45:
            return True

    # Diagram-like (x1 y2 z3 + layer/input/output)
    if re.search(r"\b[xyz]\d+\b", s2) and ("layer" in s2 or "input" in s2 or "output" in s2):
        return True

    return False


def sentence_split(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[\.\?\!])\s+", text)
    out: List[str] = []
    for p in parts:
        p = p.strip()
        # Keep if length >= 15, OR if contains a percentage (numeric result)
        if len(p) >= 15 or re.search(r"\d+\.?\d*\s*%", p):
            out.append(p)
    return out


def has_claim_signal(s: str) -> bool:
    s2 = normalize(s)

    # Drop metadata blobs
    if "university" in s2 and "abstract" in s2:
        return False
    if "proceedings" in s2 or "arxiv" in s2:
        return False

    # Must look like a sentence
    if "." not in s and "we " not in s2 and "shows" not in s2 and "demonstrate" not in s2:
        return False

    # Explicit cue words
    if any(c in s2 for c in CLAIM_CUES):
        return True

    # Has a percentage value
    if re.search(r"\d+(?:\.\d+)?\s*%", s2):
        return True

    # Non-year numeric metric
    nums = re.findall(r"\d+(?:\.\d+)?", s2)
    for n in nums:
        try:
            v = float(n)
        except ValueError:
            continue
        if 1900 <= v <= 2099 and float(v).is_integer():
            continue
        if v < 1900:
            return True

    return False


def extract_sectioned_claims(full_text: str, max_claims: int = 60) -> List[str]:
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not looks_like_table_or_figure(ln)]

    current = "unknown"
    buckets: dict = {}
    for ln in lines:
        if is_heading(ln):
            current = heading_name(ln)
            continue
        buckets.setdefault(current, []).append(ln)

    kept_chunks: List[str] = []
    for sec, sec_lines in buckets.items():
        sec_norm = normalize(sec)
        if any(d in sec_norm for d in DROP_SECTIONS):
            continue
        if any(k in sec_norm for k in KEEP_SECTIONS):
            kept_chunks.append(" ".join(sec_lines))

    if not kept_chunks:
        kept_chunks = [" ".join(lines)]

    claims: List[str] = []
    for chunk in kept_chunks:
        for sent in sentence_split(chunk):
            if not looks_like_table_or_figure(sent) and has_claim_signal(sent):
                claims.append(sent)

    # De-dup
    seen: set = set()
    unique: List[str] = []
    for c in claims:
        key = normalize(c)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    def score_sentence(s: str) -> float:
        s2 = normalize(s)
        score = 0.0
        if "we " in s2:
            score += 1.0
        if any(k in s2 for k in ["outperform", "improv", "achiev", "result",
                                   "accuracy", "runtime", "scalable"]):
            score += 1.0
        if re.search(r"\d+(?:\.\d+)?\s*%", s2):
            score += 1.0
        score += min(len(s2) / 200.0, 1.0)
        return score

    unique.sort(key=score_sentence, reverse=True)
    return unique[:max_claims]


# ---------------------------------------------------------------------------
# LLM-powered cross-paper synthesis
# ---------------------------------------------------------------------------

CROSS_PAPER_SYNTHESIS_PROMPT = (
    "You are a research analyst comparing claims from two different scientific papers.\n\n"
    "Analyze the claims below and produce a structured cross-paper synthesis.\n\n"
    "Return ONLY valid JSON with these EXACT keys:\n"
    '{\n'
    '  "shared_findings": [{"finding": "string", "paper_ids": ["paper2", "paper3"]}],\n'
    '  "contradictions": [{"claim_a": "string", "paper_a": "paper2", '
    '"claim_b": "string", "paper_b": "paper3", "type": "strong"|"weak"}],\n'
    '  "complementary_methods": [{"description": "string", "paper_ids": ["paper2", "paper3"]}],\n'
    '  "unique_contributions": [{"contribution": "string", "paper_id": "paper2"|"paper3"}]\n'
    '}\n\n'
    "RULES:\n"
    "  - Every item in shared_findings and complementary_methods MUST have paper_ids with at least 2 IDs.\n"
    "  - Every contradiction MUST reference paper_a and paper_b with different paper IDs.\n"
    "  - Use the EXACT paper IDs 'paper2' and 'paper3' as given below.\n"
    "  - Be precise. Only include genuine findings, not speculative connections.\n"
    "  - You MUST reference at least 2 distinct paper IDs across the entire output."
)


def _validate_synthesis(result: dict, min_papers: int = 2) -> bool:
    """Validate that synthesis output references enough distinct paper IDs."""
    all_paper_ids = set()
    for item in result.get("shared_findings", []) + result.get("complementary_methods", []):
        all_paper_ids.update(item.get("paper_ids", []))
    for item in result.get("contradictions", []):
        all_paper_ids.add(item.get("paper_a", ""))
        all_paper_ids.add(item.get("paper_b", ""))
    for item in result.get("unique_contributions", []):
        all_paper_ids.add(item.get("paper_id", ""))
    # Remove empty strings
    all_paper_ids.discard("")
    if len(all_paper_ids) < min_papers:
        return False
    return True


def synthesize_cross_paper(
    claims2: List[str], claims3: List[str], max_claims_per_paper: int = 20
) -> Optional[Dict]:
    """Use LLM to produce structured cross-paper synthesis from two claim sets.

    Validates output references at least 2 distinct paper IDs. Retries once
    with stronger instruction if validation fails.
    """
    if not has_keys():
        logger.info("No OpenAI API keys — skipping cross-paper synthesis")
        return None

    c2_block = "\n".join(f"  - {c[:250]}" for c in claims2[:max_claims_per_paper])
    c3_block = "\n".join(f"  - {c[:250]}" for c in claims3[:max_claims_per_paper])
    user_msg = f"Paper 2 (paper_id='paper2') claims:\n{c2_block}\n\nPaper 3 (paper_id='paper3') claims:\n{c3_block}"

    for attempt in range(2):
        prompt = user_msg
        system = CROSS_PAPER_SYNTHESIS_PROMPT
        if attempt == 1:
            prompt += (
                f"\n\nIMPORTANT: Your previous response only referenced {_last_paper_count} paper(s). "
                f"You MUST reference at least 2 distinct paper IDs in your output."
            )

        try:
            raw = llm_generate(
                prompt=prompt,
                system_prompt=system,
                temperature=0.3,
                max_tokens=1200,
            )
            raw = strip_code_fences(raw)
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                logger.warning("Synthesis returned non-dict: %s", type(parsed))
                return None

            if _validate_synthesis(parsed):
                logger.info(
                    "Cross-paper synthesis: %d shared, %d contradictions, %d complementary, %d unique",
                    len(parsed.get("shared_findings", [])),
                    len(parsed.get("contradictions", [])),
                    len(parsed.get("complementary_methods", [])),
                    len(parsed.get("unique_contributions", [])),
                )
                return parsed
            else:
                # Count how many papers were referenced for the retry message
                all_ids = set()
                for item in parsed.get("shared_findings", []) + parsed.get("complementary_methods", []):
                    all_ids.update(item.get("paper_ids", []))
                for item in parsed.get("contradictions", []):
                    all_ids.add(item.get("paper_a", ""))
                    all_ids.add(item.get("paper_b", ""))
                for item in parsed.get("unique_contributions", []):
                    all_ids.add(item.get("paper_id", ""))
                all_ids.discard("")
                _last_paper_count = len(all_ids)
                logger.warning(
                    "Synthesis validation failed (attempt %d): only %d paper(s) referenced",
                    attempt + 1, _last_paper_count,
                )
                if attempt == 0:
                    continue  # retry
                return parsed  # return anyway on second attempt

        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Cross-paper synthesis LLM call failed (attempt %d): %s", attempt + 1, exc)
            return None

    return None

# Module-level variable for retry message
_last_paper_count = 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    text2 = read_first_existing([str(PAPER2_PATH)])
    text3 = read_first_existing([str(PAPER3_PATH)])

    if not text2:
        logger.error("Could not extract paper2 text from %s", PAPER2_PATH)
        return
    if not text3:
        logger.error("Could not extract paper3 text from %s", PAPER3_PATH)
        return

    claims2 = extract_sectioned_claims(text2, max_claims=60)
    claims3 = extract_sectioned_claims(text3, max_claims=60)

    # LLM-powered cross-paper synthesis (best-effort)
    synthesis = synthesize_cross_paper(claims2, claims3)

    output: Dict = {"paper2": claims2, "paper3": claims3}
    if synthesis:
        output["cross_paper_synthesis"] = synthesis

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    logger.info(
        "Wrote %d paper2 claims + %d paper3 claims to %s%s",
        len(claims2), len(claims3), OUT_PATH,
        " (with synthesis)" if synthesis else "",
    )

    for label, lst in [("paper2", claims2), ("paper3", claims3)]:
        logger.info("--- Preview %s (top 3) ---", label)
        for s in lst[:3]:
            logger.info("  %s ...", s[:140])


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
