"""
tests/test_pdf_extractor.py
Tests for the PDF extractor utility functions.
We test the helper functions that don't require an actual PDF file.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pdf_extractor import estimate_duration, _title_case


# ── Duration estimation ───────────────────────────────────────────────────────

def test_estimate_duration_short_text():
    """Short text of ~150 words should be about 1 minute."""
    text = " ".join(["word"] * 150)   # exactly 150 words
    result = estimate_duration(text, wpm=150)
    assert "1m" in result


def test_estimate_duration_long_text():
    """9000 words at 150 wpm = 60 minutes = 1 hour."""
    text = " ".join(["word"] * 9000)
    result = estimate_duration(text, wpm=150)
    assert "1h" in result


def test_estimate_duration_empty():
    """Empty text should return 0s duration."""
    result = estimate_duration("")
    assert "0s" in result or result == "0s"


def test_estimate_duration_custom_wpm():
    """300 wpm is twice as fast — 300 words should be about 1 minute."""
    text = " ".join(["word"] * 300)
    result = estimate_duration(text, wpm=300)
    assert "1m" in result


# ── Title case helper ─────────────────────────────────────────────────────────

def test_title_case_basic():
    """Basic title case capitalisation."""
    result = _title_case("the wizard of oz")
    assert result == "The Wizard of Oz"


def test_title_case_keeps_small_words_lower():
    """Small words (of, the, and, in) stay lowercase except at start."""
    result = _title_case("a tale of two cities")
    assert result == "A Tale of Two Cities"


def test_title_case_first_word_always_capitalised():
    """First word is always capitalised even if it's a small word."""
    result = _title_case("of mice and men")
    assert result.startswith("Of")


def test_title_case_handles_uppercase_input():
    """ALL CAPS input should be properly title-cased."""
    result = _title_case("THE IRON WIZARD")
    assert result == "The Iron Wizard"
