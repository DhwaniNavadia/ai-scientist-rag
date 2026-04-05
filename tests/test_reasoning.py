"""tests/test_reasoning.py — Unit tests for critic, debate orchestrator, and reflection engine."""

import json
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, List


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_hypothesis(
    hyp_id="H1", gap_id="G1", gap_type="scalability",
    source="AgentA", text="Using decomposition reduces runtime.",
    clarity=4, novelty=4, feasibility=4, decision="KEEP",
) -> Dict:
    total = clarity + novelty + feasibility
    return {
        "hypothesis_id":  hyp_id,
        "gap_id":         gap_id,
        "gap_type":       gap_type,
        "source":         source,
        "hypothesis_text": text,
        "scores": {
            "clarity":     clarity,
            "novelty":     novelty,
            "feasibility": feasibility,
            "total":       total,
        },
        "decision": decision,
    }


# ---------------------------------------------------------------------------
# Critic — fallback on bad JSON
# ---------------------------------------------------------------------------

class TestCritic:
    def test_fallback_on_bad_json(self):
        """When OpenAI returns invalid JSON, default scores should be assigned."""
        from ai_scientist.reasoning import critic

        bad_response = MagicMock()
        bad_response.choices = [MagicMock()]
        bad_response.choices[0].message.content = "not valid json {{{{ broken"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = bad_response

        with patch("ai_scientist.reasoning.critic._get_client", return_value=mock_client):
            result = critic._score_one({
                "hypothesis_id":  "H1",
                "hypothesis_text": "Some hypothesis.",
                "scores": {},
            })

        # Default scores: clarity=3, novelty=3, feasibility=3, total=9
        assert result["scores"]["clarity"]     == 3
        assert result["scores"]["novelty"]     == 3
        assert result["scores"]["feasibility"] == 3
        assert result["scores"]["total"]       == 9
        assert result["decision"]              == "REVISE"

    def test_keep_when_total_gte_10(self):
        """A total score of 12 must produce KEEP regardless of model output."""
        from ai_scientist.reasoning import critic

        good_response = MagicMock()
        good_response.choices = [MagicMock()]
        good_response.choices[0].message.content = json.dumps({
            "clarity": 4, "novelty": 4, "feasibility": 4, "decision": "REJECT",
            "rationale": "test"
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = good_response

        with patch("ai_scientist.reasoning.critic._get_client", return_value=mock_client):
            result = critic._score_one({
                "hypothesis_id":  "H2",
                "hypothesis_text": "Some hypothesis.",
            })

        # total = 12 → KEEP (ignores model's "REJECT")
        assert result["decision"] == "KEEP"

    def test_reject_when_total_lte_5(self):
        from ai_scientist.reasoning import critic

        low_response = MagicMock()
        low_response.choices = [MagicMock()]
        low_response.choices[0].message.content = json.dumps({
            "clarity": 1, "novelty": 1, "feasibility": 1, "decision": "KEEP",
            "rationale": "test"
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = low_response

        with patch("ai_scientist.reasoning.critic._get_client", return_value=mock_client):
            result = critic._score_one({
                "hypothesis_id":  "H3",
                "hypothesis_text": "Weak hypothesis.",
            })

        assert result["decision"] == "REJECT"


# ---------------------------------------------------------------------------
# Debate orchestrator — preferred agent logic
# ---------------------------------------------------------------------------

from ai_scientist.reasoning.debate_orchestrator import pick_preferred, build_disagreement_log


class TestPickPreferred:
    def test_keep_beats_revise(self):
        a = {"decision": "KEEP",   "scores": {"total": 10}}
        b = {"decision": "REVISE", "scores": {"total": 12}}
        assert pick_preferred(a, b) == "AgentA"

    def test_revise_beats_reject(self):
        a = {"decision": "REJECT", "scores": {"total": 4}}
        b = {"decision": "REVISE", "scores": {"total": 8}}
        assert pick_preferred(a, b) == "AgentB"

    def test_same_decision_higher_total_wins(self):
        a = {"decision": "KEEP", "scores": {"total": 11}}
        b = {"decision": "KEEP", "scores": {"total": 14}}
        assert pick_preferred(a, b) == "AgentB"

    def test_tie_breaks_to_agent_a(self):
        a = {"decision": "KEEP", "scores": {"total": 12}}
        b = {"decision": "KEEP", "scores": {"total": 12}}
        assert pick_preferred(a, b) == "AgentA"

    def test_reject_vs_reject_tie(self):
        a = {"decision": "REJECT", "scores": {"total": 3}}
        b = {"decision": "REJECT", "scores": {"total": 3}}
        assert pick_preferred(a, b) == "AgentA"


class TestBuildDisagreementLog:
    def _make_scored_pair(self, gap_id="G1", gap_type="scalability",
                           a_decision="KEEP", b_decision="KEEP",
                           a_total=12, b_total=10):
        return [
            {
                "hypothesis_id": f"HA_{gap_id}",
                "gap_id":        gap_id,
                "gap_type":      gap_type,
                "gap_text":      "Some challenge.",
                "source":        "AgentA",
                "hypothesis_text": "AgentA hypothesis",
                "scores":        {"clarity": 4, "novelty": 4, "feasibility": 4, "total": a_total},
                "decision":      a_decision,
            },
            {
                "hypothesis_id": f"HB_{gap_id}",
                "gap_id":        gap_id,
                "gap_type":      gap_type,
                "gap_text":      "Some challenge.",
                "source":        "AgentB",
                "hypothesis_text": "AgentB hypothesis",
                "scores":        {"clarity": 3, "novelty": 4, "feasibility": 3, "total": b_total},
                "decision":      b_decision,
            },
        ]

    def test_one_entry_per_gap(self):
        scored = self._make_scored_pair("G1") + self._make_scored_pair("G2")
        log = build_disagreement_log(scored)
        assert len(log) == 2

    def test_agreement_true_when_same_decision(self):
        scored = self._make_scored_pair("G1", a_decision="KEEP", b_decision="KEEP")
        log = build_disagreement_log(scored)
        assert log[0]["agreement"] is True

    def test_agreement_false_when_different_decisions(self):
        scored = self._make_scored_pair("G1", a_decision="KEEP", b_decision="REJECT")
        log = build_disagreement_log(scored)
        assert log[0]["agreement"] is False

    def test_preferred_agent_set(self):
        scored = self._make_scored_pair("G1", a_total=12, b_total=10)
        log = build_disagreement_log(scored)
        assert log[0]["preferred_agent"] == "AgentA"

    def test_schema_keys_present(self):
        scored = self._make_scored_pair("G1")
        log = build_disagreement_log(scored)
        entry = log[0]
        for key in ["gap_id", "gap_type", "evidence_text", "agent_a", "agent_b",
                    "preferred_agent", "agreement"]:
            assert key in entry
