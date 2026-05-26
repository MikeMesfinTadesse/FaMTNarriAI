"""
core/text_cleaner.py
Cleans extracted text so it reads naturally when spoken aloud.
No external dependencies.
"""

import re
import unicodedata


# ── Patterns ──────────────────────────────────────────────────────────── #

_URL_RE = re.compile(
    r"https?://[^\s]+"
    r"|www\.[^\s]+"
    r"|[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Standalone page number lines: "42", "- 42 -", "Page 42", "— 42 —"
_PAGE_NUM_RE = re.compile(
    r"(?m)^\s*[-–—]?\s*(page\s*)?\d{1,4}\s*[-–—]?\s*$",
    re.IGNORECASE,
)

# Running headers/footers — repeated short lines (handled by dedup logic)
_SHORT_LINE_RE = re.compile(r"(?m)^.{1,4}\n")  # lines under 5 chars

# Hyphenation at line breaks: "discov-\nered" → "discovered"
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")

# Multiple blank lines → at most two
_MULTI_BLANK_RE = re.compile(r"\n{3,}")

# Common PDF artifacts
_ARTIFACT_PATTERNS = [
    re.compile(r"\x00"),                        # null bytes
    re.compile(r"\ufffd"),                      # replacement char
    re.compile(r"[\x01-\x08\x0b\x0e-\x1f]"),   # control chars
    re.compile(r"[ \t]{3,}", re.MULTILINE),     # excessive spaces
]

# Roman numerals on their own line (front matter pages)
_ROMAN_PAGE_RE = re.compile(
    r"(?m)^\s*[ivxlcdmIVXLCDM]{1,8}\s*$"
)

# Repeated punctuation artefacts like "......" or "------"
_REPEATED_PUNCT_RE = re.compile(r"([.·\-_=~])\1{4,}")


class TextCleaner:
    """
    Configurable pipeline that removes non-speech elements from text.
    Each step can be toggled via constructor kwargs.
    """

    def __init__(
        self,
        remove_urls: bool = True,
        remove_emails: bool = True,
        remove_page_numbers: bool = True,
        remove_artifacts: bool = True,
        fix_hyphenation: bool = True,
        fix_smart_quotes: bool = True,
        normalize_whitespace: bool = True,
    ):
        self.remove_urls = remove_urls
        self.remove_emails = remove_emails
        self.remove_page_numbers = remove_page_numbers
        self.remove_artifacts = remove_artifacts
        self.fix_hyphenation = fix_hyphenation
        self.fix_smart_quotes = fix_smart_quotes
        self.normalize_whitespace = normalize_whitespace

    # ------------------------------------------------------------------ #

    def clean(self, text: str) -> str:
        """Run the full cleaning pipeline and return cleaned text."""
        if self.fix_smart_quotes:
            text = self._normalise_quotes(text)

        text = self._normalise_unicode(text)

        if self.remove_artifacts:
            text = self._strip_artifacts(text)

        if self.remove_urls or self.remove_emails:
            text = self._strip_urls_emails(text)

        if self.remove_page_numbers:
            text = self._strip_page_numbers(text)

        if self.fix_hyphenation:
            text = self._fix_hyphenation(text)

        if self.normalize_whitespace:
            text = self._normalise_whitespace(text)

        return text.strip()

    # ── Steps ─────────────────────────────────────────────────────────── #

    @staticmethod
    def _normalise_unicode(text: str) -> str:
        """NFC normalise and replace common ligatures."""
        text = unicodedata.normalize("NFC", text)
        ligatures = {
            "\uFB00": "ff", "\uFB01": "fi", "\uFB02": "fl",
            "\uFB03": "ffi", "\uFB04": "ffl",
            "\u2019": "'",  # right single quotation
            "\u2018": "'",  # left  single quotation
            "\u201C": '"',  # left  double quotation
            "\u201D": '"',  # right double quotation
            "\u2013": "–",  # en dash
            "\u2014": "—",  # em dash
            "\u2026": "...",# ellipsis
        }
        for char, replacement in ligatures.items():
            text = text.replace(char, replacement)
        return text

    @staticmethod
    def _normalise_quotes(text: str) -> str:
        """Convert curly/smart quotes to straight ASCII equivalents."""
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u201C", '"').replace("\u201D", '"')
        text = text.replace("\u00AB", '"').replace("\u00BB", '"')
        return text

    @staticmethod
    def _strip_artifacts(text: str) -> str:
        for pat in _ARTIFACT_PATTERNS:
            text = pat.sub(" ", text)
        text = _REPEATED_PUNCT_RE.sub(r"\1\1\1", text)  # shorten to 3
        text = _ROMAN_PAGE_RE.sub("", text)
        return text

    def _strip_urls_emails(self, text: str) -> str:
        """Remove URLs and/or emails based on flags."""
        if self.remove_urls and self.remove_emails:
            return _URL_RE.sub("", text)
        if self.remove_urls:
            return re.sub(r"https?://[^\s]+|www\.[^\s]+", "", text)
        if self.remove_emails:
            return re.sub(r"[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "", text)
        return text

    @staticmethod
    def _strip_page_numbers(text: str) -> str:
        return _PAGE_NUM_RE.sub("", text)

    @staticmethod
    def _fix_hyphenation(text: str) -> str:
        """Rejoin words broken across lines with a hyphen."""
        return _HYPHEN_BREAK_RE.sub(r"\1\2", text)

    @staticmethod
    def _normalise_whitespace(text: str) -> str:
        # Collapse excessive blank lines
        text = _MULTI_BLANK_RE.sub("\n\n", text)
        # Collapse multiple spaces/tabs per line
        lines = []
        for line in text.split("\n"):
            lines.append(re.sub(r"[ \t]+", " ", line).rstrip())
        return "\n".join(lines)


# ── Convenience function ───────────────────────────────────────────────── #

def quick_clean(text: str) -> str:
    """Shorthand: run the default cleaner pipeline on a string."""
    return TextCleaner().clean(text)
