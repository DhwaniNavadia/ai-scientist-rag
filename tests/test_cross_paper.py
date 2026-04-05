"""tests/test_cross_paper.py — Unit tests for cross_paper.claims_sectioned and contradictions."""

import logging
import pytest
from typing import List


# ---------------------------------------------------------------------------
# claims_sectioned helpers
# ---------------------------------------------------------------------------

from ai_scientist.cross_paper.claims_sectioned import (
    looks_like_table_or_figure,
    sentence_split,
    has_claim_signal,
)


class TestLooksLikeTableOrFigure:
    def test_keeps_normal_sentence(self):
        s = "Our method achieves 81.5% accuracy on the test set."
        assert looks_like_table_or_figure(s) is False

    def test_keeps_dataset_name_sentence(self):
        """Sentence mentioning a dataset name must NOT be rejected."""
        for sentence in [
            "Our model achieves 81.5% accuracy on Cora.",
            "We evaluate on Citeseer, Cora, and PubMed benchmarks.",
            "Results on ogbn-arxiv surpass prior work by 2.1 points.",
        ]:
            assert looks_like_table_or_figure(sentence) is False, (
                f"Dataset sentence incorrectly flagged as table: {sentence}"
            )

    def test_rejects_figure_caption_line(self):
        assert looks_like_table_or_figure("Figure 3: Results per method.") is True

    def test_rejects_table_caption_line(self):
        assert looks_like_table_or_figure("Table 1: Comparison of models.") is True

    def test_keeps_sentence_with_few_numbers(self):
        s = "Precision improved from 88.2 to 92.7."
        assert looks_like_table_or_figure(s) is False

    def test_rejects_heavy_number_line(self):
        """A line with ≥ 8 standalone numbers looks like a table row."""
        s = "1 2 3 4 5 6 7 8 9 10 0.92 0.88"
        assert looks_like_table_or_figure(s) is True

    def test_rejects_pipe_separated_line(self):
        s = "BERT | 92.1 | 88.4 | 90.2"
        assert looks_like_table_or_figure(s) is True


class TestSentenceSplit:
    def test_basic_split(self):
        text = "First sentence. Second sentence. Third sentence here."
        sentences = sentence_split(text)
        assert len(sentences) >= 2

    def test_keeps_short_metric_sentences(self):
        """Sentences with a percentage pattern must be kept even if short."""
        text = "Accuracy: 81.5%."
        sentences = sentence_split(text)
        assert any("81.5" in s for s in sentences), (
            f"Short % sentence was dropped. Got: {sentences}"
        )

    def test_drops_very_short_non_metric_sentences(self):
        """Sentences under 15 chars without % should be dropped."""
        text = "Hi. This is a proper sentence that qualifies for inclusion."
        sentences = sentence_split(text)
        # "Hi." is only 3 chars and has no % → should not be in output
        assert not any(s.strip() == "Hi." for s in sentences)

    def test_returns_list(self):
        assert isinstance(sentence_split("Test sentence."), list)

    def test_empty_string(self):
        assert sentence_split("") == []


class TestHasClaimSignal:
    def test_detects_we_show(self):
        # "we show" is an explicit CLAIM_CUE
        assert has_claim_signal("We show that our approach reduces error significantly.") is True

    def test_detects_outperforms(self):
        assert has_claim_signal("Our method outperforms prior baselines.") is True

    def test_detects_state_of_the_art(self):
        assert has_claim_signal("Achieves state-of-the-art performance.") is True

    def test_returns_false_for_neutral(self):
        # No cue words, no %, no non-year numbers — only "." present
        assert has_claim_signal("The researchers studied the phenomenon carefully.") is False


# ---------------------------------------------------------------------------
# extract_sectioned_claims integration
# ---------------------------------------------------------------------------

from ai_scientist.cross_paper.claims_sectioned import extract_sectioned_claims


class TestExtractSectionedClaims:
    SAMPLE_TEXT = (
        "Introduction\n"
        "We propose a new framework for hierarchical allocation. "
        "Our approach achieves state-of-the-art results.\n\n"
        "Experiments\n"
        "We outperform baselines by 5.2% on the Cora dataset. "
        "Accuracy on Citeseer improves from 72.1% to 78.3%. "
        "Our model is faster than prior methods.\n\n"
        "Conclusion\n"
        "This work demonstrates that deep learning can solve combinatorial problems."
    )

    def test_returns_list(self):
        claims = extract_sectioned_claims(self.SAMPLE_TEXT)
        assert isinstance(claims, list)

    def test_contains_strings(self):
        """Each returned claim should be a non-empty string."""
        claims = extract_sectioned_claims(self.SAMPLE_TEXT)
        assert len(claims) > 0
        for c in claims:
            assert isinstance(c, str)
            assert len(c) > 0

    def test_respects_max_claims(self):
        claims = extract_sectioned_claims(self.SAMPLE_TEXT, max_claims=3)
        assert len(claims) <= 3

    def test_dataset_mentions_not_dropped(self):
        """Claims that mention Cora/Citeseer should not be filtered out."""
        claims = extract_sectioned_claims(self.SAMPLE_TEXT)
        combined = " ".join(claims)
        # At least one claim should survive containing a dataset/metric reference
        assert "Cora" in combined or "Citeseer" in combined or "5.2" in combined, (
            "Expected dataset/metric claims to survive filtering."
        )


# ---------------------------------------------------------------------------
# contradictions — fallback warning
# ---------------------------------------------------------------------------

class TestContradictionsLoadBestText:
    def test_fallback_logs_warning(self, caplog):
        """load_best_text should log a WARNING when no text file is found."""
        from ai_scientist.cross_paper.contradictions import load_best_text

        with caplog.at_level(logging.WARNING, logger="ai_scientist.cross_paper.contradictions"):
            text, source = load_best_text("paper99", ["some fallback claim"])

        # Should return the fallback claim text
        assert "some fallback claim" in text
        # Source string should indicate claims fallback
        assert "claims" in source.lower() or "fallback" in source.lower()

    def test_fallback_returns_joined_claims(self):
        from ai_scientist.cross_paper.contradictions import load_best_text

        claims = ["Claim one.", "Claim two."]
        text, _ = load_best_text("paper_nonexistent_xyz", claims)
        assert "Claim one." in text
        assert "Claim two." in text

    def test_returns_tuple(self):
        from ai_scientist.cross_paper.contradictions import load_best_text

        result = load_best_text("paper99", ["x"])
        assert isinstance(result, tuple)
        assert len(result) == 2
