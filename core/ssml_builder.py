"""
core/ssml_builder.py
Converts plain text with NarraAI emotion tags into SSML for Edge-TTS.

Supported inline tags (case-insensitive):
  (whisper)   (shout)   (excited)  (sad)   (dramatic)
  (gentle)    (pause)   (slow)     (fast)  (emphasis)

Character voice markers (for multi-voice mode):
  [Wizard: "Hello, traveller."]
  [Child: She stepped back.]
"""

import re
import xml.sax.saxutils as sax
from dataclasses import dataclass, field
from typing import Optional


# ── Emotion → SSML mapping ─────────────────────────────────────────────── #

@dataclass
class EmotionStyle:
    rate: Optional[str] = None      # x-slow slow medium fast x-fast
    pitch: Optional[str] = None     # x-low low medium high x-high
    volume: Optional[str] = None    # silent x-soft soft medium loud x-loud
    style: Optional[str] = None     # Azure neural style name (if supported)
    emphasis: Optional[str] = None  # strong / moderate / reduced


EMOTIONS: dict[str, EmotionStyle] = {
    "whisper":   EmotionStyle(rate="slow",    volume="soft",   pitch="low"),
    "shout":     EmotionStyle(rate="fast",    volume="x-loud", pitch="high",   emphasis="strong"),
    "excited":   EmotionStyle(rate="fast",    pitch="high",    volume="loud"),
    "sad":       EmotionStyle(rate="x-slow",  pitch="x-low",   volume="soft"),
    "dramatic":  EmotionStyle(rate="slow",    pitch="low",     volume="loud"),
    "gentle":    EmotionStyle(rate="slow",    pitch="medium",  volume="soft"),
    "slow":      EmotionStyle(rate="x-slow"),
    "fast":      EmotionStyle(rate="x-fast"),
    "emphasis":  EmotionStyle(emphasis="strong"),
    "pause":     None,   # handled specially → <break>
}

PAUSE_DURATION = "700ms"

# Inline tag pattern:  (whisper)  or  (Sad)  or  (SHOUT)
_TAG_RE = re.compile(r"\((\w+)\)", re.IGNORECASE)

# Character voice line: [WizardName: "Text goes here."]
_CHAR_RE = re.compile(r"\[([^\]:]+):\s*(.+?)\]", re.DOTALL)


# ── Builder ────────────────────────────────────────────────────────────── #

class SSMLBuilder:
    """
    Converts plain text (with optional NarraAI tags) into an SSML document
    ready to pass to Edge-TTS.
    """

    def __init__(
        self,
        voice: str = "en-US-AriaNeural",
        speed: float = 1.0,
        pitch_shift: int = 0,
        character_voices: Optional[dict[str, str]] = None,
    ):
        """
        Args:
            voice:            Default Edge-TTS voice name.
            speed:            Global speed multiplier (0.5–2.0).
            pitch_shift:      Global pitch offset in semitones (-12 to +12).
            character_voices: {"CharacterName": "VoiceName"} for multi-voice.
        """
        self.voice = voice
        self.speed = max(0.5, min(2.0, speed))
        self.pitch_shift = max(-12, min(12, pitch_shift))
        self.character_voices = character_voices or {}

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def build(self, text: str) -> str:
        """Return a complete SSML document string."""
        inner = self._process_text(text)
        rate_val = self._speed_to_rate_pct(self.speed)
        pitch_val = f"{self.pitch_shift:+d}st" if self.pitch_shift != 0 else "+0st"

        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<speak version="1.0" '
            'xmlns="http://www.w3.org/2001/10/synthesis" '
            'xmlns:mstts="https://www.w3.org/2001/mstts" '
            'xml:lang="en-US">\n'
            f'  <voice name="{self.voice}">\n'
            f'    <prosody rate="{rate_val}" pitch="{pitch_val}">\n'
            f"{inner}\n"
            "    </prosody>\n"
            "  </voice>\n"
            "</speak>"
        )

    def build_preview(self, text: str, max_chars: int = 500) -> str:
        """Build SSML for a short preview snippet."""
        snippet = text[:max_chars].rsplit(" ", 1)[0]  # cut at word boundary
        return self.build(snippet)

    # ------------------------------------------------------------------ #
    #  Internal processing                                                 #
    # ------------------------------------------------------------------ #

    def _process_text(self, text: str) -> str:
        """Walk through the text and emit SSML segments."""
        # First handle character voice blocks
        if self.character_voices:
            text = self._inject_character_voices(text)

        segments = self._tokenise(text)
        return "".join(segments)

    def _tokenise(self, text: str) -> list[str]:
        """
        Split text at emotion tags and produce SSML fragments.
        Returns list of XML-safe strings.
        """
        result: list[str] = []
        active_style: Optional[EmotionStyle] = None
        pos = 0

        for m in _TAG_RE.finditer(text):
            tag_name = m.group(1).lower()

            # Flush text before this tag
            chunk = text[pos : m.start()]
            if chunk:
                result.append(self._wrap_style(sax.escape(chunk), active_style))

            pos = m.end()

            if tag_name == "pause":
                result.append(f'<break time="{PAUSE_DURATION}"/>')
                active_style = None
            elif tag_name in EMOTIONS:
                active_style = EMOTIONS[tag_name]
            else:
                # Unknown tag — output literally as text
                result.append(sax.escape(m.group(0)))

        # Tail text after last tag
        tail = text[pos:]
        if tail:
            result.append(self._wrap_style(sax.escape(tail), active_style))

        return result

    @staticmethod
    def _wrap_style(text: str, style: Optional[EmotionStyle]) -> str:
        """Wrap a text chunk in <prosody> and/or <emphasis> based on style."""
        if not style or not text.strip():
            return text

        inner = text
        if style.emphasis:
            inner = f'<emphasis level="{style.emphasis}">{inner}</emphasis>'

        attrs = []
        if style.rate:
            attrs.append(f'rate="{style.rate}"')
        if style.pitch:
            attrs.append(f'pitch="{style.pitch}"')
        if style.volume:
            attrs.append(f'volume="{style.volume}"')

        if attrs:
            inner = f'<prosody {" ".join(attrs)}>{inner}</prosody>'

        return inner

    def _inject_character_voices(self, text: str) -> str:
        """
        Replace [CharacterName: "..."] blocks with <voice> switch SSML.
        Characters not found in the map use the default voice.
        """
        def replacer(m: re.Match) -> str:
            char_name = m.group(1).strip()
            char_text = m.group(2).strip()
            voice = self.character_voices.get(char_name, self.voice)
            escaped = sax.escape(char_text)
            if voice == self.voice:
                return escaped
            return (
                f'    </prosody>\n  </voice>\n'
                f'  <voice name="{voice}">\n    <prosody>\n'
                f"      {escaped}\n"
                f'    </prosody>\n  </voice>\n'
                f'  <voice name="{self.voice}">\n    <prosody>\n'
            )

        return _CHAR_RE.sub(replacer, text)

    @staticmethod
    def _speed_to_rate_pct(speed: float) -> str:
        """Convert a float multiplier to an SSML-compatible rate percentage string."""
        pct = int((speed - 1.0) * 100)
        if pct == 0:
            return "medium"
        sign = "+" if pct > 0 else ""
        return f"{sign}{pct}%"


# ── Convenience ───────────────────────────────────────────────────────── #

def text_to_ssml(
    text: str,
    voice: str = "en-US-AriaNeural",
    speed: float = 1.0,
    pitch_shift: int = 0,
    character_voices: Optional[dict[str, str]] = None,
) -> str:
    """One-liner helper."""
    return SSMLBuilder(voice, speed, pitch_shift, character_voices).build(text)
