"""ai_scientist/reporting/assembler.py — Assemble the final report from all pipeline outputs."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from ai_scientist.config import OUTPUT_DIR


# ---------------------------------------------------------------------------
# Safe dict traversal
# ---------------------------------------------------------------------------

def safe_get(d: Any, *keys: str, default: Any = None) -> Any:
    """Traverse nested dicts without raising KeyError or TypeError."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
        if d is None:
            return default
    return d


# ---------------------------------------------------------------------------
# Preference logic (works with new disagreement_log_all.json schema)
# ---------------------------------------------------------------------------

def _decision_rank(decision: str) -> int:
    return {"KEEP": 3, "REVISE": 2}.get(decision, 1)


def pick_preferred(entry: Dict) -> str:
    """
    Select the preferred agent from a disagreement log entry (new schema).
    Schema: entry["agent_a"] / entry["agent_b"] with .decision and .scores.total
    """
    a = entry.get("agent_a", {})
    b = entry.get("agent_b", {})

    ra = _decision_rank(safe_get(a, "decision", default="REJECT"))
    rb = _decision_rank(safe_get(b, "decision", default="REJECT"))

    if ra > rb:
        return "AgentA"
    if rb > ra:
        return "AgentB"

    ta = safe_get(a, "scores", "total", default=0) or 0
    tb = safe_get(b, "scores", "total", default=0) or 0

    if ta > tb:
        return "AgentA"
    if tb > ta:
        return "AgentB"

    return "AgentA"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _load(filename: str) -> Any:
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Required output missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Core assembler
# ---------------------------------------------------------------------------

def run() -> Dict:
    """
    Load all pipeline output JSON files, apply preference logic, build and
    write ``outputs/final_report.json``.

    Returns the assembled report dict.
    """
    sections     = _load("sections.json")
    claims       = _load("claims.json")
    gaps         = _load("gaps_actionable.json")
    scored       = _load("hypotheses_scored.json")
    reflections  = _load("reflection_logs.json")
    disagreements = _load("disagreement_log_all.json")

    # Index helpers
    gaps_by_id      = {safe_get(g, "gap_id", default=""): g for g in gaps}
    reflections_by_hyp = {safe_get(r, "hypothesis_id", default=""): r for r in reflections}

    # Apply / refresh preferred_agent on every disagreement entry
    for entry in disagreements:
        entry["preferred_agent"] = pick_preferred(entry)

    # ------------------------------------------------------------------
    # Build full hypothesis lineage from ALL 16 disagreement entries
    # (fixes the 16 vs 3 mismatch in the original main.py)
    # ------------------------------------------------------------------
    hypothesis_lineage: List[Dict] = []
    for entry in disagreements:
        gap_id    = safe_get(entry, "gap_id",   default="")
        gap       = gaps_by_id.get(gap_id, {})
        preferred = pick_preferred(entry)
        agent_key = "agent_a" if preferred == "AgentA" else "agent_b"
        hyp       = entry.get(agent_key, {})

        hyp_id     = safe_get(hyp, "hypothesis_id", default="")
        reflection = reflections_by_hyp.get(hyp_id, {})

        # Support both the old gap schema (gap_statement / evidence_text) and
        # the new schema (gap_text) for backward compatibility with pre-computed files.
        gap_text = (
            safe_get(gap, "gap_text", default="")
            or safe_get(gap, "gap_statement", default="")
        )

        hypothesis_lineage.append({
            "gap_id":            gap_id,
            "gap_type":          safe_get(entry, "gap_type",  default=""),
            "gap_text":          gap_text,
            "preferred_agent":   preferred,
            "hypothesis_text":   safe_get(hyp, "hypothesis",  default=""),
            "scores":            safe_get(hyp, "scores",       default={}),
            "decision":          safe_get(hyp, "decision",     default=""),
            "reflection":        safe_get(reflection, "reflection",         default=""),
            "revised_hypothesis": safe_get(reflection, "revised_hypothesis", default=""),
        })

    report: Dict = {
        "project": {
            "name":  "Autonomous AI Scientist (MVP)",
            "scope": "Single-paper + cross-paper pipeline with multi-agent reasoning",
        },
        "paper_context": {
            "available_sections":      list(sections.keys()),
            "num_claims":              len(claims),
            "num_gaps":                len(gaps),
            "num_hypotheses":          len(scored),
            "num_disagreement_entries": len(disagreements),
        },
        "claims":             claims,
        "gaps_actionable":    gaps,
        "hypothesis_lineage": hypothesis_lineage,
        "disagreement_log":   disagreements,
    }

    out_path = OUTPUT_DIR / "final_report.json"
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(out_path))

    logger.info(
        "Wrote final_report.json — lineage: %d entries, claims: %d, gaps: %d",
        len(hypothesis_lineage), len(claims), len(gaps),
    )
    return report


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run()
