"""tests/test_extraction.py — Unit tests for claim extractor and gap detector."""

import pytest
from typing import Dict, List


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sections(**kwargs: str) -> Dict[str, str]:
    defaults = {"abstract": "", "introduction": "", "evaluation": "", "conclusion": ""}
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# extract_claims
# ---------------------------------------------------------------------------

from ai_scientist.extraction.claim_extractor import extract_claims


class TestExtractClaims:
    def test_returns_list(self):
        sections = make_sections(
            introduction="We propose a novel method for X. It achieves 95% accuracy."
        )
        result = extract_claims(sections)
        assert isinstance(result, list)

    def test_detects_proposal_sentence(self):
        sections = make_sections(
            introduction="We propose an end-to-end framework."
        )
        claims = extract_claims(sections)
        assert len(claims) >= 1
        assert any("framework" in c["claim_text"].lower() for c in claims)

    def test_claim_schema(self):
        sections = make_sections(
            abstract=(
                "We introduce AutoML for time series. "
                "Our approach achieves state-of-the-art results."
            )
        )
        claims = extract_claims(sections)
        for c in claims:
            assert "claim_id"     in c
            assert "section"      in c
            assert "claim_text"   in c
            assert "evidence_text" in c
            assert "confidence"   in c

    def test_sequential_claim_ids(self):
        sections = make_sections(
            introduction=(
                "We propose method A. We develop technique B. We introduce framework C."
            )
        )
        claims = extract_claims(sections)
        ids = [c["claim_id"] for c in claims]
        assert ids == [f"C{i+1}" for i in range(len(ids))]

    def test_quantitative_confidence_higher(self):
        sections = make_sections(
            evaluation="We achieve 92.3% accuracy on the benchmark."
        )
        claims = extract_claims(sections)
        if claims:
            assert claims[0]["confidence"] == 0.9

    def test_non_quantitative_confidence_lower(self):
        sections = make_sections(
            conclusion="We propose a new framework for analysis."
        )
        claims = extract_claims(sections)
        if claims:
            assert claims[0]["confidence"] == 0.75

    def test_max_ten_claims(self):
        many_sentences = " ".join(
            [f"We propose method number {i}." for i in range(20)]
        )
        sections = make_sections(introduction=many_sentences)
        claims = extract_claims(sections)
        assert len(claims) <= 10

    def test_empty_sections_returns_empty(self):
        sections = make_sections()
        claims = extract_claims(sections)
        assert claims == []


# ---------------------------------------------------------------------------
# detect_gaps
# ---------------------------------------------------------------------------

from ai_scientist.extraction.gap_detector import detect_gaps

FAKE_SECTIONS_WITH_GAPS = make_sections(
    introduction=(
        "This is a scalability challenge for large-scale instances. "
        "Unfortunately the method does not handle noisy data. "
        "Despite progress, manually adjusting parameters remains difficult. "
        "Future work should address the human alignment problem."
    ),
    conclusion=(
        "There are limitations in the approach for large real-world deployment. "
        "This problem remains unclear and hard to solve."
    ),
)


class TestDetectGaps:
    def test_returns_both_lists(self):
        raw, actionable = detect_gaps(FAKE_SECTIONS_WITH_GAPS)
        assert isinstance(raw, list)
        assert isinstance(actionable, list)

    def test_raw_not_empty(self):
        raw, _ = detect_gaps(FAKE_SECTIONS_WITH_GAPS)
        assert len(raw) >= 1

    def test_actionable_not_empty(self):
        _, actionable = detect_gaps(FAKE_SECTIONS_WITH_GAPS)
        assert len(actionable) >= 1

    def test_gap_ids_sequential(self):
        _, actionable = detect_gaps(FAKE_SECTIONS_WITH_GAPS)
        ids = [g["gap_id"] for g in actionable]
        assert ids == [f"G{i+1}" for i in range(len(ids))]

    def test_gap_schema(self):
        _, actionable = detect_gaps(FAKE_SECTIONS_WITH_GAPS)
        for g in actionable:
            assert "gap_id"              in g
            assert "gap_type"            in g
            assert "gap_text"            in g
            assert "source_section"      in g
            assert "actionable_direction" in g

    def test_gap_type_assigned(self):
        _, actionable = detect_gaps(FAKE_SECTIONS_WITH_GAPS)
        valid_types = {"data_quality", "human_alignment", "scalability", "manual_effort"}
        for g in actionable:
            assert g["gap_type"] in valid_types

    def test_max_sixteen_gaps(self):
        long_text = " ".join(
            [f"However limitation number {i} remains unclear." for i in range(30)]
        )
        sections = make_sections(introduction=long_text)
        _, actionable = detect_gaps(sections)
        assert len(actionable) <= 16

    def test_deduplication(self):
        # Two near-identical sentences should collapse to one
        dup_text = (
            "Unfortunately the system does not scale to large instances. "
            "Unfortunately the system does not scale to large instances well."
        )
        sections = make_sections(introduction=dup_text)
        _, actionable = detect_gaps(sections)
        assert len(actionable) <= 1
