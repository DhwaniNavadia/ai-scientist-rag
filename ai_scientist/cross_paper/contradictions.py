"""
ai_scientist/cross_paper/contradictions.py
Numeric result comparator + LLM semantic contradiction detection across paper2 / paper3.

Fixes applied:
  • load_best_text() logs a WARNING when falling back to claim sentences instead of
    silently producing zero results.
  • Type hints use List/Tuple from typing for Python 3.8 compatibility.
  • FIX 8: Added detect_semantic_contradictions() and detect_all_contradictions().
"""

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from ai_scientist.config import OUTPUT_DIR, DATA_DIR
from ai_scientist.llm.llm_client import generate as llm_generate, has_keys, strip_code_fences

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLAIMS_JSON = OUTPUT_DIR / "cross_paper_claims.json"

BENCH_DATASETS: List[str] = ["cora", "citeseer", "pubmed", "ppi"]
DEFAULT_TABLE_METRIC = "accuracy"

DATASET_ALIASES: Dict[str, str] = {
    "cite seer":                    "citeseer",
    "cite-seer":                    "citeseer",
    "p p i":                        "ppi",
    "protein-protein interaction":  "ppi",
    "protein protein interaction":  "ppi",
}

ROW_BLOCKLIST: List[str] = [
    "epoch", "epochs", "early stopping", "optimizer", "adam", "sgd",
    "learning rate", "lr", "weight decay", "regularization", "l2", "lambda",
    "hidden", "features", "heads", "attention heads", "units", "layers",
    "glorot", "relu", "elu", "dropout", "batch", "minibatch", "mini-batch",
    "cross entropy", "cross-entropy", "training", "validation", "test set size",
    "table", "figure", "experimental setup", "we train", "we test", "we evaluate",
]

# ---------------------------------------------------------------------------
# Text utils
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def squeeze_letters(text: str) -> str:
    t = normalize(text)
    return re.sub(r"\b([a-z])\s+(?=[a-z]\b)", r"\1", t)


def apply_aliases(text: str) -> str:
    t = squeeze_letters(text)
    for k, v in DATASET_ALIASES.items():
        t = t.replace(k, v)
    return t


def load_claims() -> Optional[Dict]:
    if not CLAIMS_JSON.exists():
        logger.error("Missing %s — run claims_sectioned.py first", CLAIMS_JSON)
        return None
    return json.loads(CLAIMS_JSON.read_text(encoding="utf-8"))


def load_best_text(paper_key: str, claims_fallback: List[str]) -> Tuple[str, str]:
    """
    Return (text, source) for contradiction analysis.
    Logs a WARNING when falling back to claim sentences.
    """
    txt_candidates = [
        OUTPUT_DIR / f"{paper_key}.txt",
        OUTPUT_DIR / f"{paper_key}_text.txt",
        OUTPUT_DIR / f"{paper_key}_raw.txt",
        DATA_DIR   / f"{paper_key}.txt",
    ]
    for path in txt_candidates:
        if path.exists() and path.stat().st_size > 500:
            logger.info("Using text file %s for %s", path, paper_key)
            return path.read_text(encoding="utf-8", errors="ignore"), str(path)

    logger.warning(
        "[contradictions] No text file found for %s. "
        "Falling back to claim sentences — table parsing will likely find nothing. "
        "Provide %s for full analysis.",
        paper_key,
        txt_candidates[0],
    )
    return "\n".join(claims_fallback), "claims_fallback"


def split_lines(text: str) -> List[str]:
    raw = text.replace("\r", "\n").split("\n")
    return [x.strip() for x in raw if len(x.strip()) >= 5]


def detect_datasets_in_line(line: str) -> List[str]:
    t = apply_aliases(line)
    return [d for d in BENCH_DATASETS if d in t]


def is_table_like_line(line: str) -> bool:
    if "|" in line:
        return True
    if len(re.findall(r"\s{2,}", line)) >= 2:
        return True
    return False


def looks_like_table_header(line: str) -> bool:
    t = apply_aliases(line)
    ds = set(detect_datasets_in_line(t))
    if len(ds) < 2:
        return False
    if not is_table_like_line(line):
        return False
    return "method" in t or "model" in t


def header_dataset_order(line: str) -> List[str]:
    t = apply_aliases(line)
    pos = [(t.find(d), d) for d in BENCH_DATASETS if t.find(d) != -1]
    pos.sort()
    return [d for _, d in pos]


def row_has_blocklisted_context(row: str) -> bool:
    t = normalize(row)
    return any(w in t for w in ROW_BLOCKLIST)


def extract_numeric_cells(row: str) -> Tuple[List[float], str]:
    s = re.sub(r"^\s*\d+(?:\.\d+)?\s+", "", row.strip())

    pct = re.findall(r"\b\d{1,3}(?:\.\d+)?\s*%", s)
    pct_vals: List[float] = []
    for p in pct:
        try:
            v = float(p.replace("%", "").strip())
            if 0.0 <= v <= 100.0:
                pct_vals.append(v)
        except ValueError:
            pass

    if pct_vals:
        return pct_vals, "percent"

    nums = re.findall(r"\b\d+(?:\.\d+)?\b", s)
    acc_like: List[float] = []
    for n in nums:
        try:
            v = float(n)
        except ValueError:
            continue
        if 1900 <= v <= 2099 and float(v).is_integer():
            continue
        if 30.0 <= v <= 100.0:
            acc_like.append(v)
    return acc_like, "number"


# ---------------------------------------------------------------------------
# Table extraction
# ---------------------------------------------------------------------------

def extract_eval_records_from_tables(text: str, paper_key: str) -> Tuple[List[Dict], int]:
    lines = split_lines(text)
    records: List[Dict] = []
    headers_found = 0

    i = 0
    while i < len(lines):
        header = lines[i]
        if not looks_like_table_header(header):
            i += 1
            continue

        headers_found += 1
        order = header_dataset_order(header)
        if len(order) < 2:
            i += 1
            continue

        for j in range(i + 1, min(i + 35, len(lines))):
            row = lines[j]
            if looks_like_table_header(row):
                break
            if not is_table_like_line(row):
                continue
            if row_has_blocklisted_context(row):
                continue
            vals, vtype = extract_numeric_cells(row)
            if len(vals) < len(order):
                continue
            vals = vals[:len(order)]
            for d, v in zip(order, vals):
                records.append({
                    "paper":       paper_key,
                    "dataset":     d,
                    "metric":      DEFAULT_TABLE_METRIC,
                    "value":       float(v),
                    "value_type":  vtype,
                    "row":         row.strip(),
                    "header":      header.strip(),
                })
        i += 1

    # De-dup
    seen: set = set()
    unique: List[Dict] = []
    for r in records:
        key = (r["paper"], r["dataset"], r["metric"], r["value"], normalize(r["row"]))
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique, headers_found


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def match_by_dataset_metric(rec2: List[Dict], rec3: List[Dict]) -> List[Tuple[Dict, Dict]]:
    by2: Dict = defaultdict(list)
    by3: Dict = defaultdict(list)
    for r in rec2:
        by2[(r["dataset"], r["metric"])].append(r)
    for r in rec3:
        by3[(r["dataset"], r["metric"])].append(r)

    pairs: List[Tuple[Dict, Dict]] = []
    for key, L2 in by2.items():
        if key not in by3:
            continue
        for a in L2:
            for b in by3[key]:
                pairs.append((a, b))

    seen: set = set()
    unique: List[Tuple[Dict, Dict]] = []
    for a, b in pairs:
        k = (normalize(a["row"]), normalize(b["row"]), a["dataset"], a["metric"])
        if k not in seen:
            seen.add(k)
            unique.append((a, b))
    return unique


# ---------------------------------------------------------------------------
# LLM-based semantic contradiction detection (FIX 8)
# ---------------------------------------------------------------------------

CONTRADICTION_PROMPT = (
    "You are a scientific contradiction detector performing pairwise cross-paper comparison.\n\n"
    "You are given claims from Paper A and Paper B. These are DIFFERENT papers.\n"
    "Identify genuine semantic contradictions — cases where the two papers disagree on:\n"
    "  1. Empirical results (different numbers for the same experiment/dataset)\n"
    "  2. Methodological claims (conflicting statements about how something works)\n"
    "  3. Interpretive conclusions (opposing interpretations of similar evidence)\n\n"
    "RULES:\n"
    "  - Only report GENUINE contradictions, not complementary or unrelated findings.\n"
    "  - Each contradiction must cite specific claims from BOTH papers.\n"
    "  - Differences in scope (e.g. one paper studies X, another Y) are NOT contradictions.\n"
    "  - Assign severity: 'high' (directly conflicting core conclusions), "
    "'medium' (meaningful disagreement on methods or secondary findings), "
    "'low' (minor wording or framing difference).\n\n"
    "Return ONLY valid JSON: a list of objects with keys:\n"
    '  "claim_paper_a": "the specific claim from Paper A",\n'
    '  "claim_paper_b": "the conflicting claim from Paper B",\n'
    '  "contradiction_type": "empirical" | "methodological" | "interpretive",\n'
    '  "severity": "high" | "medium" | "low",\n'
    '  "evidence_a": "verbatim quote or data from Paper A supporting the claim",\n'
    '  "evidence_b": "verbatim quote or data from Paper B supporting the claim",\n'
    '  "confidence": 0.0 to 1.0,\n'
    '  "explanation": "2-3 sentences explaining why these claims contradict"\n\n'
    "If no genuine contradictions exist, return []."
)


def detect_semantic_contradictions(
    claims2: List[str], claims3: List[str]
) -> List[Dict]:
    """Use LLM to detect semantic contradictions between two sets of claims.

    Includes same-paper guard: if both claim lists are identical, skip detection.
    """
    if not has_keys():
        logger.info("No OpenAI API keys — skipping semantic contradiction detection")
        return []

    # Same-paper guard: skip if claim sets are identical
    if set(c.strip().lower() for c in claims2) == set(c.strip().lower() for c in claims3):
        logger.info("Same-paper guard triggered — claim sets are identical, skipping")
        return []

    # Truncate claims to avoid token limits
    c2_text = "\n".join(f"- {c[:250]}" for c in claims2[:15])
    c3_text = "\n".join(f"- {c[:250]}" for c in claims3[:15])
    user_msg = f"Paper A claims:\n{c2_text}\n\nPaper B claims:\n{c3_text}"

    try:
        raw = llm_generate(
            prompt=user_msg,
            system_prompt=CONTRADICTION_PROMPT,
            temperature=0.3,
            max_tokens=1000,
        )
        raw = strip_code_fences(raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            results = []
            for item in parsed:
                if isinstance(item, dict) and "explanation" in item:
                    # Normalise legacy severity values
                    raw_sev = item.get("severity", "medium")
                    sev_map = {"minor": "low", "moderate": "medium", "major": "high"}
                    severity = sev_map.get(raw_sev, raw_sev)
                    results.append({
                        "type": "semantic",
                        "claim_paper2": item.get("claim_paper_a", item.get("claim_paper2", "")),
                        "claim_paper3": item.get("claim_paper_b", item.get("claim_paper3", "")),
                        "contradiction_type": item.get("contradiction_type", "unknown"),
                        "severity": severity,
                        "evidence_a": item.get("evidence_a", ""),
                        "evidence_b": item.get("evidence_b", ""),
                        "confidence": float(item.get("confidence", 0.5)),
                        "explanation": item.get("explanation", ""),
                        "potential_contradiction": True,
                    })
            logger.info("LLM found %d semantic contradictions", len(results))
            return results
        return []
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("LLM contradiction detection failed: %s", exc)
        return []


def detect_all_contradictions(
    numeric_contradictions: List[Dict],
    claims2: List[str],
    claims3: List[str],
) -> List[Dict]:
    """Combine numeric table-based and LLM semantic contradictions."""
    semantic = detect_semantic_contradictions(claims2, claims3)

    # Tag numeric contradictions
    for item in numeric_contradictions:
        item["type"] = item.get("type", "numeric")

    combined = numeric_contradictions + semantic
    logger.info(
        "Total contradictions: %d (numeric=%d, semantic=%d)",
        len(combined), len(numeric_contradictions), len(semantic),
    )
    return combined


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    claims = load_claims()
    if claims is None:
        return

    raw2: List[str] = claims.get("paper2", [])
    raw3: List[str] = claims.get("paper3", [])

    text2, src2 = load_best_text("paper2", raw2)
    text3, src3 = load_best_text("paper3", raw3)

    rec2, h2 = extract_eval_records_from_tables(text2, "paper2")
    rec3, h3 = extract_eval_records_from_tables(text3, "paper3")

    logger.info("Raw claims → paper2: %d | paper3: %d", len(raw2), len(raw3))
    logger.info("Text sources → paper2: %s | paper3: %s", src2, src3)
    logger.info("Table headers → paper2: %d | paper3: %d", h2, h3)
    logger.info("Eval records (strict table) → paper2: %d | paper3: %d", len(rec2), len(rec3))

    out_path = OUTPUT_DIR / "cross_paper_contradictions.json"

    if len(rec2) == 0 or len(rec3) == 0:
        logger.warning(
            "Zero strict table eval records on at least one side. "
            "Result tables are probably not in clean text format. "
            "Attempting LLM semantic contradictions only."
        )
        numeric_out = []
    else:
        pairs = match_by_dataset_metric(rec2, rec3)
        numeric_out: List[Dict] = []
        for a, b in pairs:
            d = float(a["value"]) - float(b["value"])
            flag = abs(d) >= 1.0

            numeric_out.append({
                "dataset":                 a["dataset"],
                "metric":                  a["metric"],
                "paper2_value":            a["value"],
                "paper3_value":            b["value"],
                "delta_p2_minus_p3":       round(d, 4),
                "potential_contradiction": flag,
                "reason":                  f"Δ={d:.4f} (threshold=1.0)",
                "paper2_header":           a["header"],
                "paper2_row":              a["row"],
                "paper3_header":           b["header"],
                "paper3_row":              b["row"],
            })

        numeric_out.sort(key=lambda r: (not r["potential_contradiction"], -abs(r["delta_p2_minus_p3"])))

    # FIX 8: Combine numeric + semantic (LLM) contradictions
    out = detect_all_contradictions(numeric_out, raw2, raw3)

    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    logger.info("Saved %d contradiction entries to %s", len(out), out_path)

    for r in out[:5]:
        tag = "FLAG" if r["potential_contradiction"] else "OK"
        logger.info(
            "%s | %s | p2=%.2f | p3=%.2f | %s",
            tag, r["dataset"], r["paper2_value"], r["paper3_value"], r["reason"],
        )


# ---------------------------------------------------------------------------
# Qdrant-powered cross-paper contradiction detection (NEW)
# ---------------------------------------------------------------------------

QDRANT_CONTRADICTION_PROMPT = (
    "You are a scientific claim comparator. You are given text chunks from "
    "DIFFERENT research papers retrieved from a vector database. Identify any "
    "contradictions, disagreements, or conflicting findings between these papers.\n\n"
    "Focus on:\n"
    "- Conflicting empirical results or conclusions\n"
    "- Contradictory methodological claims\n"
    "- Disagreements about the effectiveness of approaches\n"
    "- Opposing interpretations of similar evidence\n\n"
    "IMPORTANT: paper_a and paper_b MUST be different papers. Never report a\n"
    "contradiction within the same paper.\n\n"
    "Return ONLY valid JSON: a list of objects with keys:\n"
    '  "paper_a" (paper_id of first paper),\n'
    '  "paper_b" (paper_id of second paper — MUST differ from paper_a),\n'
    '  "claim_a" (the claim or finding from paper_a),\n'
    '  "claim_b" (the conflicting claim from paper_b),\n'
    '  "contradiction_type" (one of: "methodological", "empirical", "interpretive"),\n'
    '  "severity" (one of: "high", "medium", "low"),\n'
    '  "evidence_a" (verbatim quote or data from paper_a),\n'
    '  "evidence_b" (verbatim quote or data from paper_b),\n'
    '  "confidence" (0.0 to 1.0),\n'
    '  "explanation" (2-3 sentences explaining the contradiction and why it matters).\n\n'
    "If no genuine contradictions exist, return []. Do NOT fabricate contradictions."
)


def detect_qdrant_contradictions(
    queries: Optional[List[str]] = None,
    top_k: int = 10,
) -> List[Dict]:
    """
    Use RAG retrieval + LLM to detect contradictions across all indexed papers.
    Retrieves diverse chunks, groups by paper, and asks LLM to find conflicts.
    """
    if not has_keys():
        logger.info("No OpenAI API keys — skipping Qdrant contradiction detection")
        return []

    try:
        from ai_scientist.rag.document_store import DocumentStore
        from ai_scientist.rag.retriever import RAGRetriever
        from ai_scientist.config import validate_qdrant_config
        if not validate_qdrant_config():
            logger.warning("Qdrant not configured — skipping Qdrant contradictions")
            return []
        store = DocumentStore()
        retriever = RAGRetriever(store)
    except Exception as exc:
        logger.warning("Failed to init RAG for contradictions: %s", exc)
        return []

    if queries is None:
        queries = [
            "model performance results accuracy improvements",
            "limitations and challenges of the proposed approach",
            "comparison with baseline methods and state of the art",
            "scalability efficiency computational cost",
            "key contributions and novel findings",
        ]

    # Collect chunks from multiple queries, ensuring paper diversity
    all_chunks: List[Dict] = []
    seen_keys: set = set()
    for query in queries:
        try:
            results = retriever.retrieve(query, top_k=top_k)
            for r in results:
                key = f"{r.get('paper_id','')}_{r.get('section','')}_{r.get('chunk_index','')}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_chunks.append(r)
        except Exception as exc:
            logger.warning("RAG retrieval failed for query '%s': %s", query[:50], exc)

    # Group by paper
    by_paper: Dict[str, List[Dict]] = defaultdict(list)
    for chunk in all_chunks:
        by_paper[chunk.get("paper_id", "unknown")].append(chunk)

    paper_ids = list(by_paper.keys())
    logger.info("Retrieved chunks from %d papers for contradiction analysis: %s",
                len(paper_ids), paper_ids)

    if len(paper_ids) < 2:
        logger.warning("Need at least 2 papers for cross-paper contradictions, got %d", len(paper_ids))
        return []

    # Build context: top chunks per paper
    context_parts = []
    for pid in paper_ids:
        chunks = by_paper[pid][:5]  # Max 5 chunks per paper
        title = chunks[0].get("title", pid) if chunks else pid
        context_parts.append(f"\n=== Paper: {pid} ({title}) ===")
        for i, c in enumerate(chunks, 1):
            sec = c.get("section", "?")
            text = c.get("text", "")[:400]
            context_parts.append(f"  [{i}] ({sec}) {text}")

    user_msg = "\n".join(context_parts)

    try:
        raw = llm_generate(
            prompt=user_msg,
            system_prompt=QDRANT_CONTRADICTION_PROMPT,
            temperature=0.3,
            max_tokens=1200,
        )
        raw = strip_code_fences(raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            results = []
            skipped_same_paper = 0
            for item in parsed:
                if isinstance(item, dict) and "explanation" in item:
                    pa = item.get("paper_a", "")
                    pb = item.get("paper_b", "")
                    # Cross-paper guard: reject same-paper "contradictions"
                    if pa and pb and pa == pb:
                        skipped_same_paper += 1
                        continue
                    # Normalise legacy severity values
                    raw_sev = item.get("severity", "medium")
                    sev_map = {"minor": "low", "moderate": "medium", "major": "high"}
                    severity = sev_map.get(raw_sev, raw_sev)
                    results.append({
                        "type": "semantic_qdrant",
                        "paper_a": pa,
                        "paper_b": pb,
                        "claim_a": item.get("claim_a", ""),
                        "claim_b": item.get("claim_b", ""),
                        "contradiction_type": item.get("contradiction_type", "unknown"),
                        "severity": severity,
                        "evidence_a": item.get("evidence_a", ""),
                        "evidence_b": item.get("evidence_b", ""),
                        "confidence": float(item.get("confidence", 0.5)),
                        "explanation": item.get("explanation", ""),
                        "potential_contradiction": True,
                    })
            if skipped_same_paper:
                logger.info("Cross-paper guard: skipped %d same-paper pairs", skipped_same_paper)
            logger.info("Qdrant LLM found %d cross-paper contradictions", len(results))
            return results
        return []
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("LLM contradiction detection failed: %s", exc)
        return []


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
