from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.schemas import (
    AgentHypothesis,
    Claim,
    CrossPaperData,
    EvalMetrics,
    EvalSummary,
    EvaluationReport,
    FinalReport,
    Gap,
    HypothesisPair,
    PerGapEvalResult,
    ReflectionEntry,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_json(path: Path) -> Optional[Any]:
    """Return parsed JSON or None if file missing / invalid."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _find_output_dir(paper_id: str, outputs_root: Path) -> Path:
    """
    Return the directory that contains pipeline output files for paper_id.
    Only falls back to the root outputs/ dir for 'default' paper_id.
    """
    candidate = outputs_root / paper_id
    if candidate.is_dir() and any(candidate.iterdir()):
        return candidate
    # Only fall back to root for the special "default" paper
    if paper_id == "default":
        return outputs_root
    # Return the per-paper dir even if it doesn't exist yet
    # (reader functions handle missing files gracefully)
    return candidate


def _extract_title(sections: Any) -> str:
    """Best-effort: pull a title from sections dict or return a default."""
    if not isinstance(sections, dict):
        return "Research Paper"
    # Some parsers put a "title" key at the top level
    for key in ("title", "Title", "TITLE"):
        if isinstance(sections.get(key), str) and sections[key].strip():
            return sections[key].strip()
    return "Research Paper"


# ── Claim mapping ─────────────────────────────────────────────────────────────

_CONFIDENCE_MAP = {"high": 0.9, "medium": 0.7, "low": 0.5}


def _to_float_confidence(value: Any, default: float = 0.5) -> float:
    """Convert 'high'/'medium'/'low' strings or numeric values to float."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        mapped = _CONFIDENCE_MAP.get(value.strip().lower())
        if mapped is not None:
            return mapped
        try:
            return float(value)
        except ValueError:
            pass
    return default


def _map_claims(raw: Any) -> List[Claim]:
    if not isinstance(raw, list):
        return []
    out: List[Claim] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        out.append(
            Claim(
                claim_id=str(item.get("claim_id", f"C{i+1}")),
                claim_text=str(item.get("claim_text", "")),
                evidence_text=str(item.get("evidence_text", "")),
                confidence=_to_float_confidence(item.get("confidence", 0.5)),
                section=str(item.get("section", "Unknown")),
            )
        )
    return out


# ── Gap mapping ───────────────────────────────────────────────────────────────

def _map_gaps(raw: Any) -> List[Gap]:
    if not isinstance(raw, list):
        return []
    out: List[Gap] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        # Support both old schema (gap_statement) and new schema (gap_description)
        description = str(
            item.get("gap_description")
            or item.get("gap_statement")
            or item.get("gap_text")
            or ""
        )
        direction = str(
            item.get("actionable_direction")
            or item.get("evidence_text")
            or item.get("direction")
            or ""
        )
        out.append(
            Gap(
                gap_id=str(item.get("gap_id", f"G{i+1}")),
                gap_description=description,
                gap_type=str(
                    item.get("gap_type")
                    or item.get("type")
                    or "unknown"
                ),
                actionable_direction=direction,
                priority=int(item.get("priority") or i + 1),
            )
        )
    return out


# ── Hypothesis pair mapping ───────────────────────────────────────────────────

def _make_agent_hyp(agent_label: str, raw_output: Dict) -> AgentHypothesis:
    # Support both new format (scores at top level) and legacy format (nested under critic)
    critic = raw_output.get("critic") or raw_output.get("scores") or {}
    if isinstance(critic, dict) and "total" not in critic:
        # scores dict: {clarity, novelty, feasibility, total}
        total = float(critic.get("total", 0))
    else:
        total = float(critic.get("total", 0))
    # Normalise from 0–15 to 0–10
    score = round((total / 15.0) * 10.0, 1) if total > 0 else 0.0
    hypothesis_text = str(
        raw_output.get("hypothesis_text", "")
        or raw_output.get("hypothesis", "")
    )
    decision = str(
        raw_output.get("decision", "")
        or critic.get("decision", "KEEP")
    )
    return AgentHypothesis(
        agent=agent_label,
        hypothesis=hypothesis_text,
        rationale=str(raw_output.get("rationale", "Based on critic analysis.")),
        score=score,
        decision=decision,
    )


def _map_pairs(debate_log: Any) -> List[HypothesisPair]:
    """Map disagreement_log_all.json entries → HypothesisPair list.

    Supports two formats:
      - New: entry["agent_a"] / entry["agent_b"] dicts + entry["preferred_agent"]
      - Legacy: entry["agent_outputs"] list + entry["disagreement_summary"]
    """
    if not isinstance(debate_log, list):
        return []
    out: List[HypothesisPair] = []
    for entry in debate_log:
        if not isinstance(entry, dict):
            continue
        gap_id = str(entry.get("gap_id", ""))

        # --- New format: agent_a / agent_b top-level keys ---
        if "agent_a" in entry or "agent_b" in entry:
            a_raw = entry.get("agent_a") or {}
            b_raw = entry.get("agent_b") or {}
            agent_a = _make_agent_hyp("AgentA", a_raw)
            agent_b = _make_agent_hyp("AgentB", b_raw)
            preferred = str(entry.get("preferred_agent", "AgentA"))
            agreement = bool(entry.get("agreement", agent_a.decision == agent_b.decision))
        else:
            # --- Legacy format: agent_outputs list ---
            agent_outputs = entry.get("agent_outputs", [])
            if not isinstance(agent_outputs, list) or len(agent_outputs) < 2:
                continue
            by_agent = {ao.get("agent"): ao for ao in agent_outputs if isinstance(ao, dict)}
            a_raw = by_agent.get("AgentA") or agent_outputs[0]
            b_raw = by_agent.get("AgentB") or agent_outputs[1]
            agent_a = _make_agent_hyp("AgentA", a_raw)
            agent_b = _make_agent_hyp("AgentB", b_raw)
            summary = entry.get("disagreement_summary") or {}
            preferred = str(summary.get("preferred", "AgentA"))
            agreement = agent_a.decision == agent_b.decision

        out.append(
            HypothesisPair(
                gap_id=gap_id,
                agentA=agent_a,
                agentB=agent_b,
                preferred=preferred,
                agreement=agreement,
            )
        )
    return out


# ── Reflection mapping ────────────────────────────────────────────────────────

def _map_reflections(raw: Any) -> List[ReflectionEntry]:
    if not isinstance(raw, list):
        return []
    out: List[ReflectionEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        # Real schema: hypothesis_id, why, improvement_plan, trace.gap_id
        trace = item.get("trace") or {}
        gap_id = str(
            item.get("gap_id")
            or (trace.get("gap_id") if isinstance(trace, dict) else None)
            or ""
        )
        original = str(
            item.get("original_hypothesis")
            or item.get("why")
            or item.get("hypothesis_text")
            or ""
        )
        out.append(
            ReflectionEntry(
                gap_id=gap_id,
                original_hypothesis=original,
                improvement_plan=str(item.get("improvement_plan", "")),
                revised_hypothesis=str(
                    item.get("revised_hypothesis")
                    or item.get("improved_hypothesis")
                    or original
                ),
                improvement_score=_to_float_confidence(
                    item.get("improvement_score", 0.0), default=0.0
                ),
            )
        )
    return out


# ── Sections mapping ──────────────────────────────────────────────────────────

def _map_sections(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    result: Dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            result[key] = value
        elif isinstance(value, list):
            result[key] = " ".join(str(v) for v in value)
        elif isinstance(value, dict):
            result[key] = json.dumps(value)
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def read_final_report(paper_id: str, outputs_root: Path) -> FinalReport:
    base = _find_output_dir(paper_id, outputs_root)

    sections_raw = _read_json(base / "sections.json") or {}
    claims_raw = _read_json(base / "claims.json") or []
    gaps_raw = _read_json(base / "gaps_actionable.json") or []
    debate_raw = _read_json(base / "disagreement_log_all.json") or []
    reflect_raw = _read_json(base / "reflection_logs.json") or []

    title = _extract_title(sections_raw)
    # Check if final_report.json has a richer title
    final_raw = _read_json(base / "final_report.json") or {}
    if isinstance(final_raw, dict) and final_raw.get("paper_title"):
        title = str(final_raw["paper_title"])

    return FinalReport(
        paper_id=paper_id,
        paper_title=title,
        sections=_map_sections(sections_raw),
        claims=_map_claims(claims_raw),
        gaps=_map_gaps(gaps_raw),
        hypothesis_pairs=_map_pairs(debate_raw),
        reflections=_map_reflections(reflect_raw),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def read_evaluation_report(paper_id: str, outputs_root: Path) -> EvaluationReport:
    base = _find_output_dir(paper_id, outputs_root)
    # Try outputs/{paper_id}/evaluation/ then outputs/evaluation/
    # Try multiple filename variants: evaluation_report.json, evaluation_metrics.json, eval_metrics.json
    eval_candidates = [
        base / "evaluation" / "evaluation_report.json",
        base / "evaluation_report.json",
        base / "evaluation" / "evaluation_metrics.json",
        base / "evaluation_metrics.json",
        base / "eval_metrics.json",
        outputs_root / "evaluation" / "evaluation_report.json",
        outputs_root / "evaluation" / "evaluation_metrics.json",
        outputs_root / "evaluation_metrics.json",
        outputs_root / "eval_metrics.json",
    ]
    eval_path = None
    for candidate in eval_candidates:
        if candidate.exists():
            eval_path = candidate
            break
    if eval_path is None:
        eval_path = base / "evaluation_report.json"  # will trigger FileNotFoundError below

    raw = _read_json(eval_path)
    if not isinstance(raw, dict):
        raise FileNotFoundError(f"evaluation_report.json not found for paper_id={paper_id!r}")

    # Map metrics
    metrics_raw = raw.get("metrics") or {}
    metrics = EvalMetrics(
        win_rate=float(metrics_raw.get("win_rate", 0.0)),
        avg_hypothesis_score=float(metrics_raw.get("avg_hypothesis_score", 0.0)),
        keep_rate=float(metrics_raw.get("keep_rate", 0.0)),
        agent_agreement_rate=float(metrics_raw.get("agent_agreement_rate", 0.0)),
        total_gaps_evaluated=int(metrics_raw.get("total_gaps_evaluated", 0)),
        total_comparisons_run=int(
            metrics_raw.get("total_comparisons_run")
            or metrics_raw.get("total_comparisons", 0)
        ),
    )

    # Map per-gap results
    per_gap: List[PerGapEvalResult] = []
    for item in raw.get("per_gap_results", []):
        if not isinstance(item, dict):
            continue
        per_gap.append(
            PerGapEvalResult(
                gap_id=str(item.get("gap_id", "")),
                gap_description=str(
                    item.get("gap_description")
                    or item.get("gap_statement")
                    or ""
                ),
                majority_winner=str(item.get("majority_winner", "tie")),
                system_wins=int(item.get("system_wins", 0)),
                baseline_wins=int(item.get("baseline_wins", 0)),
                ties=int(item.get("ties", 0)),
                keep_votes=int(item.get("keep_votes", 0)),
                avg_system_score=float(item.get("avg_system_score", 0.0)),
                avg_baseline_score=float(item.get("avg_baseline_score", 0.0)),
            )
        )

    # Map summary
    summary_raw = raw.get("summary") or {}
    summary = EvalSummary(
        strengths=list(summary_raw.get("strengths", [])),
        weaknesses=list(summary_raw.get("weaknesses", [])),
        conclusion=str(summary_raw.get("conclusion", "")),
    )

    return EvaluationReport(
        paper_id=paper_id,
        metrics=metrics,
        per_gap_results=per_gap,
        summary=summary,
    )


def list_available_papers(outputs_root: Path, inputs_dir: Optional[Path] = None) -> List[str]:
    """
    Return known paper IDs.
    Merges papers that have outputs with papers that have been uploaded.
    """
    papers: set[str] = set()
    if outputs_root.is_dir():
        for child in sorted(outputs_root.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                if any((child / f).exists() for f in ("sections.json", "final_report.json", "gaps_actionable.json")):
                    papers.add(child.name)
        # If no subdirs have pipeline outputs but outputs/ itself does:
        if not papers:
            marker_files = ("sections.json", "final_report.json", "gaps_actionable.json")
            if any((outputs_root / f).exists() for f in marker_files):
                papers.add("default")
    # Also include uploaded papers so they appear in the UI
    if inputs_dir and inputs_dir.is_dir():
        for pdf in inputs_dir.iterdir():
            if pdf.suffix.lower() == ".pdf":
                papers.add(pdf.stem)
    return sorted(papers)


def read_cross_paper_data(paper_id: str, outputs_root: Path) -> CrossPaperData:
    base = _find_output_dir(paper_id, outputs_root)
    claims_raw = _read_json(base / "cross_paper_claims.json")
    contrad_raw = _read_json(base / "cross_paper_contradictions.json")

    # cross_paper_claims.json may be a dict {"paper2": [...], "paper3": [...]} or a list
    cross_claims: list = []
    if isinstance(claims_raw, dict):
        # Flatten all paper lists into a single list of claim entries
        for paper_key, claim_list in claims_raw.items():
            if isinstance(claim_list, list):
                for claim_text in claim_list:
                    cross_claims.append({"source": paper_key, "claim": claim_text})
    elif isinstance(claims_raw, list):
        cross_claims = claims_raw

    contradictions: list = contrad_raw if isinstance(contrad_raw, list) else []

    return CrossPaperData(cross_claims=cross_claims, contradictions=contradictions)
