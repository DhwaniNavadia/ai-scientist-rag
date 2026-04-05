"""evaluation/tests/test_judge.py — Unit tests for evaluation/judge.py."""

import json
import pytest
from unittest.mock import MagicMock, patch

from evaluation.judge import judge, _parse_judge_response


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_HYP = {"hypothesis_text": "Using hierarchical decomposition reduces scheduling complexity."}
BASELINE_HYP = {"hypothesis": "A greedy heuristic will produce near-optimal seating assignments."}
GAP_DESC = "Current methods do not scale to large venue sizes."

VALID_JUDGE_JSON = {
    "winner":         "system",
    "system_score":   7.5,
    "baseline_score": 5.0,
    "reasoning":      "System hypothesis is more specific and testable.",
    "keep_system":    True,
}


# ─────────────────────────────────────────────────────────────────────────────
# _parse_judge_response
# ─────────────────────────────────────────────────────────────────────────────

class TestParseJudgeResponse:
    def test_valid_json_parsed_correctly(self):
        raw = json.dumps(VALID_JUDGE_JSON)
        result = _parse_judge_response(raw)
        assert result["winner"]         == "system"
        assert result["system_score"]   == 7.5
        assert result["baseline_score"] == 5.0
        assert result["keep_system"]    is True
        assert isinstance(result["reasoning"], str)

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps(VALID_JUDGE_JSON) + "\n```"
        result = _parse_judge_response(raw)
        assert result["winner"] == "system"

    def test_raises_value_error_on_invalid_json(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            _parse_judge_response("not valid json at all {{ broken")

    def test_raises_value_error_on_missing_fields(self):
        incomplete = {"winner": "system", "system_score": 7.0}
        with pytest.raises(ValueError, match="missing required fields"):
            _parse_judge_response(json.dumps(incomplete))

    def test_raises_value_error_on_bad_winner(self):
        bad = {**VALID_JUDGE_JSON, "winner": "neither"}
        with pytest.raises(ValueError, match="Invalid winner"):
            _parse_judge_response(json.dumps(bad))

    def test_all_valid_winner_values(self):
        for winner in ("system", "baseline", "tie"):
            data = {**VALID_JUDGE_JSON, "winner": winner}
            result = _parse_judge_response(json.dumps(data))
            assert result["winner"] == winner


# ─────────────────────────────────────────────────────────────────────────────
# judge() — end-to-end with mocked LLM
# ─────────────────────────────────────────────────────────────────────────────

class TestJudge:
    def test_valid_response_returned(self, monkeypatch):
        """judge() should parse and return a valid response dict."""
        monkeypatch.setattr(
            "evaluation.judge._call_judge_api",
            lambda user_message: json.dumps(VALID_JUDGE_JSON),
        )
        result = judge(SYSTEM_HYP, BASELINE_HYP, GAP_DESC)
        assert result["winner"]       == "system"
        assert result["system_score"] == 7.5
        assert result["keep_system"]  is True

    def test_retry_on_api_failure(self, monkeypatch):
        """judge() should retry and succeed if the first two calls raise."""
        call_count = [0]

        def flaky_api(user_message: str) -> str:
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("Simulated transient API error")
            return json.dumps(VALID_JUDGE_JSON)

        monkeypatch.setattr("evaluation.judge._call_judge_api", flaky_api)
        monkeypatch.setattr("evaluation.judge.time.sleep", lambda _: None)

        result = judge(SYSTEM_HYP, BASELINE_HYP, GAP_DESC, max_retries=3)
        assert call_count[0]    == 3
        assert result["winner"] == "system"

    def test_raises_value_error_after_all_retries_fail(self, monkeypatch):
        """judge() should raise ValueError when every attempt returns bad JSON."""
        monkeypatch.setattr(
            "evaluation.judge._call_judge_api",
            lambda user_message: "not json at all",
        )
        monkeypatch.setattr("evaluation.judge.time.sleep", lambda _: None)

        with pytest.raises(ValueError):
            judge(SYSTEM_HYP, BASELINE_HYP, GAP_DESC, max_retries=2)

    def test_raises_value_error_after_persistent_api_errors(self, monkeypatch):
        """judge() should raise ValueError when API always raises an exception."""
        monkeypatch.setattr(
            "evaluation.judge._call_judge_api",
            lambda user_message: (_ for _ in ()).throw(RuntimeError("always fails")),
        )
        monkeypatch.setattr("evaluation.judge.time.sleep", lambda _: None)

        with pytest.raises(ValueError):
            judge(SYSTEM_HYP, BASELINE_HYP, GAP_DESC, max_retries=1)

    def test_uses_hypothesis_text_field(self, monkeypatch):
        """judge() should read 'hypothesis_text' from system_hyp."""
        seen_messages: list = []

        def capture_api(user_message: str) -> str:
            seen_messages.append(user_message)
            return json.dumps(VALID_JUDGE_JSON)

        monkeypatch.setattr("evaluation.judge._call_judge_api", capture_api)
        judge({"hypothesis_text": "My system hypothesis."}, BASELINE_HYP, GAP_DESC)
        assert "My system hypothesis." in seen_messages[0]

    def test_falls_back_to_hypothesis_field(self, monkeypatch):
        """judge() should fall back to 'hypothesis' if 'hypothesis_text' is absent."""
        seen_messages: list = []

        def capture_api(user_message: str) -> str:
            seen_messages.append(user_message)
            return json.dumps(VALID_JUDGE_JSON)

        monkeypatch.setattr("evaluation.judge._call_judge_api", capture_api)
        judge({"hypothesis": "Fallback text."}, BASELINE_HYP, GAP_DESC)
        assert "Fallback text." in seen_messages[0]

    def test_baseline_wins_result(self, monkeypatch):
        baseline_win = {**VALID_JUDGE_JSON, "winner": "baseline", "keep_system": False,
                        "system_score": 4.0, "baseline_score": 8.0}
        monkeypatch.setattr(
            "evaluation.judge._call_judge_api",
            lambda user_message: json.dumps(baseline_win),
        )
        result = judge(SYSTEM_HYP, BASELINE_HYP, GAP_DESC)
        assert result["winner"]      == "baseline"
        assert result["keep_system"] is False
