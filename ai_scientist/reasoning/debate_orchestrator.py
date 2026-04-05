"""ai_scientist/reasoning/debate_orchestrator.py — Build AgentA vs AgentB disagreement log."""

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from ai_scientist.config import OUTPUT_DIR
from ai_scientist.llm.llm_client import generate as llm_generate, has_keys, strip_code_fences

# ---------------------------------------------------------------------------
# Preference logic (shared with assembler)
# ---------------------------------------------------------------------------

def _decision_rank(decision: str) -> int:
    """Higher is better: KEEP=3, REVISE=2, REJECT=1."""
    return {"KEEP": 3, "REVISE": 2}.get(decision, 1)


def pick_preferred(agent_a: Dict, agent_b: Dict) -> str:
    """
    Choose the better agent based on:
      1. Decision rank (KEEP > REVISE > REJECT)
      2. Total score
      3. Tie-break → AgentA
    """
    ra = _decision_rank(agent_a.get("decision", "REJECT"))
    rb = _decision_rank(agent_b.get("decision", "REJECT"))

    if ra > rb:
        return "AgentA"
    if rb > ra:
        return "AgentB"

    ta = agent_a.get("scores", {}).get("total", 0)
    tb = agent_b.get("scores", {}).get("total", 0)

    if ta > tb:
        return "AgentA"
    if tb > ta:
        return "AgentB"

    return "AgentA"


# ---------------------------------------------------------------------------
# LLM-powered comparative reasoning (NEW)
# ---------------------------------------------------------------------------

DEBATE_SYSTEM_PROMPT = (
    "You are a senior research advisor adjudicating between two hypotheses proposed "
    "by different research agents for the same research gap. Compare them critically.\n\n"
    "Respond ONLY with valid JSON:\n"
    '{"preferred": "AgentA" or "AgentB",\n'
    ' "reasoning": "2-3 sentences comparing strengths/weaknesses of each hypothesis",\n'
    ' "synthesis": "1-2 sentences describing how the best elements of both could be combined",\n'
    ' "confidence": 0.0-1.0}'
)


def _llm_compare(gap_text: str, hyp_a: str, hyp_b: str) -> Optional[Dict]:
    """Use LLM to do real comparative reasoning between two hypotheses."""
    if not has_keys():
        return None

    user_msg = (
        f"Research gap: {gap_text[:500]}\n\n"
        f"AgentA hypothesis: {hyp_a[:400]}\n\n"
        f"AgentB hypothesis: {hyp_b[:400]}"
    )

    try:
        raw = llm_generate(
            prompt=user_msg,
            system_prompt=DEBATE_SYSTEM_PROMPT,
            temperature=0.4,
            max_tokens=300,
        )
        raw = strip_code_fences(raw)
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Debate LLM parse/call failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Challenge round — agents respond to each other's reasoning
# ---------------------------------------------------------------------------

CHALLENGE_SYSTEM_PROMPT = (
    "You are a research scientist defending your hypothesis against a critique.\n"
    "You proposed a hypothesis for a research gap. Another agent proposed a different one "
    "and an advisor has compared them.\n\n"
    "Respond to the advisor's critique. Either:\n"
    "  1. DEFEND your hypothesis by addressing the weakness identified\n"
    "  2. CONCEDE if the other hypothesis is genuinely stronger, explaining why\n"
    "  3. REFINE your hypothesis to address the critique while keeping its core insight\n\n"
    "Respond ONLY with valid JSON:\n"
    '{"action": "DEFEND" | "CONCEDE" | "REFINE",\n'
    ' "response": "2-3 sentences addressing the critique",\n'
    ' "refined_hypothesis": "only if action=REFINE, otherwise empty string"}'
)


def _challenge_round(
    gap_text: str,
    hyp_a: str,
    hyp_b: str,
    advisor_reasoning: str,
    advisor_preferred: str,
) -> Optional[Dict]:
    """Run a challenge round where the non-preferred agent responds to the critique."""
    if not has_keys():
        return None

    # The non-preferred agent gets to respond
    challenger = "AgentA" if advisor_preferred == "AgentB" else "AgentB"
    challenger_hyp = hyp_a if challenger == "AgentA" else hyp_b
    other_hyp = hyp_b if challenger == "AgentA" else hyp_a

    user_msg = (
        f"Research gap: {gap_text[:400]}\n\n"
        f"Your hypothesis: {challenger_hyp[:400]}\n\n"
        f"Other agent's hypothesis: {other_hyp[:400]}\n\n"
        f"Advisor's reasoning: {advisor_reasoning[:400]}\n"
        f"Advisor's preference: {advisor_preferred}"
    )

    try:
        raw = llm_generate(
            prompt=user_msg,
            system_prompt=CHALLENGE_SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=300,
        )
        raw = strip_code_fences(raw)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed["challenger"] = challenger
            return parsed
        return None
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Challenge round LLM failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Round 3 — Synthesis verdict
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = (
    "You are a senior research advisor delivering a final verdict after a 3-round debate "
    "between two research agents.\n\n"
    "Round 1: You compared both hypotheses and stated your initial preference.\n"
    "Round 2: The non-preferred agent challenged your reasoning.\n"
    "Now deliver your FINAL verdict considering ALL evidence.\n\n"
    "Respond ONLY with valid JSON:\n"
    '{"final_preferred": "AgentA" or "AgentB",\n'
    ' "verdict": "2-3 sentences summarising the final decision",\n'
    ' "decisive_factor": "the single most important reason for this choice (MUST NOT be empty)",\n'
    ' "confidence": 0.0-1.0,\n'
    ' "recommendation": "ACCEPT" | "REVISE" | "MERGE"}'
)


def _synthesis_round(
    gap_text: str,
    hyp_a: str,
    hyp_b: str,
    round1_reasoning: str,
    round1_preferred: str,
    challenge: Optional[Dict],
) -> Optional[Dict]:
    """Round 3: final verdict after considering the challenge."""
    if not has_keys():
        return None

    challenge_text = "No challenge was made."
    if challenge:
        action = challenge.get("action", "?")
        resp = challenge.get("response", "")
        refined = challenge.get("refined_hypothesis", "")
        challenger = challenge.get("challenger", "?")
        challenge_text = (
            f"{challenger} responded with action={action}: {resp[:300]}"
        )
        if refined:
            challenge_text += f"\nRefined hypothesis: {refined[:200]}"

    user_msg = (
        f"Research gap: {gap_text[:400]}\n\n"
        f"AgentA hypothesis: {hyp_a[:300]}\n"
        f"AgentB hypothesis: {hyp_b[:300]}\n\n"
        f"Round 1 reasoning: {round1_reasoning[:300]}\n"
        f"Round 1 preferred: {round1_preferred}\n\n"
        f"Round 2 challenge: {challenge_text[:400]}"
    )

    try:
        raw = llm_generate(
            prompt=user_msg,
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=300,
        )
        raw = strip_code_fences(raw)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            # Ensure decisive_factor is never empty
            if not parsed.get("decisive_factor", "").strip():
                parsed["decisive_factor"] = "Score-based preference after inconclusive debate"
            return parsed
        return None
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Synthesis round LLM failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Core orchestrator
# ---------------------------------------------------------------------------

def build_disagreement_log(scored_hyps: List[Dict]) -> List[Dict]:
    """
    Group *scored_hyps* (two per gap: AgentA + AgentB) into one entry per gap.

    Returns list of dicts with schema:
        gap_id, gap_type, evidence_text,
        agent_a {hypothesis_id, hypothesis, scores, decision},
        agent_b {hypothesis_id, hypothesis, scores, decision},
        preferred_agent, agreement
    """
    # Group by gap_id
    by_gap: Dict[str, Dict] = {}
    for hyp in scored_hyps:
        gid   = hyp.get("gap_id", "")
        agent = hyp.get("source", "AgentA")

        if gid not in by_gap:
            by_gap[gid] = {
                "gap_id":       gid,
                "gap_type":     hyp.get("gap_type", ""),
                "evidence_text": hyp.get("gap_text", ""),
                "agent_a":      None,
                "agent_b":      None,
            }

        slot = {
            "hypothesis_id": hyp.get("hypothesis_id", ""),
            "hypothesis":    hyp.get("hypothesis_text", ""),
            "scores":        hyp.get("scores", {}),
            "decision":      hyp.get("decision", "REVISE"),
        }

        if agent == "AgentA":
            by_gap[gid]["agent_a"] = slot
        else:
            by_gap[gid]["agent_b"] = slot

    # Build final records
    log: List[Dict] = []
    for gid, entry in by_gap.items():
        a = entry["agent_a"] or {"hypothesis_id": "", "hypothesis": "", "scores": {}, "decision": "REJECT"}
        b = entry["agent_b"] or {"hypothesis_id": "", "hypothesis": "", "scores": {}, "decision": "REJECT"}

        # Score-based preference as fallback
        score_preferred = pick_preferred(a, b)
        agreement       = (a.get("decision", "") == b.get("decision", ""))

        # LLM comparative reasoning (when both hypotheses are non-trivial)
        llm_judgment = None
        hyp_a_text = a.get("hypothesis", "")
        hyp_b_text = b.get("hypothesis", "")
        if (has_keys()
                and hyp_a_text and hyp_b_text
                and "[Generation failed]" not in hyp_a_text
                and "[Generation failed]" not in hyp_b_text):
            llm_judgment = _llm_compare(
                entry["evidence_text"],
                hyp_a_text,
                hyp_b_text,
            )

        if llm_judgment:
            preferred = llm_judgment.get("preferred", score_preferred)
            reasoning = llm_judgment.get("reasoning", "")
            synthesis = llm_judgment.get("synthesis", "")
            confidence = llm_judgment.get("confidence", 0.5)

            round_1 = {
                "preferred": preferred,
                "reasoning": reasoning,
                "synthesis": synthesis,
                "confidence": confidence,
            }

            # Round 2: Challenge round — let the non-preferred agent respond
            challenge = _challenge_round(
                entry["evidence_text"],
                hyp_a_text,
                hyp_b_text,
                reasoning,
                preferred,
            )

            round_2 = None
            if challenge:
                round_2 = {
                    "challenger": challenge.get("challenger", ""),
                    "action": challenge.get("action", ""),
                    "response": challenge.get("response", ""),
                    "refined_hypothesis": challenge.get("refined_hypothesis", ""),
                }

            # Round 3: Synthesis verdict
            synthesis_result = _synthesis_round(
                entry["evidence_text"],
                hyp_a_text,
                hyp_b_text,
                reasoning,
                preferred,
                challenge,
            )

            round_3 = None
            if synthesis_result:
                preferred = synthesis_result.get("final_preferred", preferred)
                confidence = synthesis_result.get("confidence", confidence)
                round_3 = {
                    "final_preferred": synthesis_result.get("final_preferred", preferred),
                    "verdict": synthesis_result.get("verdict", ""),
                    "decisive_factor": synthesis_result.get("decisive_factor", ""),
                    "confidence": synthesis_result.get("confidence", 0.5),
                    "recommendation": synthesis_result.get("recommendation", "REVISE"),
                }
            else:
                # Fallback round_3 when LLM unavailable
                round_3 = {
                    "final_preferred": preferred,
                    "verdict": f"Score-based verdict: {preferred} preferred.",
                    "decisive_factor": f"Higher total score ({preferred})",
                    "confidence": confidence,
                    "recommendation": "REVISE",
                }
        else:
            preferred = score_preferred
            reasoning = f"Score-based: AgentA total={a.get('scores', {}).get('total', 0)}, AgentB total={b.get('scores', {}).get('total', 0)}"
            synthesis = ""
            confidence = 0.3
            challenge = None

            round_1 = {
                "preferred": preferred,
                "reasoning": reasoning,
                "synthesis": "",
                "confidence": confidence,
            }
            round_2 = None
            round_3 = {
                "final_preferred": preferred,
                "verdict": reasoning,
                "decisive_factor": "Score-based preference (no LLM keys available)",
                "confidence": confidence,
                "recommendation": "REVISE",
            }

        # If challenge resulted in CONCEDE, keep advisor's choice.
        # If REFINE, note it but keep advisor's choice (refined hyp stored for reflection).
        # If DEFEND, flag for manual review.
        challenge_result = round_2
        if round_2 and round_2.get("action") == "DEFEND":
            # Flag: the non-preferred agent defended — may warrant re-evaluation
            confidence = max(confidence - 0.1, 0.0)

        log.append({
            "gap_id":          entry["gap_id"],
            "gap_type":        entry["gap_type"],
            "evidence_text":   entry["evidence_text"],
            "agent_a":         a,
            "agent_b":         b,
            "preferred_agent": preferred,
            "agreement":       agreement,
            "round_1":         round_1,
            "round_2":         round_2,
            "round_3":         round_3,
            "llm_reasoning":   reasoning,
            "synthesis":       synthesis,
            "confidence":      confidence,
            "challenge":       challenge_result,
        })

    logger.info(
        "Built disagreement log: %d entries, %d agreements",
        len(log),
        sum(1 for e in log if e["agreement"]),
    )
    return log


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run() -> List[Dict]:
    """Load hypotheses_scored.json, build disagreement log, write disagreement_log_all.json."""
    scored_path = OUTPUT_DIR / "hypotheses_scored.json"
    if not scored_path.exists():
        raise FileNotFoundError(f"hypotheses_scored.json not found: {scored_path}")

    scored = json.loads(scored_path.read_text(encoding="utf-8"))
    log = build_disagreement_log(scored)

    out_path = OUTPUT_DIR / "disagreement_log_all.json"
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(log, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(out_path))

    logger.info("Wrote %d disagreement entries to %s", len(log), out_path)
    return log


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run()
