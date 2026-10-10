"""
tests/test_text_cleaner.py
═══════════════════════════════════════════════════════════════

WHAT ARE TESTS?
    Tests are small Python scripts that check your code works correctly.
    You write a test once. Then every time you change the code, you run
    the tests. If a test fails, you know exactly what broke.

WHY WRITE TESTS?
    Without tests: you change one thing and accidentally break another.
    With tests: Python catches the break immediately and tells you.

HOW TO RUN:
    pip install pytest
    pytest tests/

HOW TO READ A TEST:
    def test_something():
        result = the_function_you_are_testing(input)
        assert result == expected_output   ← "assert" means "check that"

    If the assert fails → pytest shows you what was expected vs what happened.
═══════════════════════════════════════════════════════════════
"""

import sys
from pathlib import Path

# Add the project root to sys.path so we can import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.text_cleaner import TextCleaner, quick_clean


# ── Setup ────────────────────────────────────────────────────────────────────
# Create one cleaner instance used across all tests
cleaner = TextCleaner()


# ── URL removal tests ─────────────────────────────────────────────────────────

def test_removes_http_urls():
    """URLs starting with http:// should be removed."""
    text = "Visit https://example.com for more information."
    result = cleaner.clean(text)
    assert "https://example.com" not in result
    assert "Visit" in result
    assert "for more information" in result


def test_removes_www_urls():
    """URLs starting with www. should be removed."""
    text = "Check www.google.com for details."
    result = cleaner.clean(text)
    assert "www.google.com" not in result


def test_keeps_text_when_url_removed():
    """After removing a URL, surrounding text should still be there."""
    text = "Read the guide at https://docs.python.org to learn more."
    result = cleaner.clean(text)
    assert "Read the guide at" in result
    assert "to learn more" in result


# ── Email removal tests ───────────────────────────────────────────────────────

def test_removes_email_addresses():
    """Email addresses should be removed from text."""
    text = "Contact us at support@narraai.com for help."
    result = cleaner.clean(text)
    assert "support@narraai.com" not in result
    assert "Contact us at" in result


# ── Page number removal tests ─────────────────────────────────────────────────

def test_removes_standalone_page_numbers():
    """Lines containing only a number (page markers) should be removed."""
    text = "Chapter text here.\n42\nMore text follows."
    result = cleaner.clean(text)
    # The lone "42" on its own line should be gone
    lines = [line.strip() for line in result.split("\n") if line.strip()]
    assert "42" not in lines


def test_removes_page_with_dashes():
    """Page markers like '- 42 -' should be removed."""
    text = "End of chapter.\n- 42 -\nNext chapter begins."
    result = cleaner.clean(text)
    assert "- 42 -" not in result


def test_keeps_numbers_in_sentences():
    """Numbers that are part of a sentence should NOT be removed."""
    text = "There were 42 students in the class."
    result = cleaner.clean(text)
    assert "42" in result


# ── Hyphenation fix tests ─────────────────────────────────────────────────────

def test_fixes_hyphenated_line_breaks():
    """
    PDF line breaks often split words like:
      'discov-
       ered'
    These should become 'discovered'.
    """
    text = "She had discov-\nered the truth."
    result = cleaner.clean(text)
    assert "discovered" in result
    assert "discov-" not in result


# ── Whitespace normalisation tests ────────────────────────────────────────────

def test_collapses_multiple_spaces():
    """Multiple spaces in a row should become one space."""
    text = "The   quick   brown   fox."
    result = cleaner.clean(text)
    assert "   " not in result
    assert "The quick brown fox" in result


def test_collapses_excessive_blank_lines():
    """More than 2 consecutive blank lines should become 2."""
    text = "Paragraph one.\n\n\n\n\nParagraph two."
    result = cleaner.clean(text)
    # Should not have 3+ consecutive newlines
    assert "\n\n\n" not in result


# ── Toggle options tests ──────────────────────────────────────────────────────

def test_can_disable_url_removal():
    """When remove_urls=False, URLs should stay in the text."""
    cleaner_no_url = TextCleaner(remove_urls=False)
    text = "Visit https://example.com for info."
    result = cleaner_no_url.clean(text)
    assert "https://example.com" in result


def test_can_disable_email_removal():
    """When remove_emails=False, emails should stay in the text."""
    cleaner_no_email = TextCleaner(remove_emails=False)
    text = "Email us at hello@example.com."
    result = cleaner_no_email.clean(text)
    assert "hello@example.com" in result


# ── quick_clean convenience function ─────────────────────────────────────────

def test_quick_clean_works():
    """quick_clean() is a shorthand — should clean URLs and emails."""
    text = "Go to http://example.com or email info@example.com."
    result = quick_clean(text)
    assert "http://example.com" not in result
    assert "info@example.com" not in result


def test_quick_clean_preserves_content():
    """quick_clean() should not delete actual story content."""
    text = "Once upon a time, in a land far away, there lived a dragon."
    result = quick_clean(text)
    assert "Once upon a time" in result
    assert "dragon" in result


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_string_returns_empty():
    """Cleaning an empty string should return an empty string."""
    assert cleaner.clean("") == ""


def test_clean_text_unchanged():
    """Text with no URLs, emails, or page numbers should be unchanged."""
    text = "The old wizard raised his hand toward the sky."
    result = cleaner.clean(text)
    assert "wizard" in result
    assert "sky" in result


def test_arabic_text_preserved():
    """Arabic text should pass through the cleaner without corruption."""
    text = "مرحباً بكم في تطبيق نارا للكتب الصوتية."
    result = cleaner.clean(text)
    assert "مرحباً" in result


def test_amharic_text_preserved():
    """Amharic text should pass through the cleaner without corruption."""
    text = "ወደ NarraAI እንኳን ደህና መጡ።"
    result = cleaner.clean(text)
    assert "NarraAI" in result
