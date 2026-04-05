"""ai_scientist/evaluation/metrics.py — Automated quality metrics for pipeline outputs.

Provides:
  - retrieval_precision_at_k: measures how many RAG-retrieved chunks are relevant
  - paper_diversity_score: measures how diverse retrieved evidence is across papers
  - hypothesis_quality_score: aggregates critic scores into a single quality metric
  - run_evaluation: orchestrates all metrics and writes evaluation_metrics.json
"""

import json
import logging
import math
import os
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)

from ai_scientist.config import OUTPUT_DIR
from ai_scientist.llm.llm_client import generate as llm_generate, has_keys, strip_code_fences


# ---------------------------------------------------------------------------
# Retrieval precision @ K
# ---------------------------------------------------------------------------

def retrieval_precision_at_k(
    retrieved_chunks: List[Dict],
    relevant_keywords: List[str],
    k: int = 5,
) -> float:
    """
    Estimate retrieval precision at K by checking whether retrieved chunks
    contain at least one of the *relevant_keywords*.

    This is a proxy metric: true relevance requires human judgment, but
    keyword overlap is a reasonable automated approximation.

    Args:
        retrieved_chunks: list of dicts with at least a "text" key
        relevant_keywords: list of keywords that indicate relevance
        k: top-K cutoff

    Returns:
        Precision@K in [0.0, 1.0]
    """
    if not retrieved_chunks or k <= 0:
        return 0.0

    top_k = retrieved_chunks[:k]
    keywords_lower = [kw.lower() for kw in relevant_keywords if kw.strip()]

    if not keywords_lower:
        return None  # Cannot evaluate without relevance criteria

    hits = 0
    for chunk in top_k:
        text = chunk.get("text", "").lower()
        if any(kw in text for kw in keywords_lower):
            hits += 1

    return hits / len(top_k)


# ---------------------------------------------------------------------------
# Paper diversity score
# ---------------------------------------------------------------------------

def paper_diversity_score(retrieved_chunks: List[Dict]) -> float:
    """
    Compute how diverse retrieved evidence is across different papers.

    Uses normalised entropy: 1.0 = perfectly even across N papers,
    0.0 = all from one paper.

    Args:
        retrieved_chunks: list of dicts with a "paper_id" key

    Returns:
        Diversity score in [0.0, 1.0]
    """
    if not retrieved_chunks:
        return {"score": 0.0, "n_papers": 0, "max_fraction": 1.0, "is_diverse": False}

    paper_ids = [c.get("paper_id", "unknown") for c in retrieved_chunks]
    counts = Counter(paper_ids)
    n_papers = len(counts)
    total = sum(counts.values())
    max_fraction = max(counts.values()) / total if total > 0 else 1.0

    if n_papers <= 1:
        return {"score": 0.0, "n_papers": n_papers, "max_fraction": max_fraction, "is_diverse": False}

    # Shannon entropy
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)
    # Normalise by max entropy (uniform distribution over n_papers)
    max_entropy = math.log2(n_papers)
    score = entropy / max_entropy if max_entropy > 0 else 0.0

    # Diversity requires at least 2 papers AND no single paper dominates >60%
    is_diverse = n_papers >= 2 and max_fraction <= 0.6

    return {"score": score, "n_papers": n_papers, "max_fraction": round(max_fraction, 3), "is_diverse": is_diverse}


# ---------------------------------------------------------------------------
# Hypothesis quality score
# ---------------------------------------------------------------------------

# LLM prompt for hypothesis quality assessment
_HYP_QUALITY_PROMPT = (
    "You are a research methodology expert. Rate this hypothesis on three dimensions.\n\n"
    "Respond ONLY with valid JSON:\n"
    '{"specificity": 1-10, "novelty": 1-10, "testability": 1-10, '
    '"justification": "one sentence explaining the scores"}'
)


def _llm_assess_hypothesis(hypothesis_text: str) -> Optional[Dict]:
    """Use LLM to assess a single hypothesis on specificity/novelty/testability."""
    if not has_keys() or not hypothesis_text or "[Generation failed]" in hypothesis_text:
        return None
    try:
        raw = llm_generate(
            prompt=f"Hypothesis: {hypothesis_text[:500]}",
            system_prompt=_HYP_QUALITY_PROMPT,
            temperature=0.3,
            max_tokens=150,
        )
        raw = strip_code_fences(raw)
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "specificity" in parsed:
            return parsed
        return None
    except Exception as exc:
        logger.warning("LLM hypothesis assessment failed: %s", exc)
        return None


def hypothesis_quality_score(scored_hypotheses: List[Dict]) -> Dict[str, Union[float, List]]:
    """
    Aggregate critic scores across all hypotheses, plus LLM-based
    specificity/novelty/testability assessment.

    Returns:
        Dict with:
            avg_total, avg_clarity, avg_novelty, avg_feasibility,
            keep_rate, reject_rate,
            llm_assessments: list of per-hypothesis LLM ratings (if keys available)
    """
    if not scored_hypotheses:
        return {
            "avg_total": 0.0, "avg_clarity": 0.0, "avg_novelty": 0.0,
            "avg_feasibility": 0.0, "keep_rate": 0.0, "reject_rate": 0.0,
            "llm_assessments": [],
        }

    totals = []
    clarities = []
    novelties = []
    feasibilities = []
    decisions = []

    for hyp in scored_hypotheses:
        scores = hyp.get("scores", {})
        c = scores.get("clarity", 0)
        n = scores.get("novelty", 0)
        f = scores.get("feasibility", 0)
        clarities.append(c)
        novelties.append(n)
        feasibilities.append(f)
        totals.append(scores.get("total", c + n + f))
        decisions.append(hyp.get("decision", "REVISE"))

    count = len(scored_hypotheses)

    # LLM-based quality assessment (sample up to 5 hypotheses)
    llm_assessments = []
    for hyp in scored_hypotheses[:5]:
        hyp_text = hyp.get("hypothesis_text", hyp.get("hypothesis", ""))
        assessment = _llm_assess_hypothesis(hyp_text)
        if assessment:
            llm_assessments.append({
                "hypothesis_id": hyp.get("hypothesis_id", ""),
                "specificity": assessment.get("specificity", 0),
                "novelty": assessment.get("novelty", 0),
                "testability": assessment.get("testability", 0),
                "justification": assessment.get("justification", ""),
            })

    return {
        "avg_total": sum(totals) / count,
        "avg_clarity": sum(clarities) / count,
        "avg_novelty": sum(novelties) / count,
        "avg_feasibility": sum(feasibilities) / count,
        "keep_rate": sum(1 for d in decisions if d == "KEEP") / count,
        "reject_rate": sum(1 for d in decisions if d == "REJECT") / count,
        "llm_assessments": llm_assessments,
    }


# ---------------------------------------------------------------------------
# Debate quality metrics
# ---------------------------------------------------------------------------

def debate_quality_score(disagreement_log: List[Dict]) -> Dict[str, Union[float, int]]:
    """
    Compute debate-related quality metrics based on 3-round structure.

    Scoring: each non-empty round contributes ~3.33 points (max 10).
    Bonus +1 if challenge round cites evidence (contains quote markers).

    Returns:
        agreement_rate, avg_confidence, challenge_rate,
        avg_round_score, rounds_with_all_3
    """
    if not disagreement_log:
        return {
            "agreement_rate": 0.0, "avg_confidence": 0.0, "challenge_rate": 0.0,
            "avg_round_score": 0.0, "rounds_with_all_3": 0,
        }

    count = len(disagreement_log)
    agreements = sum(1 for e in disagreement_log if e.get("agreement", False))
    confidences = [e.get("confidence", 0.0) for e in disagreement_log]
    challenges = sum(1 for e in disagreement_log if e.get("challenge") is not None)
    rounds_with_all_3 = 0
    round_scores = []

    for entry in disagreement_log:
        score = 0.0
        r1 = entry.get("round_1")
        r2 = entry.get("round_2")
        r3 = entry.get("round_3")

        if r1 and r1.get("reasoning"):
            score += 3.33
        if r2 and r2.get("response", r2.get("action")):
            score += 3.33
            # Bonus for evidence citations in challenges
            resp = r2.get("response", "")
            if any(marker in resp for marker in ['"', "'", "showed", "found", "reported", "%"]):
                score += 1.0
        if r3 and r3.get("decisive_factor"):
            score += 3.33

        if r1 and r2 and r3:
            rounds_with_all_3 += 1

        round_scores.append(min(score, 10.0))

    return {
        "agreement_rate": agreements / count,
        "avg_confidence": sum(confidences) / count,
        "challenge_rate": challenges / count,
        "avg_round_score": round(sum(round_scores) / count, 2),
        "rounds_with_all_3": rounds_with_all_3,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_evaluation(output_dir: Optional[Path] = None, paper_id: Optional[str] = None) -> Dict:
    """
    Load pipeline outputs, compute all metrics, write evaluation_metrics.json.

    If *paper_id* is given, also writes outputs/{paper_id}/eval_metrics.json.

    Returns the full metrics dict.
    """
    out_dir = output_dir or OUTPUT_DIR

    metrics: Dict = {
        "hypothesis_quality": {},
        "debate_quality": {},
        "claim_count": 0,
        "gap_count": 0,
    }

    # Hypothesis quality
    scored_path = out_dir / "hypotheses_scored.json"
    if scored_path.exists():
        scored = json.loads(scored_path.read_text(encoding="utf-8"))
        metrics["hypothesis_quality"] = hypothesis_quality_score(scored)
        logger.info("Hypothesis quality: %s", metrics["hypothesis_quality"])

    # Debate quality
    debate_path = out_dir / "disagreement_log_all.json"
    if debate_path.exists():
        debate_log = json.loads(debate_path.read_text(encoding="utf-8"))
        metrics["debate_quality"] = debate_quality_score(debate_log)
        logger.info("Debate quality: %s", metrics["debate_quality"])

    # Counts
    claims_path = out_dir / "claims.json"
    if claims_path.exists():
        claims = json.loads(claims_path.read_text(encoding="utf-8"))
        metrics["claim_count"] = len(claims) if isinstance(claims, list) else 0

    gaps_path = out_dir / "gaps_actionable.json"
    if gaps_path.exists():
        gaps = json.loads(gaps_path.read_text(encoding="utf-8"))
        metrics["gap_count"] = len(gaps) if isinstance(gaps, list) else 0

    # Write to default location
    out_path = out_dir / "evaluation_metrics.json"
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(out_path))
    logger.info("Wrote evaluation metrics to %s", out_path)

    # Write to paper-specific directory if paper_id provided
    if paper_id:
        paper_dir = out_dir / paper_id
        paper_dir.mkdir(parents=True, exist_ok=True)
        paper_path = paper_dir / "eval_metrics.json"
        ptmp = paper_path.with_suffix(".tmp")
        ptmp.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        os.replace(str(ptmp), str(paper_path))
        logger.info("Wrote paper-specific eval metrics to %s", paper_path)

    return metrics


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_evaluation()
