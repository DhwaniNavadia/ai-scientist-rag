"""ai_scientist/reasoning/hypothesis_generator.py — Generate hypotheses via OpenAI."""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from ai_scientist.config import OUTPUT_DIR
from ai_scientist.llm.llm_client import generate as llm_generate, has_keys, strip_code_fences


# ---------------------------------------------------------------------------
# Hypothesis dataclass
# ---------------------------------------------------------------------------

@dataclass
class Hypothesis:
    hypothesis_id: str
    gap_id: str
    gap_type: str
    gap_text: str
    actionable_direction: str
    hypothesis_text: str
    source: str  # "AgentA" or "AgentB"
    based_on: List[str] = field(default_factory=list)
    novelty_score: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

AGENT_A_SYSTEM_PROMPT = (
    "You are a conservative research scientist (Agent A). Given a research gap "
    "and optional supporting evidence from indexed papers, propose one specific, "
    "testable hypothesis grounded in existing literature. Prefer incremental "
    "improvements and methodologically sound ideas.\n\n"
    "Respond ONLY with valid JSON:\n"
    '{"hypothesis": "your hypothesis (2-3 sentences)",\n'
    ' "based_on": ["key paper/finding 1", "key paper/finding 2"],\n'
    ' "novelty_score": 0.0-1.0,\n'
    ' "confidence": 0.0-1.0}'
)

AGENT_B_SYSTEM_PROMPT = (
    "You are an exploratory research scientist (Agent B). Given a research gap "
    "and optional supporting evidence from indexed papers, propose one bold, "
    "creative hypothesis that challenges assumptions or combines ideas from "
    "different sub-fields. Prioritise novelty over safety.\n\n"
    "Respond ONLY with valid JSON:\n"
    '{"hypothesis": "your hypothesis (2-3 sentences)",\n'
    ' "based_on": ["key paper/finding 1", "key paper/finding 2"],\n'
    ' "novelty_score": 0.0-1.0,\n'
    ' "confidence": 0.0-1.0}'
)

USER_TEMPLATE = (
    "Research gap: {gap_text}\n"
    "Actionable direction: {actionable_direction}\n"
    "Gap type: {gap_type}\n"
    "{rag_context}\n"
    "Propose a hypothesis."
)


# ---------------------------------------------------------------------------
# RAG helper
# ---------------------------------------------------------------------------

def _get_rag_retriever():
    """Try to initialise RAGRetriever; return None on failure (graceful degradation)."""
    try:
        from ai_scientist.rag.document_store import DocumentStore
        from ai_scientist.rag.retriever import RAGRetriever
        store = DocumentStore()
        # Test connectivity lazily — only if Qdrant is configured
        from ai_scientist.config import validate_qdrant_config
        if not validate_qdrant_config():
            return None
        return RAGRetriever(store)
    except Exception as exc:
        logger.warning("RAG retriever unavailable, proceeding without: %s", exc)
        return None


def _format_rag_context(evidence: List[Dict]) -> str:
    """Format retrieved evidence into a prompt block."""
    if not evidence:
        return ""
    lines = ["\nRelevant evidence from indexed papers:"]
    for i, e in enumerate(evidence[:5], 1):
        paper = e.get("paper_id", "?")
        section = e.get("section", "?")
        score = e.get("score", 0)
        text = e.get("text", "")[:300]
        lines.append(f"  [{i}] ({paper}/{section}, score={score:.2f}) {text}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def _generate_for_agent(gap: Dict, agent: str, temperature: float,
                        rag_evidence: Optional[List[Dict]] = None) -> Dict:
    """Generate one hypothesis for *agent* from *gap*. Returns Hypothesis.to_dict()."""
    rag_context = _format_rag_context(rag_evidence) if rag_evidence else ""

    user_msg = USER_TEMPLATE.format(
        gap_text=gap.get("gap_text", ""),
        actionable_direction=gap.get("actionable_direction", ""),
        gap_type=gap.get("gap_type", ""),
        rag_context=rag_context,
    )

    system_prompt = AGENT_A_SYSTEM_PROMPT if agent == "AgentA" else AGENT_B_SYSTEM_PROMPT

    gap_id = gap.get("gap_id", "?")
    logger.debug("Generating hypothesis for gap %s as %s", gap_id, agent)

    raw_text = llm_generate(
        prompt=user_msg,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=300,
    )

    # Parse JSON response; fall back to raw text if parse fails
    hypothesis_text = raw_text.strip()
    based_on: List[str] = []
    novelty_score = 0.0
    confidence = 0.0

    try:
        cleaned = strip_code_fences(raw_text)
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            hypothesis_text = parsed.get("hypothesis", hypothesis_text)
            based_on = parsed.get("based_on", [])
            if not isinstance(based_on, list):
                based_on = []
            novelty_score = float(parsed.get("novelty_score", 0.0))
            confidence = float(parsed.get("confidence", 0.0))
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.debug("Hypothesis JSON parse failed for gap %s / %s, using raw text", gap_id, agent)

    agent_tag = "A" if agent == "AgentA" else "B"
    hyp_id = f"H{agent_tag}_{gap_id}"

    hyp = Hypothesis(
        hypothesis_id=hyp_id,
        gap_id=gap_id,
        gap_type=gap.get("gap_type", ""),
        gap_text=gap.get("gap_text", ""),
        actionable_direction=gap.get("actionable_direction", ""),
        hypothesis_text=hypothesis_text,
        source=agent,
        based_on=based_on,
        novelty_score=novelty_score,
        confidence=confidence,
    )
    return hyp.to_dict()


def generate_hypotheses(gaps: List[Dict]) -> List[Dict]:
    """
    For each gap generate two hypotheses:
      AgentA (conservative) @ temp=0.4
      AgentB (exploratory)  @ temp=0.9
    Injects RAG evidence when Qdrant is available.
    Returns flat list of all raw hypotheses.
    """
    if not has_keys():
        raise EnvironmentError("No OpenAI API keys configured — cannot generate hypotheses.")

    # FIX 2B: Try to initialise RAG retriever (graceful degradation)
    retriever = _get_rag_retriever()
    if retriever:
        logger.info("RAG retriever active — evidence will be injected into prompts")
    else:
        logger.info("RAG retriever unavailable — generating hypotheses without evidence")

    hypotheses: List[Dict] = []
    for gap in gaps:
        gap_id = gap.get("gap_id", "?")
        logger.info("Generating hypotheses for gap %s", gap_id)

        # Retrieve evidence for this gap (if RAG available)
        rag_evidence = None
        if retriever:
            try:
                rag_evidence = retriever.retrieve_for_gap(
                    gap.get("gap_text", ""), gap_id=gap_id
                )
            except Exception as exc:
                logger.warning("RAG retrieval failed for gap %s: %s", gap_id, exc)

        # FIX 10: Differentiated temperatures
        for agent, temp in [("AgentA", 0.4), ("AgentB", 0.9)]:
            hyp = _generate_for_agent(gap, agent, temp, rag_evidence=rag_evidence)
            hypotheses.append(hyp)

    logger.info("Generated %d raw hypotheses", len(hypotheses))
    return hypotheses


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run() -> List[Dict]:
    """Load gaps_actionable.json, generate hypotheses, write hypotheses.json."""
    gaps_path = OUTPUT_DIR / "gaps_actionable.json"
    if not gaps_path.exists():
        raise FileNotFoundError(f"gaps_actionable.json not found: {gaps_path}")

    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))
    hypotheses = generate_hypotheses(gaps)

    out_path = OUTPUT_DIR / "hypotheses.json"
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(hypotheses, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(out_path))

    logger.info("Wrote %d hypotheses to %s", len(hypotheses), out_path)
    return hypotheses


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run()
