"""evaluation/tests/test_metrics.py — Unit tests for evaluation/metrics.py."""

import math
import pytest

from evaluation.metrics import MetricsSummary, compute_metrics
from evaluation.pairwise import PairwiseResult


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_result(
    gap_id:          str   = "G1",
    system_wins:     int   = 2,
    baseline_wins:   int   = 1,
    ties:            int   = 0,
    keep_votes:      int   = 2,
    avg_system_score: float = 7.5,
    avg_baseline_score: float = 5.0,
    n_runs:          int   = 3,
) -> PairwiseResult:
    """Build a PairwiseResult with sensible defaults."""
    majority = max(
        {"system": system_wins, "baseline": baseline_wins, "tie": ties},
        key=lambda k: {"system": system_wins, "baseline": baseline_wins, "tie": ties}[k],
    )
    return PairwiseResult(
        gap_id=gap_id,
        majority_winner=majority,
        system_wins=system_wins,
        baseline_wins=baseline_wins,
        ties=ties,
        keep_votes=keep_votes,
        avg_system_score=avg_system_score,
        avg_baseline_score=avg_baseline_score,
        n_runs=n_runs,
    )


# ─────────────────────────────────────────────────────────────────────────────
# MetricsSummary type
# ─────────────────────────────────────────────────────────────────────────────

class TestMetricsSummaryDataclass:
    def test_to_dict_returns_dict(self):
        s = MetricsSummary(
            win_rate=0.5, avg_hypothesis_score=6.0,
            keep_rate=0.5, agent_agreement_rate=0.5,
            total_gaps_evaluated=2, total_comparisons_run=6,
        )
        d = s.to_dict()
        assert isinstance(d, dict)
        assert d["win_rate"] == 0.5

    def test_all_fields_present(self):
        s = MetricsSummary(
            win_rate=0.6, avg_hypothesis_score=7.2,
            keep_rate=0.8, agent_agreement_rate=1.0,
            total_gaps_evaluated=5, total_comparisons_run=15,
        )
        for field in ["win_rate", "avg_hypothesis_score", "keep_rate",
                      "agent_agreement_rate", "total_gaps_evaluated",
                      "total_comparisons_run"]:
            assert field in s.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# compute_metrics — win_rate
# ─────────────────────────────────────────────────────────────────────────────

class TestWinRate:
    def test_basic_win_rate(self):
        # 2 system wins + 1 baseline win across 3 runs → 2/3
        results = [make_result("G1", system_wins=2, baseline_wins=1, ties=0)]
        m = compute_metrics(results)
        assert abs(m.win_rate - 2 / 3) < 1e-4

    def test_win_rate_aggregated_across_gaps(self):
        # G1: sys=2, base=1, ties=0  G2: sys=1, base=2, ties=0
        # total: sys=3, base=3, ties=0 → win_rate = 3/6 = 0.5
        results = [
            make_result("G1", system_wins=2, baseline_wins=1, ties=0),
            make_result("G2", system_wins=1, baseline_wins=2, ties=0),
        ]
        m = compute_metrics(results)
        assert abs(m.win_rate - 0.5) < 1e-4

    def test_all_ties_win_rate_is_zero(self):
        results = [make_result("G1", system_wins=0, baseline_wins=0, ties=3)]
        m = compute_metrics(results)
        assert m.win_rate == 0.0

    def test_all_system_wins(self):
        results = [make_result("G1", system_wins=3, baseline_wins=0, ties=0)]
        m = compute_metrics(results)
        assert abs(m.win_rate - 1.0) < 1e-4

    def test_all_baseline_wins(self):
        results = [make_result("G1", system_wins=0, baseline_wins=3, ties=0)]
        m = compute_metrics(results)
        assert m.win_rate == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# compute_metrics — keep_rate
# ─────────────────────────────────────────────────────────────────────────────

class TestKeepRate:
    def test_keep_rate_when_majority_keep(self):
        # n_runs=3, ceil(3/2)=2; keep_votes=2 → passes
        results = [make_result("G1", keep_votes=2, n_runs=3)]
        m = compute_metrics(results)
        assert m.keep_rate == 1.0

    def test_keep_rate_when_minority_keep(self):
        # n_runs=3, ceil(3/2)=2; keep_votes=1 → fails
        results = [make_result("G1", keep_votes=1, n_runs=3)]
        m = compute_metrics(results)
        assert m.keep_rate == 0.0

    def test_keep_rate_mixed(self):
        # G1: keep=2/3 → passes, G2: keep=1/3 → fails → 1/2
        results = [
            make_result("G1", keep_votes=2, n_runs=3),
            make_result("G2", keep_votes=1, n_runs=3),
        ]
        m = compute_metrics(results)
        assert abs(m.keep_rate - 0.5) < 1e-4

    def test_keep_rate_all_keep(self):
        results = [
            make_result("G1", keep_votes=3, n_runs=3),
            make_result("G2", keep_votes=3, n_runs=3),
        ]
        m = compute_metrics(results)
        assert m.keep_rate == 1.0

    def test_keep_rate_none_keep(self):
        results = [
            make_result("G1", keep_votes=0, n_runs=3),
            make_result("G2", keep_votes=0, n_runs=3),
        ]
        m = compute_metrics(results)
        assert m.keep_rate == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# compute_metrics — agent_agreement_rate
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentAgreementRate:
    def test_full_agreement_system_wins_all(self):
        results = [make_result("G1", system_wins=3, baseline_wins=0, ties=0, n_runs=3)]
        m = compute_metrics(results)
        assert m.agent_agreement_rate == 1.0

    def test_full_agreement_all_ties(self):
        results = [make_result("G1", system_wins=0, baseline_wins=0, ties=3, n_runs=3)]
        m = compute_metrics(results)
        assert m.agent_agreement_rate == 1.0

    def test_no_agreement_split_result(self):
        # 1 system, 1 baseline, 1 tie → no full agreement
        results = [make_result("G1", system_wins=1, baseline_wins=1, ties=1, n_runs=3)]
        m = compute_metrics(results)
        assert m.agent_agreement_rate == 0.0

    def test_mixed_agreement(self):
        # G1: all system (agrees), G2: split (doesn't agree) → 0.5
        results = [
            make_result("G1", system_wins=3, baseline_wins=0, ties=0, n_runs=3),
            make_result("G2", system_wins=1, baseline_wins=1, ties=1, n_runs=3),
        ]
        m = compute_metrics(results)
        assert abs(m.agent_agreement_rate - 0.5) < 1e-4


# ─────────────────────────────────────────────────────────────────────────────
# compute_metrics — edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_results_returns_zeros(self):
        m = compute_metrics([])
        assert m.win_rate               == 0.0
        assert m.avg_hypothesis_score   == 0.0
        assert m.keep_rate              == 0.0
        assert m.agent_agreement_rate   == 0.0
        assert m.total_gaps_evaluated   == 0
        assert m.total_comparisons_run  == 0

    def test_total_gaps_evaluated(self):
        results = [make_result(f"G{i}") for i in range(5)]
        m = compute_metrics(results)
        assert m.total_gaps_evaluated == 5

    def test_total_comparisons_run(self):
        # 3 gaps × 3 runs each = 9
        results = [make_result(f"G{i}", n_runs=3) for i in range(3)]
        m = compute_metrics(results)
        assert m.total_comparisons_run == 9

    def test_avg_hypothesis_score_computed_correctly(self):
        results = [
            make_result("G1", avg_system_score=8.0),
            make_result("G2", avg_system_score=6.0),
        ]
        m = compute_metrics(results)
        assert abs(m.avg_hypothesis_score - 7.0) < 1e-4
