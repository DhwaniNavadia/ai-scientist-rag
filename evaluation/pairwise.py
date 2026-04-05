"""evaluation/pairwise.py — Pairwise comparison system with self-consistency.

For each (system_hypothesis, baseline_hypothesis) pair, runs N independent
judge evaluations and aggregates the results into a :class:`PairwiseResult`
dataclass.  Using multiple runs guards against judge variance.
"""

import logging
from dataclasses import asdict, dataclass
from typing import Dict, List, Tuple

from evaluation.judge import judge as run_judge

logger = logging.getLogger("evaluation.pairwise")


# ─────────────────────────────────────────────────────────────────────────────
# Data class
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PairwiseResult:
    """Aggregated result of N judge evaluations for a single gap pair.

    Attributes:
        gap_id:             Gap identifier (e.g. ``"G1"``).
        majority_winner:    Most-common winner across all runs
                            (``"system"`` | ``"baseline"`` | ``"tie"``).
        system_wins:        Number of runs the system won.
        baseline_wins:      Number of runs the baseline won.
        ties:               Number of tied runs.
        keep_votes:         Number of runs where ``keep_system`` was ``True``.
        avg_system_score:   Mean system score across all runs.
        avg_baseline_score: Mean baseline score across all runs.
        n_runs:             Total runs attempted for this pair.
    """

    gap_id:             str
    majority_winner:    str
    system_wins:        int
    baseline_wins:      int
    ties:               int
    keep_votes:         int
    avg_system_score:   float
    avg_baseline_score: float
    n_runs:             int

    def to_dict(self) -> Dict:
        """Return a plain dict representation suitable for JSON serialisation."""
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def _majority(system_wins: int, baseline_wins: int, ties: int) -> str:
    """Return the most common outcome across N runs.

    Args:
        system_wins:   Count of system wins.
        baseline_wins: Count of baseline wins.
        ties:          Count of ties.

    Returns:
        ``"system"``, ``"baseline"``, or ``"tie"``.
    """
    counts = {
        "system":   system_wins,
        "baseline": baseline_wins,
        "tie":      ties,
    }
    return max(counts, key=lambda k: counts[k])


def evaluate_gap(
    gap_id:          str,
    gap_description: str,
    system_hyp:      Dict,
    baseline_hyp:    Dict,
    n_runs:          int = 3,
) -> PairwiseResult:
    """Run N independent judge evaluations for one gap pair.

    Each evaluation calls the judge independently, providing self-consistency
    over stochastic LLM outputs.  Failed individual runs are logged and
    skipped; if ALL runs fail, a zero-score result is returned rather than
    raising.

    Args:
        gap_id:          Identifier of the gap being evaluated.
        gap_description: Plain-text description of the research gap.
        system_hyp:      System hypothesis dict (from the pipeline).
        baseline_hyp:    Baseline hypothesis dict (from ``baseline.py``).
        n_runs:          Number of independent judge calls (default: 3).

    Returns:
        :class:`PairwiseResult` aggregating all runs.
    """
    logger.info("Evaluating gap %s with %d judge run(s).", gap_id, n_runs)

    system_wins   = 0
    baseline_wins = 0
    ties          = 0
    keep_votes    = 0
    system_scores:   List[float] = []
    baseline_scores: List[float] = []
    successful_runs  = 0

    for run_idx in range(n_runs):
        try:
            result = run_judge(system_hyp, baseline_hyp, gap_description)
            logger.debug(
                "  Gap %s run %d/%d: winner=%s  sys=%.1f  base=%.1f",
                gap_id, run_idx + 1, n_runs,
                result["winner"], result["system_score"], result["baseline_score"],
            )

            if result["winner"] == "system":
                system_wins += 1
            elif result["winner"] == "baseline":
                baseline_wins += 1
            else:
                ties += 1

            if result["keep_system"]:
                keep_votes += 1

            system_scores.append(result["system_score"])
            baseline_scores.append(result["baseline_score"])
            successful_runs += 1

        except (ValueError, Exception) as exc:
            logger.warning(
                "Judge run %d/%d for gap %s failed: %s", run_idx + 1, n_runs, gap_id, exc
            )

    # Handle case where all runs failed.
    if successful_runs == 0:
        logger.error("All %d judge runs failed for gap %s. Returning zero result.", n_runs, gap_id)
        return PairwiseResult(
            gap_id=gap_id,
            majority_winner="tie",
            system_wins=0,
            baseline_wins=0,
            ties=n_runs,
            keep_votes=0,
            avg_system_score=0.0,
            avg_baseline_score=0.0,
            n_runs=n_runs,
        )

    avg_sys  = sum(system_scores)   / len(system_scores)
    avg_base = sum(baseline_scores) / len(baseline_scores)

    majority = _majority(system_wins, baseline_wins, ties)

    logger.info(
        "Gap %s result: majority=%s  sys_wins=%d  base_wins=%d  ties=%d  "
        "keep=%d  avg_sys=%.2f  avg_base=%.2f",
        gap_id, majority, system_wins, baseline_wins, ties,
        keep_votes, avg_sys, avg_base,
    )

    return PairwiseResult(
        gap_id=gap_id,
        majority_winner=majority,
        system_wins=system_wins,
        baseline_wins=baseline_wins,
        ties=ties,
        keep_votes=keep_votes,
        avg_system_score=round(avg_sys, 4),
        avg_baseline_score=round(avg_base, 4),
        n_runs=successful_runs,
    )


def evaluate_all_gaps(
    pairs:  List[Tuple[str, str, Dict, Dict]],
    n_runs: int = 3,
) -> List[PairwiseResult]:
    """Run pairwise evaluation for every gap pair.

    Args:
        pairs:  List of ``(gap_id, gap_description, system_hyp, baseline_hyp)``
                tuples.
        n_runs: Number of independent judge runs per pair (default: 3).

    Returns:
        List of :class:`PairwiseResult`, one per gap.
    """
    logger.info("Starting pairwise evaluation: %d gap(s) × %d run(s).", len(pairs), n_runs)
    results: List[PairwiseResult] = []

    for gap_id, gap_description, system_hyp, baseline_hyp in pairs:
        result = evaluate_gap(
            gap_id=gap_id,
            gap_description=gap_description,
            system_hyp=system_hyp,
            baseline_hyp=baseline_hyp,
            n_runs=n_runs,
        )
        results.append(result)

    logger.info("Pairwise evaluation complete: %d results.", len(results))
    return results
