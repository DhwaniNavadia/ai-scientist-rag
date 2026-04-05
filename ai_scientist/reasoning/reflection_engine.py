"""ai_scientist/reasoning/reflection_engine.py — Generate improvement plans for KEEP hypotheses."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

from ai_scientist.config import OUTPUT_DIR
from ai_scientist.llm.llm_client import generate as llm_generate, has_keys, strip_code_fences

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a senior researcher reviewing a hypothesis and supporting evidence "
    "from related papers. Your job is to:\n"
    "1. Identify weaknesses in the hypothesis\n"
    "2. Assess whether the evidence supports or undermines it\n"
    "3. Produce a stronger, more grounded revised version\n\n"
    "Respond ONLY with valid JSON in this exact format:\n"
    '{"reflection": "...", "improvement_plan": "...", "revised_hypothesis": "...", '
    '"evidence_assessment": "...", "confidence_delta": -0.3 to +0.3}'
)

USER_TEMPLATE = (
    "Hypothesis: {hypothesis_text}\n"
    "Scores — Clarity: {clarity}/5, Novelty: {novelty}/5, Feasibility: {feasibility}/5\n"
    "Decision: {decision}\n"
    "{evidence_block}"
)

# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------

def _reflect_one(hyp: Dict, evidence: list = None) -> Dict:
    """Generate reflection for a single hypothesis, optionally with RAG evidence."""
    scores  = hyp.get("scores", {})

    # Build evidence block from RAG results
    evidence_block = ""
    if evidence:
        lines = ["\nSupporting evidence from indexed papers:"]
        for i, e in enumerate(evidence[:5], 1):
            paper = e.get("paper_id", "?")
            section = e.get("section", "?")
            text = e.get("text", "")[:250]
            lines.append(f"  [{i}] ({paper}/{section}) {text}")
        evidence_block = "\n".join(lines)

    user_msg = USER_TEMPLATE.format(
        hypothesis_text=hyp.get("hypothesis_text", ""),
        clarity=scores.get("clarity", 3),
        novelty=scores.get("novelty", 3),
        feasibility=scores.get("feasibility", 3),
        decision=hyp.get("decision", "REVISE"),
        evidence_block=evidence_block,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_msg},
    ]

    hyp_id = hyp.get("hypothesis_id", "?")
    logger.debug("Reflecting on hypothesis %s", hyp_id)

    raw_text = ""
    try:
        raw_text = llm_generate(
            prompt=user_msg,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=300,
        )
        raw_text = strip_code_fences(raw_text)
        parsed   = json.loads(raw_text)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning(
            "Failed to parse reflection for %s (%s). Raw: %r. Using fallback.",
            hyp_id, exc, raw_text[:200],
        )
        parsed = {
            "reflection":         "Unable to parse model response.",
            "improvement_plan":   "Re-run with a valid API key and stable connection.",
            "revised_hypothesis": hyp.get("hypothesis_text", ""),
        }

    return {
        "hypothesis_id":       hyp_id,
        "original_hypothesis": hyp.get("hypothesis_text", ""),
        "decision":            hyp.get("decision", "REVISE"),
        "reflection":          parsed.get("reflection", ""),
        "improvement_plan":    parsed.get("improvement_plan", ""),
        "revised_hypothesis":  parsed.get("revised_hypothesis", hyp.get("hypothesis_text", "")),
        "evidence_assessment": parsed.get("evidence_assessment", ""),
        "confidence_delta":    parsed.get("confidence_delta", 0.0),
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
        logger.warning("RAG retriever unavailable for reflections: %s", exc)
        return None


def generate_reflections(scored_hyps: List[Dict]) -> List[Dict]:
    """
    Reflect on KEEP and REVISE hypotheses (skip REJECT).
    Injects RAG evidence when available for grounded reflections.
    """
    if not has_keys():
        raise EnvironmentError("No OpenAI API keys configured — cannot generate reflections.")

    # Reflect on KEEP and REVISE (not just KEEP)
    eligible = [h for h in scored_hyps
                if h.get("decision") in ("KEEP", "REVISE")
                and "[Generation failed]" not in h.get("hypothesis_text", "")]
    logger.info("Generating reflections for %d eligible hypotheses (KEEP + REVISE)", len(eligible))

    if not eligible:
        logger.warning("No eligible hypotheses for reflection (all failed or rejected)")
        return []

    retriever = _get_rag_retriever()
    if retriever:
        logger.info("Reflection engine RAG active — evidence will inform reflections")

    reflections: List[Dict] = []
    for hyp in eligible:
        # Retrieve evidence for this hypothesis
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

        reflections.append(_reflect_one(hyp, evidence=evidence))

    logger.info("Generated %d reflections", len(reflections))
    return reflections


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run() -> List[Dict]:
    """Load hypotheses_scored.json, reflect on KEEP entries, write reflection_logs.json."""
    scored_path = OUTPUT_DIR / "hypotheses_scored.json"
    if not scored_path.exists():
        raise FileNotFoundError(f"hypotheses_scored.json not found: {scored_path}")

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    reflections = generate_reflections(scored)

    out_path = OUTPUT_DIR / "reflection_logs.json"
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(reflections, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(out_path))

    logger.info("Wrote %d reflections to %s", len(reflections), out_path)
    return reflections


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run()
