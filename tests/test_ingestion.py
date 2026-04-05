"""tests/test_ingestion.py — Unit tests for PDF parser."""

import re
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Import helpers under test
# ---------------------------------------------------------------------------

from ai_scientist.ingestion.pdf_parser import (
    _is_page_number,
    _detect_heading,
    parse_pdf,
)


# ---------------------------------------------------------------------------
# _is_page_number
# ---------------------------------------------------------------------------

class TestIsPageNumber:
    def test_single_digit(self):
        assert _is_page_number("1")

    def test_multi_digit(self):
        assert _is_page_number("  42  ")

    def test_not_page_number_text(self):
        assert not _is_page_number("Introduction")

    def test_not_page_number_mixed(self):
        assert not _is_page_number("Page 3")

    def test_empty_string(self):
        assert not _is_page_number("")


# ---------------------------------------------------------------------------
# _detect_heading
# ---------------------------------------------------------------------------

class TestDetectHeading:
    def test_plain_abstract(self):
        assert _detect_heading("Abstract") == "abstract"

    def test_plain_introduction(self):
        assert _detect_heading("Introduction") == "introduction"

    def test_numbered_introduction(self):
        assert _detect_heading("2 Introduction") == "introduction"

    def test_numbered_evaluation(self):
        assert _detect_heading("4 Evaluation") == "evaluation"

    def test_numbered_conclusion(self):
        assert _detect_heading("5 Conclusion") == "conclusion"

    def test_framework_maps_to_introduction(self):
        assert _detect_heading("3 Framework") == "introduction"

    def test_references_skipped(self):
        assert _detect_heading("References") == "__skip__"

    def test_appendix_skipped(self):
        assert _detect_heading("7 Appendix") == "__skip__"

    def test_subsection_not_heading(self):
        # "2.1 Related Problems" should NOT trigger a section change
        assert _detect_heading("2.1 Related Problems") is None

    def test_ordinary_sentence_not_heading(self):
        assert _detect_heading("We propose a new approach.") is None

    def test_standalone_number_with_next_line_intro(self):
        assert _detect_heading("2", "Introduction") == "introduction"

    def test_standalone_number_with_next_line_skip(self):
        assert _detect_heading("7", "References") == "__skip__"

    def test_conclusion_variant(self):
        assert _detect_heading("Conclusions") == "conclusion"


# ---------------------------------------------------------------------------
# parse_pdf — integration test (only runs when paper1.pdf exists)
# ---------------------------------------------------------------------------

PAPER1 = Path("data/papers/paper1.pdf")


@pytest.mark.skipif(not PAPER1.exists(), reason="paper1.pdf not present")
class TestParsePdf:
    def test_returns_four_sections(self):
        from ai_scientist.ingestion.pdf_parser import parse_pdf
        sections = parse_pdf(PAPER1)
        assert set(sections.keys()) == {"abstract", "introduction", "evaluation", "conclusion"}

    def test_no_empty_sections(self):
        from ai_scientist.ingestion.pdf_parser import parse_pdf
        sections = parse_pdf(PAPER1)
        for name, text in sections.items():
            assert text.strip(), f"Section '{name}' is empty"

    def test_no_isolated_page_numbers(self):
        """Section text must not contain stand-alone digit-only lines."""
        from ai_scientist.ingestion.pdf_parser import parse_pdf
        sections = parse_pdf(PAPER1)
        for name, text in sections.items():
            for line in text.splitlines():
                assert not re.match(r"^\s*\d{1,4}\s*$", line), (
                    f"Page number found in section '{name}': {line!r}"
                )
