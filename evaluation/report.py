"""evaluation/report.py — Evaluation report generator.

Orchestrates the full evaluation pipeline:
  1. Load research gaps from ``gaps_actionable.json``.
  2. Load system hypotheses from ``disagreement_log_all.json``.
  3. Generate (or load cached) baseline hypotheses via ``baseline.py``.
  4. Run pairwise comparisons via ``pairwise.py``.
  5. Compute aggregate metrics via ``metrics.py``.
  6. Generate an LLM-authored summary (strengths / weaknesses / conclusion).
  7. Save the full report to ``outputs/evaluation/evaluation_report.json``.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ai_scientist.config import OUTPUT_DIR, OPENAI_API_KEY
from evaluation.baseline import run_all_baselines
from evaluation.metrics import MetricsSummary, compute_metrics
from evaluation.pairwise import PairwiseResult, evaluate_all_gaps

logger = logging.getLogger("evaluation.report")

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

EVAL_DIR: Path = OUTPUT_DIR / "evaluation"
PIPELINE_VERSION: str = "1.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> object:
    """Load and return the contents of a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON object.

    Raises:
        FileNotFoundError: If *path* does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _load_gaps(gaps_path: Optional[Path]) -> List[Dict]:
    """Load research gaps from disk.

    If *gaps_path* is a ``.json`` file, load it directly.
    If it is a directory, scan for ``gaps_actionable.json`` within it.
    Falls back to ``OUTPUT_DIR / gaps_actionable.json`` when *gaps_path* is
    ``None``.

    Args:
        gaps_path: Path to a JSON file or directory containing gap files.

    Returns:
        List of gap dicts.
    """
    if gaps_path is None:
        target = OUTPUT_DIR / "gaps_actionable.json"
    elif gaps_path.is_dir():
        target = gaps_path / "gaps_actionable.json"
        if not target.exists():
            # Fallback: first JSON file in the directory.
            candidates = sorted(gaps_path.glob("*.json"))
            target = candidates[0] if candidates else target
    else:
        target = gaps_path

    if not target.exists():
        logger.error("Gap file not found: %s", target)
        return []

    gaps = _load_json(target)
    logger.info("Loaded %d gap(s) from %s", len(gaps), target)
    return gaps


def _load_system_hypotheses(dlog_path: Path) -> Dict[str, Dict]:
    """Build a ``{gap_id: hypothesis_dict}`` map from the disagreement log.

    Uses the ``preferred_agent`` field to pick the winning hypothesis per gap.

    Args:
        dlog_path: Path to ``disagreement_log_all.json``.

    Returns:
        Dict mapping gap_id → system hypothesis dict with at minimum
        ``"hypothesis_text"``.
    """
    if not dlog_path.exists():
        logger.error("disagreement_log_all.json not found at %s", dlog_path)
        return {}

    entries = _load_json(dlog_path)
    sys_hyps: Dict[str, Dict] = {}

    for entry in entries:
        gap_id    = entry.get("gap_id", "")
        preferred = entry.get("preferred_agent", "AgentA")
        agent_key = "agent_a" if preferred == "AgentA" else "agent_b"
        hyp_data  = entry.get(agent_key, {})

        sys_hyps[gap_id] = {
            "hypothesis_text": hyp_data.get("hypothesis", ""),
            "scores":          hyp_data.get("scores", {}),
            "decision":        hyp_data.get("decision", ""),
        }

    logger.info("Loaded system hypotheses for %d gap(s).", len(sys_hyps))
    return sys_hyps


# ─────────────────────────────────────────────────────────────────────────────
# Summary generation
# ─────────────────────────────────────────────────────────────────────────────

def _generate_llm_summary(metrics: MetricsSummary) -> Dict:
    """Ask the LLM to write a summary of the evaluation results.

    Falls back to a rule-based summary if the API call fails.

    Args:
        metrics: Computed :class:`MetricsSummary`.

    Returns:
        Dict with ``"strengths"`` (list), ``"weaknesses"`` (list),
        ``"conclusion"`` (str).
    """
    system_prompt = (
        "You are a senior AI researcher reviewing an evaluation of a "
        "multi-agent research hypothesis generation system versus a single-agent "
        "baseline. Based on the provided metrics, generate a concise JSON summary "
        "with three keys: "
        '"strengths" (list of strings — what the system does well), '
        '"weaknesses" (list of strings — where it underperforms), '
        '"conclusion" (2-3 sentence overall verdict). '
        "Return ONLY valid JSON, no preamble."
    )

    user_message = (
        f"Evaluation metrics:\n{json.dumps(metrics.to_dict(), indent=2)}\n\n"
        "Generate a JSON summary with keys: strengths, weaknesses, conclusion."
    )

    for attempt in range(2):
        if attempt > 0:
            time.sleep(3)
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                max_tokens=512,
                temperature=0.4,
            )
            raw  = resp.choices[0].message.content or ""
            text = raw.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                inner = (
                    lines[1:-1]
                    if lines and lines[-1].strip().startswith("```")
                    else lines[1:]
                )
                text = "\n".join(inner)
            data = json.loads(text)
            return {
                "strengths":  list(data.get("strengths",  [])),
                "weaknesses": list(data.get("weaknesses", [])),
                "conclusion": str(data.get("conclusion",  "")),
            }
        except Exception as exc:
            logger.warning("LLM summary attempt %d failed: %s", attempt + 1, exc)

    logger.warning("LLM summary unavailable — using rule-based fallback.")
    return _rule_based_summary(metrics)


def _rule_based_summary(metrics: MetricsSummary) -> Dict:
    """Generate a summary purely from metric thresholds, no LLM required.

    Args:
        metrics: Computed :class:`MetricsSummary`.

    Returns:
        Dict with ``"strengths"``, ``"weaknesses"``, ``"conclusion"``.
    """
    strengths:  List[str] = []
    weaknesses: List[str] = []

    if metrics.win_rate > 0.55:
        strengths.append(
            f"System outperformed the baseline in {metrics.win_rate:.0%} of comparisons."
        )
    elif metrics.win_rate < 0.35:
        weaknesses.append(
            f"System won only {metrics.win_rate:.0%} of comparisons against the baseline."
        )
    else:
        strengths.append("System performance is competitive with the single-agent baseline.")

    if metrics.keep_rate > 0.55:
        strengths.append(
            f"High keep rate ({metrics.keep_rate:.0%}) indicates consistently useful hypotheses."
        )
    elif metrics.keep_rate < 0.3:
        weaknesses.append(
            f"Low keep rate ({metrics.keep_rate:.0%}) suggests many hypotheses need revision."
        )

    if metrics.avg_hypothesis_score >= 7.0:
        strengths.append(
            f"Average system score of {metrics.avg_hypothesis_score:.2f}/10 reflects strong quality."
        )
    elif metrics.avg_hypothesis_score < 5.0:
        weaknesses.append(
            f"Average system score of {metrics.avg_hypothesis_score:.2f}/10 is below expectations."
        )

    if metrics.agent_agreement_rate > 0.7:
        strengths.append(
            f"High judge agreement ({metrics.agent_agreement_rate:.0%}) shows consistent evaluation."
        )
    else:
        weaknesses.append(
            f"Low judge agreement ({metrics.agent_agreement_rate:.0%}) indicates evaluation variance."
        )

    if not strengths:
        strengths.append("System generates hypotheses for all identified gaps.")
    if not weaknesses:
        weaknesses.append("No significant weaknesses detected at this evaluation scale.")

    if metrics.win_rate > 0.5:
        verdict = (
            f"The multi-agent system demonstrates clear improvement over the single-agent baseline "
            f"with a {metrics.win_rate:.0%} win rate and an average hypothesis quality score of "
            f"{metrics.avg_hypothesis_score:.2f}/10. "
            "The system's debate and critic mechanisms add measurable value."
        )
    else:
        verdict = (
            f"The multi-agent system has not yet demonstrated a significant advantage over the "
            f"single-agent baseline (win rate: {metrics.win_rate:.0%}). "
            "Further tuning of the hypothesis generation and critic stages is recommended."
        )

    return {"strengths": strengths, "weaknesses": weaknesses, "conclusion": verdict}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def run(
    gaps_path:    Optional[Path] = None,
    baseline_dir: Optional[Path] = None,
    output_dir:   Optional[Path] = None,
    n_runs:       int = 3,
    verbose:      bool = False,
) -> Dict:
    """Orchestrate the full evaluation pipeline and save the report.

    Steps:
        1. Load gaps from *gaps_path* (defaults to
           ``outputs/gaps_actionable.json``).
        2. Load system hypotheses from ``outputs/disagreement_log_all.json``.
        3. Generate / load baseline hypotheses for every gap.
        4. Pair system with baseline, run *n_runs* pairwise evaluations per gap.
        5. Compute aggregate metrics.
        6. Generate LLM summary (falls back to rule-based on API failure).
        7. Assemble and save the full report JSON.

    Args:
        gaps_path:    Path to the gaps JSON file or directory.  ``None`` uses
                      the default pipeline output location.
        baseline_dir: Directory for baseline cache files.  ``None`` uses
                      ``outputs/baseline/``.
        output_dir:   Directory for the evaluation report.  ``None`` uses
                      ``outputs/evaluation/``.
        n_runs:       Number of judge runs per gap pair (default: 3).
        verbose:      Enable debug-level logging.

    Returns:
        Full report dict matching the ``evaluation_report.json`` schema.

    Raises:
        RuntimeError: If no evaluable gap pairs can be assembled.
    """
    if verbose:
        logging.getLogger("evaluation").setLevel(logging.DEBUG)

    report_dir = output_dir if output_dir is not None else EVAL_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Load gaps ─────────────────────────────────────────────────────────
    gaps = _load_gaps(gaps_path)
    if not gaps:
        raise RuntimeError("No gaps found. Run --mode tier1 first.")

    # ── 2. Load system hypotheses ────────────────────────────────────────────
    dlog_path = OUTPUT_DIR / "disagreement_log_all.json"
    sys_hyps  = _load_system_hypotheses(dlog_path)

    # ── 3. Generate / load baselines ─────────────────────────────────────────
    from evaluation.baseline import BASELINE_DIR as _default_baseline_dir
    effective_baseline_dir = baseline_dir if baseline_dir is not None else _default_baseline_dir

    # Temporarily redirect BASELINE_DIR if a custom path was given.
    import evaluation.baseline as _baseline_mod
    _orig_dir = _baseline_mod.BASELINE_DIR
    _baseline_mod.BASELINE_DIR = effective_baseline_dir
    try:
        baseline_results = run_all_baselines(gaps)
    finally:
        _baseline_mod.BASELINE_DIR = _orig_dir

    baseline_by_id: Dict[str, Dict] = {b["gap_id"]: b for b in baseline_results}

    # ── 4. Build pairs and evaluate ──────────────────────────────────────────
    pairs: List[Tuple[str, str, Dict, Dict]] = []
    skipped: List[str] = []

    for gap in gaps:
        gap_id      = gap.get("gap_id", "")
        gap_text    = gap.get("gap_text") or gap.get("gap_statement", "")
        direction   = gap.get("actionable_direction", "")
        description = f"{gap_text} {direction}".strip()

        sys_hyp  = sys_hyps.get(gap_id)
        base_hyp = baseline_by_id.get(gap_id)

        if sys_hyp is None:
            logger.warning("No system hypothesis for gap %s — skipping.", gap_id)
            skipped.append(gap_id)
            continue
        if base_hyp is None:
            logger.warning("No baseline hypothesis for gap %s — skipping.", gap_id)
            skipped.append(gap_id)
            continue

        pairs.append((gap_id, description, sys_hyp, base_hyp))

    if not pairs:
        raise RuntimeError(
            "No evaluable gap pairs found.  "
            "Ensure both the pipeline and baseline outputs are present."
        )

    if skipped:
        logger.warning("Skipped %d gap(s) due to missing data: %s", len(skipped), skipped)

    pairwise_results: List[PairwiseResult] = evaluate_all_gaps(pairs, n_runs=n_runs)

    # ── 5. Compute metrics ───────────────────────────────────────────────────
    metrics: MetricsSummary = compute_metrics(pairwise_results)

    # ── 6. Generate summary ──────────────────────────────────────────────────
    summary = _generate_llm_summary(metrics)

    # ── 7. Assemble and save report ──────────────────────────────────────────
    report: Dict = {
        "metadata": {
            "timestamp":        datetime.now(timezone.utc).isoformat(),
            "pipeline_version": PIPELINE_VERSION,
            "n_runs_per_pair":  n_runs,
            "total_gaps":       len(pairs),
        },
        "metrics":          metrics.to_dict(),
        "per_gap_results":  [r.to_dict() for r in pairwise_results],
        "summary":          summary,
    }

    report_path = report_dir / "evaluation_report.json"
    tmp_path    = report_path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tmp_path.replace(report_path)
    logger.info("Evaluation report saved → %s", report_path)

    # Print human-readable summary to console.
    print("\n" + "═" * 60)
    print("  EVALUATION SUMMARY")
    print("═" * 60)
    print(f"  Gaps evaluated : {metrics.total_gaps_evaluated}")
    print(f"  Total runs     : {metrics.total_comparisons_run}")
    print(f"  Win rate       : {metrics.win_rate:.1%}")
    print(f"  Keep rate      : {metrics.keep_rate:.1%}")
    print(f"  Avg sys score  : {metrics.avg_hypothesis_score:.2f} / 10")
    print(f"  Agreement rate : {metrics.agent_agreement_rate:.1%}")
    print("─" * 60)
    print("  Strengths:")
    for s in summary.get("strengths", []):
        print(f"    • {s}")
    print("  Weaknesses:")
    for w in summary.get("weaknesses", []):
        print(f"    • {w}")
    print("  Conclusion:")
    print(f"    {summary.get('conclusion', '')}")
    print("═" * 60 + "\n")

    return report
