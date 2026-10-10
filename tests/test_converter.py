"""
tests/test_converter.py
Tests for the converter module — chunking, filenames, speed conversion.
These test the pure logic functions (no network calls to Edge-TTS needed).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.converter import (
    _clean_for_tts,
    _split_into_chunks,
    _speed_to_rate,
    voice_short_name,
    _safe_str,
)


# ── Text cleaning ─────────────────────────────────────────────────────────────

def test_clean_removes_emotion_tags():
    """NarraAI emotion tags should be stripped before TTS."""
    text = "(whisper) She leaned close. (pause) Nothing."
    result = _clean_for_tts(text)
    assert "(whisper)" not in result
    assert "(pause)" not in result
    assert "She leaned close" in result


def test_clean_removes_character_tags():
    """[Character: "dialogue"] markers keep the dialogue, drop the tag."""
    text = '[Wizard: "You shall not pass."]'
    result = _clean_for_tts(text)
    assert "[Wizard:" not in result
    assert "You shall not pass" in result


def test_clean_fixes_soft_wraps():
    """Lines not ending in punctuation should join with a space."""
    text = "She walked through the\nforest slowly."
    result = _clean_for_tts(text)
    # Should become one line
    assert "through the forest" in result


def test_clean_preserves_paragraph_breaks():
    """Double newlines (paragraph breaks) should be preserved."""
    text = "Paragraph one.\n\nParagraph two."
    result = _clean_for_tts(text)
    assert "\n\n" in result


def test_clean_empty_string():
    """Empty string input should return empty string."""
    assert _clean_for_tts("") == ""


# ── Chunking ──────────────────────────────────────────────────────────────────

def test_split_short_text_single_chunk():
    """Text shorter than max_chars should return one chunk."""
    text = "Once upon a time there was a dragon."
    chunks = _split_into_chunks(text, max_chars=500)
    assert len(chunks) == 1
    assert chunks[0] == text.strip()


def test_split_long_text_multiple_chunks():
    """Text longer than max_chars should be split into multiple chunks."""
    # Create text that is definitely longer than 100 chars
    text = "The dragon roared. " * 20   # 380+ chars
    chunks = _split_into_chunks(text, max_chars=100)
    assert len(chunks) > 1


def test_split_never_exceeds_max_chars():
    """Every chunk must be <= max_chars characters."""
    text = "The dragon roared loudly across the valley. " * 50
    max_chars = 200
    chunks = _split_into_chunks(text, max_chars=max_chars)
    for i, chunk in enumerate(chunks):
        assert len(chunk) <= max_chars, (
            f"Chunk {i} has {len(chunk)} chars, exceeds limit of {max_chars}"
        )


def test_split_no_empty_chunks():
    """The chunker should never produce empty strings."""
    text = "Short sentence. Another one. And one more."
    chunks = _split_into_chunks(text)
    for chunk in chunks:
        assert chunk.strip() != "", "Found empty chunk"


def test_split_preserves_all_content():
    """All words in the original text should appear in the chunks."""
    text = "The quick brown fox jumps over the lazy dog."
    chunks = _split_into_chunks(text, max_chars=20)
    combined = " ".join(chunks)
    # Every word from the original should be somewhere in the output
    for word in ["quick", "brown", "fox", "lazy", "dog"]:
        assert word in combined, f"Word '{word}' lost during chunking"


def test_split_empty_text():
    """Empty text should return empty list."""
    assert _split_into_chunks("") == []


def test_split_whitespace_only():
    """Whitespace-only text should return empty list."""
    assert _split_into_chunks("   \n\n   ") == []


# ── Speed to rate conversion ──────────────────────────────────────────────────

def test_speed_normal_is_zero_percent():
    """1.0x speed = +0% rate."""
    assert _speed_to_rate(1.0) == "+0%"


def test_speed_faster():
    """1.5x speed = +50% rate."""
    assert _speed_to_rate(1.5) == "+50%"


def test_speed_slower():
    """0.8x speed = -20% rate."""
    assert _speed_to_rate(0.8) == "-20%"


def test_speed_double():
    """2.0x speed = +100% rate."""
    assert _speed_to_rate(2.0) == "+100%"


def test_speed_half():
    """0.5x speed = -50% rate."""
    assert _speed_to_rate(0.5) == "-50%"


# ── Voice short name ──────────────────────────────────────────────────────────

def test_voice_short_name_standard():
    """Extract short name from standard Edge-TTS voice ID."""
    assert voice_short_name("en-US-AriaNeural") == "Aria"


def test_voice_short_name_gb():
    """Works for non-US voices too."""
    assert voice_short_name("en-GB-SoniaNeural") == "Sonia"


def test_voice_short_name_arabic():
    """Works for Arabic voices."""
    assert voice_short_name("ar-SA-ZariyahNeural") == "Zariyah"


def test_voice_short_name_amharic():
    """Works for Amharic voices."""
    assert voice_short_name("am-ET-MekdesNeural") == "Mekdes"


# ── Safe filename string ──────────────────────────────────────────────────────

def test_safe_str_removes_slashes():
    """Filenames cannot contain forward or backslashes."""
    result = _safe_str("my/file\\name")
    assert "/" not in result
    assert "\\" not in result


def test_safe_str_replaces_spaces():
    """Spaces become underscores in filenames."""
    result = _safe_str("The Iron Wizard")
    assert " " not in result
    assert "_" in result


def test_safe_str_respects_max_len():
    """Output should not exceed max_len characters."""
    long_title = "A" * 100
    result = _safe_str(long_title, max_len=40)
    assert len(result) <= 40


def test_safe_str_removes_special_chars():
    """Characters like <, >, :, ", *, ? should be removed."""
    result = _safe_str('My "Book": Part <1>')
    for char in ['<', '>', ':', '"', '*', '?']:
        assert char not in result
