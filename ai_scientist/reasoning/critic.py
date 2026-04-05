"""ai_scientist/reasoning/critic.py — Score hypotheses with OpenAI peer-review critic."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from ai_scientist.config import OUTPUT_DIR
from ai_scientist.llm.llm_client import generate as llm_generate, has_keys, strip_code_fences

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a peer-review critic evaluating a research hypothesis. "
    "Score on three dimensions, each from 1-5:\n"
    "- Clarity (1=vague, 5=precise and specific)\n"
    "- Novelty (1=obvious, 5=genuinely new direction)\n"
    "- Feasibility (1=impossible, 5=realistic to test in a research paper)\n\n"
    "MANDATORY: You MUST identify at least one weakness or limitation in your rationale, "
    "even for strong hypotheses. A perfect score with no criticism is not acceptable.\n\n"
    "Respond ONLY with valid JSON in this exact format:\n"
    '{"clarity": N, "novelty": N, "feasibility": N, '
    '"decision": "KEEP|REVISE|REJECT", '
    '"rationale": "one sentence including at least one criticism", '
    '"weakness": "the primary weakness or limitation of this hypothesis"}\n\n'
    "Decision rules: KEEP if total >= 10, REVISE if total 6-9, REJECT if total <= 5."
)

USER_TEMPLATE = "Hypothesis: {hypothesis_text}"

DEFAULT_SCORES: Dict = {
    "clarity":     3,
    "novelty":     3,
    "feasibility": 3,
    "total":       9,
    "decision":    "REVISE",
    "rationale":   "Default scores assigned due to parse failure.",
}


# ---------------------------------------------------------------------------
# Core scorer
# ---------------------------------------------------------------------------

def _score_one(hypothesis: Dict, retrieved_evidence: Optional[List[Dict]] = None) -> Dict:
    """Call OpenAI critic and return extended hypothesis dict with scores.

    Args:
        hypothesis:         Hypothesis dict with at least 'hypothesis_text'.
        retrieved_evidence: Optional list of RAG evidence dicts for additional context.
    """
    # Build evidence block if we have RAG context
    evidence_block = ""
    if retrieved_evidence:
        lines = ["Supporting evidence from indexed papers:"]
        for i, e in enumerate(retrieved_evidence[:5], 1):
            paper = e.get("paper_id", "?")
            section = e.get("section", "?")
            text = e.get("text", "")[:200]
            lines.append(f"  [{i}] ({paper}/{section}) {text}")
        evidence_block = "\n".join(lines) + "\n\n"

    user_content = evidence_block + USER_TEMPLATE.format(
        hypothesis_text=hypothesis.get("hypothesis_text", "")
    )

    hyp_id = hypothesis.get("hypothesis_id", "?")
    logger.debug("Scoring hypothesis %s", hyp_id)

    raw_text = ""
    try:
        raw_text = llm_generate(
            prompt=user_content,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=200,
        )
        raw_text = strip_code_fences(raw_text)
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning(
            "Failed to parse critic response for %s (%s). Raw: %r. Using defaults.",
            hyp_id, exc, raw_text[:200],
        )
        parsed = {}

    clarity     = int(parsed.get("clarity",     DEFAULT_SCORES["clarity"]))
    novelty     = int(parsed.get("novelty",     DEFAULT_SCORES["novelty"]))
    feasibility = int(parsed.get("feasibility", DEFAULT_SCORES["feasibility"]))
    total       = clarity + novelty + feasibility

    # Enforce decision rules regardless of what the model returned
    if total >= 10:
        decision = "KEEP"
    elif total >= 6:
        decision = "REVISE"
    else:
        decision = "REJECT"

    return {
        **hypothesis,
        "scores": {
            "clarity":     clarity,
            "novelty":     novelty,
            "feasibility": feasibility,
            "total":       total,
        },
        "decision":  decision,
        "rationale": parsed.get("rationale", DEFAULT_SCORES["rationale"]),
        "weakness":  parsed.get("weakness", ""),
    }


def _get_rag_retriever():
    """Try to initialise RAGRetriever; return None on failure."""
    try:
        from ai_scientist.rag.document_store import DocumentStore
        from ai_scientist.rag.retriever import RAGRetriever
        from ai_scientist.config import validate_qdrant_config
        if not validate_qdrant_config():
            return None
        return RAGRetriever(DocumentStore())
    except Exception as exc:
        logger.warning("RAG retriever unavailable for critic: %s", exc)
        return None


def score_hypotheses(hypotheses: List[Dict]) -> List[Dict]:
    """
    Score all hypotheses. Returns list with added ``scores``, ``decision``,
    ``rationale`` fields. Assigns sequential H1, H2, ... IDs.
    Injects RAG evidence when Qdrant is available.
    """
    if not has_keys():
        raise EnvironmentError("No OpenAI API keys configured — cannot score hypotheses.")

    retriever = _get_rag_retriever()
    if retriever:
        logger.info("Critic RAG active — evidence will inform scoring")
    else:
        logger.info("Critic scoring without RAG evidence")

    scored: List[Dict] = []
    counter = 1
    for hyp in hypotheses:
        # Retrieve supporting evidence for each hypothesis
        evidence = None
        if retriever:
            try:
                evidence = retriever.retrieve_for_hypothesis(
                    hyp.get("hypothesis_text", ""),
                    hypothesis_id=hyp.get("hypothesis_id", ""),
                )
            except Exception as exc:
                logger.warning("RAG retrieval failed for %s: %s",
                               hyp.get("hypothesis_id", "?"), exc)

        result = _score_one(hyp, retrieved_evidence=evidence)
        result["hypothesis_id"] = f"H{counter}"
        counter += 1
        scored.append(result)

    logger.info("Scored %d hypotheses", len(scored))
    return scored


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run() -> List[Dict]:
    """Load hypotheses.json, score each, write hypotheses_scored.json."""
    hyp_path = OUTPUT_DIR / "hypotheses.json"
    if not hyp_path.exists():
        raise FileNotFoundError(f"hypotheses.json not found: {hyp_path}")

    hypotheses = json.loads(hyp_path.read_text(encoding="utf-8"))
    scored = score_hypotheses(hypotheses)

    out_path = OUTPUT_DIR / "hypotheses_scored.json"
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(scored, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(out_path))

    logger.info("Wrote %d scored hypotheses to %s", len(scored), out_path)
    return scored


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run()
