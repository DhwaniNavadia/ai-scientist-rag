"""evaluation/metrics.py — Aggregate evaluation metrics computation.

Computes six metrics across all :class:`~evaluation.pairwise.PairwiseResult`
objects and returns them in a :class:`MetricsSummary` dataclass.
"""

import logging
import math
from dataclasses import asdict, dataclass
from typing import Dict, List

from evaluation.pairwise import PairwiseResult

logger = logging.getLogger("evaluation.metrics")


# ─────────────────────────────────────────────────────────────────────────────
# Data class
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MetricsSummary:
    """Summary of evaluation metrics across all gaps.

    Attributes:
        win_rate:             system_wins / (system_wins + baseline_wins + ties),
                              summed across all runs across all gaps.
        avg_hypothesis_score: Mean of per-gap average system scores.
        keep_rate:            Proportion of gaps where keep_votes >=
                              ceil(n_runs / 2).
        agent_agreement_rate: Proportion of gaps where ALL runs agreed on the
                              same winner.
        total_gaps_evaluated: Number of gaps included in the evaluation.
        total_comparisons_run: Total judge calls executed (sum of n_runs).
    """

    win_rate:              float
    avg_hypothesis_score:  float
    keep_rate:             float
    agent_agreement_rate:  float
    total_gaps_evaluated:  int
    total_comparisons_run: int

    def to_dict(self) -> Dict:
        """Return a plain dict representation suitable for JSON serialisation."""
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(results: List[PairwiseResult]) -> MetricsSummary:
    """Compute all six evaluation metrics from a list of pairwise results.

    Handles edge cases:
    * Empty ``results`` list → all metrics are 0.0 / 0.
    * All ties               → ``win_rate`` is 0.0 (system won nothing).

    Args:
        results: List of :class:`~evaluation.pairwise.PairwiseResult` objects,
                 one per evaluated gap.

    Returns:
        :class:`MetricsSummary` with all metrics populated.
    """
    if not results:
        logger.warning("compute_metrics called with empty results list.")
        return MetricsSummary(
            win_rate=0.0,
            avg_hypothesis_score=0.0,
            keep_rate=0.0,
            agent_agreement_rate=0.0,
            total_gaps_evaluated=0,
            total_comparisons_run=0,
        )

    total_gaps = len(results)

    # ── 1. win_rate ──────────────────────────────────────────────────────────
    # Aggregate wins/losses/ties across ALL runs across ALL gaps.
    total_sys   = sum(r.system_wins   for r in results)
    total_base  = sum(r.baseline_wins for r in results)
    total_ties  = sum(r.ties          for r in results)
    total_all   = total_sys + total_base + total_ties

    win_rate = total_sys / total_all if total_all > 0 else 0.0

    # ── 2. avg_hypothesis_score ──────────────────────────────────────────────
    # Mean of per-gap average system scores.
    avg_hypothesis_score = (
        sum(r.avg_system_score for r in results) / total_gaps
    )

    # ── 3. keep_rate ─────────────────────────────────────────────────────────
    # A gap "passes" if keep_votes >= ceil(n_runs / 2).
    keep_count = sum(
        1
        for r in results
        if r.keep_votes >= math.ceil(r.n_runs / 2)
    )
    keep_rate = keep_count / total_gaps

    # ── 4. agent_agreement_rate ──────────────────────────────────────────────
    # A gap has full agreement when all N runs chose the same winner.
    agree_count = sum(
        1
        for r in results
        if (
            r.system_wins   == r.n_runs
            or r.baseline_wins == r.n_runs
            or r.ties          == r.n_runs
        )
    )
    agent_agreement_rate = agree_count / total_gaps

    # ── 5 & 6. totals ────────────────────────────────────────────────────────
    total_comparisons = sum(r.n_runs for r in results)

    summary = MetricsSummary(
        win_rate=round(win_rate, 4),
        avg_hypothesis_score=round(avg_hypothesis_score, 4),
        keep_rate=round(keep_rate, 4),
        agent_agreement_rate=round(agent_agreement_rate, 4),
        total_gaps_evaluated=total_gaps,
        total_comparisons_run=total_comparisons,
    )

    logger.info(
        "Metrics — win_rate=%.3f  keep_rate=%.3f  "
        "avg_score=%.3f  agreement=%.3f  gaps=%d  runs=%d",
        summary.win_rate, summary.keep_rate, summary.avg_hypothesis_score,
        summary.agent_agreement_rate, summary.total_gaps_evaluated,
        summary.total_comparisons_run,
    )

    return summary
