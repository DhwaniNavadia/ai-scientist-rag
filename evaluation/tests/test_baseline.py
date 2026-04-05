"""evaluation/tests/test_baseline.py — Unit tests for evaluation/baseline.py."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from evaluation.baseline import generate_baseline, run_all_baselines


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

VALID_LLM_RESPONSE = json.dumps({
    "hypothesis":  "Applying convex relaxation to the HSAP will reduce solve time by 40%.",
    "rationale":   "Convex relaxation has proven effective in similarly structured problems.",
    "confidence":  0.78,
})

SAMPLE_GAP = {
    "gap_id":             "G1",
    "gap_text":           "Current methods do not scale to large venues.",
    "actionable_direction": "Investigate scalable decomposition techniques.",
    "gap_type":           "scalability",
    "source_section":     "evaluation",
}


# ─────────────────────────────────────────────────────────────────────────────
# generate_baseline
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateBaseline:
    def test_schema_matches_spec(self, monkeypatch):
        """Returned dict must match the exact baseline output schema."""
        monkeypatch.setattr(
            "evaluation.baseline._chat_complete",
            lambda msgs, **kw: VALID_LLM_RESPONSE,
        )
        result = generate_baseline("G1", "Test gap description")

        assert result["gap_id"]       == "G1"
        assert result["gap_description"] == "Test gap description"
        assert isinstance(result["hypothesis"], str) and result["hypothesis"]
        assert isinstance(result["rationale"],  str) and result["rationale"]
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["generated_by"] == "baseline"
        assert "timestamp" in result and result["timestamp"]

    def test_hypothesis_text_from_llm(self, monkeypatch):
        monkeypatch.setattr(
            "evaluation.baseline._chat_complete",
            lambda msgs, **kw: VALID_LLM_RESPONSE,
        )
        result = generate_baseline("G2", "Scalability gap")
        assert "convex relaxation" in result["hypothesis"].lower()

    def test_confidence_clamped_to_valid_range(self, monkeypatch):
        """Confidence values outside [0,1] returned by the LLM should be clamped."""
        bad_response = json.dumps({"hypothesis": "h", "rationale": "r", "confidence": 1.5})
        monkeypatch.setattr(
            "evaluation.baseline._chat_complete",
            lambda msgs, **kw: bad_response,
        )
        result = generate_baseline("G3", "desc")
        assert result["confidence"] <= 1.0

    def test_fallback_on_invalid_json(self, monkeypatch):
        """If the LLM returns malformed JSON, a fallback hypothesis is generated."""
        monkeypatch.setattr(
            "evaluation.baseline._chat_complete",
            lambda msgs, **kw: "not valid json !!",
        )
        result = generate_baseline("G4", "Some gap")
        assert isinstance(result["hypothesis"], str) and result["hypothesis"]
        assert result["confidence"] == 0.5
        assert result["generated_by"] == "baseline"

    def test_gap_id_preserved(self, monkeypatch):
        monkeypatch.setattr(
            "evaluation.baseline._chat_complete",
            lambda msgs, **kw: VALID_LLM_RESPONSE,
        )
        result = generate_baseline("MY_GAP_ID", "desc")
        assert result["gap_id"] == "MY_GAP_ID"


# ─────────────────────────────────────────────────────────────────────────────
# run_all_baselines
# ─────────────────────────────────────────────────────────────────────────────

class TestRunAllBaselines:
    def test_saves_to_correct_path(self, monkeypatch, tmp_path):
        """Each baseline must be saved as <gap_id>_baseline.json in BASELINE_DIR."""
        import evaluation.baseline as bmod
        monkeypatch.setattr(bmod, "BASELINE_DIR", tmp_path / "baseline")
        monkeypatch.setattr(
            "evaluation.baseline._chat_complete",
            lambda msgs, **kw: VALID_LLM_RESPONSE,
        )

        run_all_baselines([SAMPLE_GAP])

        expected = tmp_path / "baseline" / "G1_baseline.json"
        assert expected.exists(), f"Expected file not found: {expected}"
        data = json.loads(expected.read_text(encoding="utf-8"))
        assert data["gap_id"] == "G1"

    def test_returns_list_of_dicts(self, monkeypatch, tmp_path):
        import evaluation.baseline as bmod
        monkeypatch.setattr(bmod, "BASELINE_DIR", tmp_path / "baseline")
        monkeypatch.setattr(
            "evaluation.baseline._chat_complete",
            lambda msgs, **kw: VALID_LLM_RESPONSE,
        )

        results = run_all_baselines([SAMPLE_GAP])
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], dict)

    def test_loads_cached_result(self, monkeypatch, tmp_path):
        """If a cache file exists, the LLM should NOT be called again."""
        baseline_dir = tmp_path / "baseline"
        baseline_dir.mkdir()

        cached = {
            "gap_id":          "G1",
            "gap_description": "desc",
            "hypothesis":      "Cached hypothesis.",
            "rationale":       "Cached rationale.",
            "confidence":      0.9,
            "generated_by":    "baseline",
            "timestamp":       "2026-01-01T00:00:00+00:00",
        }
        (baseline_dir / "G1_baseline.json").write_text(
            json.dumps(cached), encoding="utf-8"
        )

        import evaluation.baseline as bmod
        monkeypatch.setattr(bmod, "BASELINE_DIR", baseline_dir)

        call_count = [0]
        def spy(msgs, **kw):
            call_count[0] += 1
            return VALID_LLM_RESPONSE

        monkeypatch.setattr("evaluation.baseline._chat_complete", spy)

        results = run_all_baselines([SAMPLE_GAP])

        assert call_count[0] == 0, "LLM should not be called when cache exists"
        assert results[0]["hypothesis"] == "Cached hypothesis."

    def test_empty_gaps_returns_empty_list(self, monkeypatch, tmp_path):
        import evaluation.baseline as bmod
        monkeypatch.setattr(bmod, "BASELINE_DIR", tmp_path / "baseline")
        results = run_all_baselines([])
        assert results == []

    def test_multiple_gaps_all_saved(self, monkeypatch, tmp_path):
        import evaluation.baseline as bmod
        monkeypatch.setattr(bmod, "BASELINE_DIR", tmp_path / "baseline")
        monkeypatch.setattr(
            "evaluation.baseline._chat_complete",
            lambda msgs, **kw: VALID_LLM_RESPONSE,
        )

        gaps = [
            {**SAMPLE_GAP, "gap_id": "G1"},
            {**SAMPLE_GAP, "gap_id": "G2"},
            {**SAMPLE_GAP, "gap_id": "G3"},
        ]
        results = run_all_baselines(gaps)

        assert len(results) == 3
        for gid in ("G1", "G2", "G3"):
            p = tmp_path / "baseline" / f"{gid}_baseline.json"
            assert p.exists(), f"Missing file for {gid}"
