"""evaluation/tests/test_report.py — Unit tests for evaluation/report.py."""

import json
import pytest
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch, MagicMock

from evaluation.metrics import MetricsSummary
from evaluation.pairwise import PairwiseResult


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures & helpers
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_METRICS = MetricsSummary(
    win_rate=0.667,
    avg_hypothesis_score=7.2,
    keep_rate=0.8,
    agent_agreement_rate=0.6,
    total_gaps_evaluated=3,
    total_comparisons_run=9,
)

SAMPLE_PAIRWISE = PairwiseResult(
    gap_id="G1",
    majority_winner="system",
    system_wins=2,
    baseline_wins=1,
    ties=0,
    keep_votes=2,
    avg_system_score=7.5,
    avg_baseline_score=5.0,
    n_runs=3,
)

SAMPLE_SUMMARY = {
    "strengths":  ["System shows strong novelty.", "High keep rate."],
    "weaknesses": ["Moderate agreement between judge runs."],
    "conclusion": "The multi-agent system outperforms the baseline on this dataset.",
}

GAPS = [
    {
        "gap_id":               "G1",
        "gap_text":             "Current methods do not scale.",
        "actionable_direction": "Explore decomposition.",
        "gap_type":             "scalability",
    }
]

SYSTEM_HYP = {"hypothesis_text": "Hierarchical decomposition reduces complexity."}
BASELINE_HYP = {
    "gap_id":          "G1",
    "gap_description": "Current methods do not scale.",
    "hypothesis":      "A greedy heuristic will work.",
    "rationale":       "Simple and effective.",
    "confidence":      0.6,
    "generated_by":    "baseline",
    "timestamp":       "2026-01-01T00:00:00+00:00",
}


def _make_disagreement_log() -> List[Dict]:
    return [
        {
            "gap_id":         "G1",
            "gap_type":       "scalability",
            "evidence_text":  "Current methods do not scale.",
            "preferred_agent": "AgentA",
            "agent_a": {
                "hypothesis_id": "HA_G1",
                "hypothesis":    SYSTEM_HYP["hypothesis_text"],
                "scores":        {"clarity": 4, "novelty": 4, "feasibility": 4, "total": 12},
                "decision":      "KEEP",
            },
            "agent_b": {
                "hypothesis_id": "HB_G1",
                "hypothesis":    "Alternative approach via ML.",
                "scores":        {"clarity": 3, "novelty": 3, "feasibility": 3, "total": 9},
                "decision":      "REVISE",
            },
            "agreement": False,
        }
    ]


# ─────────────────────────────────────────────────────────────────────────────
# _rule_based_summary
# ─────────────────────────────────────────────────────────────────────────────

class TestRuleBasedSummary:
    def test_returns_expected_keys(self):
        from evaluation.report import _rule_based_summary
        summary = _rule_based_summary(SAMPLE_METRICS)
        assert "strengths"  in summary
        assert "weaknesses" in summary
        assert "conclusion" in summary

    def test_strengths_non_empty(self):
        from evaluation.report import _rule_based_summary
        summary = _rule_based_summary(SAMPLE_METRICS)
        assert len(summary["strengths"]) >= 1

    def test_weaknesses_non_empty(self):
        from evaluation.report import _rule_based_summary
        summary = _rule_based_summary(SAMPLE_METRICS)
        assert len(summary["weaknesses"]) >= 1

    def test_conclusion_is_string(self):
        from evaluation.report import _rule_based_summary
        summary = _rule_based_summary(SAMPLE_METRICS)
        assert isinstance(summary["conclusion"], str) and summary["conclusion"]

    def test_high_win_rate_produces_strength(self):
        from evaluation.report import _rule_based_summary
        high_metrics = MetricsSummary(
            win_rate=0.8, avg_hypothesis_score=8.0,
            keep_rate=0.9, agent_agreement_rate=0.9,
            total_gaps_evaluated=5, total_comparisons_run=15,
        )
        summary = _rule_based_summary(high_metrics)
        combined = " ".join(summary["strengths"])
        assert any(
            "outperform" in s.lower() or "win" in s.lower()
            for s in summary["strengths"]
        ), f"Expected win-related strength. Got: {summary['strengths']}"

    def test_low_win_rate_produces_weakness(self):
        from evaluation.report import _rule_based_summary
        low_metrics = MetricsSummary(
            win_rate=0.2, avg_hypothesis_score=4.0,
            keep_rate=0.1, agent_agreement_rate=0.2,
            total_gaps_evaluated=5, total_comparisons_run=15,
        )
        summary = _rule_based_summary(low_metrics)
        assert len(summary["weaknesses"]) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Full report schema
# ─────────────────────────────────────────────────────────────────────────────

class TestReportSchema:
    def _build_report(self, tmp_path: Path) -> Dict:
        """Build a minimal report using mocked dependencies."""
        from evaluation import report as report_mod

        # Patch: gaps loading
        with patch.object(report_mod, "_load_gaps", return_value=GAPS), \
             patch.object(report_mod, "_load_system_hypotheses",
                          return_value={"G1": SYSTEM_HYP}), \
             patch("evaluation.baseline.run_all_baselines",
                   return_value=[BASELINE_HYP]), \
             patch("evaluation.report.run_all_baselines",
                   return_value=[BASELINE_HYP]), \
             patch("evaluation.report.evaluate_all_gaps",
                   return_value=[SAMPLE_PAIRWISE]), \
             patch("evaluation.report.compute_metrics",
                   return_value=SAMPLE_METRICS), \
             patch("evaluation.report._generate_llm_summary",
                   return_value=SAMPLE_SUMMARY):

            return report_mod.run(
                gaps_path=None,
                baseline_dir=tmp_path / "baseline",
                output_dir=tmp_path / "evaluation",
                n_runs=3,
            )

    def test_report_has_required_top_level_keys(self, tmp_path):
        report = self._build_report(tmp_path)
        for key in ["metadata", "metrics", "per_gap_results", "summary"]:
            assert key in report, f"Missing key: {key}"

    def test_metadata_has_required_fields(self, tmp_path):
        report = self._build_report(tmp_path)
        metadata = report["metadata"]
        for field in ["timestamp", "pipeline_version", "n_runs_per_pair", "total_gaps"]:
            assert field in metadata, f"Missing metadata field: {field}"

    def test_metrics_schema(self, tmp_path):
        report = self._build_report(tmp_path)
        metrics = report["metrics"]
        for field in ["win_rate", "avg_hypothesis_score", "keep_rate",
                      "agent_agreement_rate", "total_gaps_evaluated",
                      "total_comparisons_run"]:
            assert field in metrics, f"Missing metrics field: {field}"

    def test_per_gap_results_is_list(self, tmp_path):
        report = self._build_report(tmp_path)
        assert isinstance(report["per_gap_results"], list)
        assert len(report["per_gap_results"]) >= 1

    def test_summary_has_required_keys(self, tmp_path):
        report = self._build_report(tmp_path)
        summary = report["summary"]
        assert "strengths"  in summary
        assert "weaknesses" in summary
        assert "conclusion" in summary

    def test_summary_non_empty(self, tmp_path):
        report = self._build_report(tmp_path)
        assert report["summary"]["conclusion"]

    def test_file_saved_to_correct_path(self, tmp_path):
        self._build_report(tmp_path)
        expected = tmp_path / "evaluation" / "evaluation_report.json"
        assert expected.exists(), f"Report file not found at {expected}"

    def test_saved_file_is_valid_json(self, tmp_path):
        self._build_report(tmp_path)
        path = tmp_path / "evaluation" / "evaluation_report.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "metrics" in data

    def test_n_runs_preserved_in_metadata(self, tmp_path):
        from evaluation import report as report_mod

        with patch.object(report_mod, "_load_gaps", return_value=GAPS), \
             patch.object(report_mod, "_load_system_hypotheses",
                          return_value={"G1": SYSTEM_HYP}), \
             patch("evaluation.report.run_all_baselines",
                   return_value=[BASELINE_HYP]), \
             patch("evaluation.report.evaluate_all_gaps",
                   return_value=[SAMPLE_PAIRWISE]), \
             patch("evaluation.report.compute_metrics",
                   return_value=SAMPLE_METRICS), \
             patch("evaluation.report._generate_llm_summary",
                   return_value=SAMPLE_SUMMARY):

            report = report_mod.run(
                output_dir=tmp_path / "evaluation",
                n_runs=5,
            )

        assert report["metadata"]["n_runs_per_pair"] == 5
