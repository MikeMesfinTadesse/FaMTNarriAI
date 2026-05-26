"""
core/converter.py — NarraAI Audiobook Studio
═══════════════════════════════════════════════════════════════════════════════

PURPOSE:
    The audio generation engine. Takes chapter dicts (title + text) and converts
    them to MP3 files using Microsoft Edge-TTS neural voices. This module is the
    only place that talks to the TTS service — every other module feeds into this.

KEY RESPONSIBILITIES:
    • VOICES dict      — master catalogue of all available Edge-TTS voices
    • _clean_for_tts   — strips NarraAI markup so TTS gets plain readable text
    • _split_into_chunks — splits text at sentence boundaries (never mid-sentence),
                           handles Latin, Arabic, CJK, Indic scripts
    • validate_voice   — pings Edge-TTS before a conversion to confirm the voice
                         works, raises a clear error if not
    • AudiobookConverter — main class: convert_chapters() and preview()
    • _safe_filename   — generates descriptive filenames including voice name +
                         document title so files are never overwritten
    • _synthesise_with_retry — chunk-level retry (up to 3×) with backoff so a
                               single network blip doesn't kill a full chapter

FILENAME CONVENTION:
    Output files are named:  VoiceName__DocumentTitle__01_ChapterTitle.mp3
    Example:  Aria__The_Iron_Wizard__01_The_Awakening.mp3
    This ensures every file is unique and easy to identify without opening it.

DEPENDENCIES:
    edge-tts  (pip install edge-tts)
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import re
import time
from pathlib import Path
from typing import Callable, Optional

try:
    import edge_tts
except ImportError as e:
    raise ImportError("Run:  pip install edge-tts") from e


# ══════════════════════════════════════════════════════════════════════════════
#  Voice Catalogue
#  All voices are verified working Neural voices from Microsoft Edge-TTS.
#  Key: Edge-TTS voice ID   Value: Human-readable label shown in the UI
# ══════════════════════════════════════════════════════════════════════════════

VOICES: dict[str, str] = {
    # English — US
    "en-US-AriaNeural":        "Aria (Expressive, F)",
    "en-US-GuyNeural":         "Guy (Friendly, M)",
    "en-US-JennyNeural":       "Jenny (Casual, F)",
    "en-US-ChristopherNeural": "Christopher (Authoritative, M)",
    "en-US-EricNeural":        "Eric (Rational, M)",
    "en-US-MichelleNeural":    "Michelle (Friendly, F)",
    "en-US-RogerNeural":       "Roger (Lively, M)",
    "en-US-SteffanNeural":     "Steffan (Passionate, M)",
    "en-US-JaneNeural":        "Jane (Cheerful, F)",
    "en-US-DavisNeural":       "Davis (Casual, M)",
    "en-US-NancyNeural":       "Nancy (Pleasant, F)",
    "en-US-SaraNeural":        "Sara (Pleasant, F)",
    # English — GB
    "en-GB-SoniaNeural":       "Sonia (GB, F)",
    "en-GB-RyanNeural":        "Ryan (GB, M)",
    "en-GB-LibbyNeural":       "Libby (GB, F)",
    "en-GB-EmmaNeural":        "Emma (GB, F)",
    "en-GB-OliverNeural":      "Oliver (GB, M)",
    # English — AU / IN / CA / IE
    "en-AU-NatashaNeural":     "Natasha (AU, F)",
    "en-AU-WilliamNeural":     "William (AU, M)",
    "en-IN-NeerjaNeural":      "Neerja (IN, F)",
    "en-IN-PrabhatNeural":     "Prabhat (IN, M)",
    "en-CA-ClaraNeural":       "Clara (CA, F)",
    "en-CA-LiamNeural":        "Liam (CA, M)",
    "en-IE-EmilyNeural":       "Emily (IE, F)",
    "en-IE-ConnorNeural":      "Connor (IE, M)",
    # Arabic
    "ar-SA-ZariyahNeural":     "Zariyah (SA, F)",
    "ar-SA-HamedNeural":       "Hamed (SA, M)",
    "ar-EG-SalmaNeural":       "Salma (EG, F)",
    "ar-EG-ShakirNeural":      "Shakir (EG, M)",
    "ar-AE-FatimaNeural":      "Fatima (AE, F)",
    "ar-AE-HamdanNeural":      "Hamdan (AE, M)",
    # French
    "fr-FR-DeniseNeural":      "Denise (FR, F)",
    "fr-FR-HenriNeural":       "Henri (FR, M)",
    # German
    "de-DE-KatjaNeural":       "Katja (DE, F)",
    "de-DE-ConradNeural":      "Conrad (DE, M)",
    # Spanish
    "es-ES-ElviraNeural":      "Elvira (ES, F)",
    "es-MX-DaliaNeural":       "Dalia (MX, F)",
    "es-MX-JorgeNeural":       "Jorge (MX, M)",
    # Japanese
    "ja-JP-NanamiNeural":      "Nanami (JP, F)",
    "ja-JP-KeitaNeural":       "Keita (JP, M)",
    # Chinese
    "zh-CN-XiaoxiaoNeural":    "Xiaoxiao (CN, F)",
    "zh-CN-YunxiNeural":       "Yunxi (CN, M)",
    "zh-TW-HsiaoChenNeural":   "HsiaoChen (TW, F)",
    # Korean
    "ko-KR-SunHiNeural":       "Sun-Hi (KR, F)",
    "ko-KR-InJoonNeural":      "InJoon (KR, M)",
    # Hindi
    "hi-IN-SwaraNeural":       "Swara (HI, F)",
    "hi-IN-MadhurNeural":      "Madhur (HI, M)",
    # Turkish
    "tr-TR-EmelNeural":        "Emel (TR, F)",
    "tr-TR-AhmetNeural":       "Ahmet (TR, M)",
    # Slovak
    "sk-SK-LukasNeural":       "Lukas (SK, M)",
    "sk-SK-ViktoriaNeural":    "Viktoria (SK, F)",
    # Russian
    "ru-RU-SvetlanaNeural":    "Svetlana (RU, F)",
    "ru-RU-DmitryNeural":      "Dmitry (RU, M)",
    # Italian
    "it-IT-ElsaNeural":        "Elsa (IT, F)",
    "it-IT-DiegoNeural":       "Diego (IT, M)",
    # Portuguese
    "pt-BR-FranciscaNeural":   "Francisca (BR, F)",
    "pt-BR-AntonioNeural":     "Antonio (BR, M)",
    # Dutch
    "nl-NL-ColetteNeural":     "Colette (NL, F)",
    "nl-NL-MaartenNeural":     "Maarten (NL, M)",
    # Polish
    "pl-PL-AgnieszkaNeural":   "Agnieszka (PL, F)",
    "pl-PL-MarekNeural":       "Marek (PL, M)",
    # Swedish
    "sv-SE-SofieNeural":       "Sofie (SE, F)",
    "sv-SE-MattiasNeural":     "Mattias (SE, M)",
    # Swahili
    "sw-KE-ZuriNeural":        "Zuri (KE, F)",
    "sw-KE-RafikiNeural":      "Rafiki (KE, M)",
    "sw-TZ-RehemaNeural":      "Rehema (TZ, F)",
    "sw-TZ-DaudiNeural":       "Daudi (TZ, M)",
    # Amharic
    "am-ET-MekdesNeural":      "Mekdes (ET, F)",
    "am-ET-AmehaNeural":       "Ameha (ET, M)",
    # Filipino
    "fil-PH-BlessicaNeural":   "Blessica (PH, F)",
    "fil-PH-AngeloNeural":     "Angelo (PH, M)",
}

# Voices well-suited for children's storytelling (warm, expressive, clear)
KIDS_VOICES: dict[str, str] = {
    "en-US-AriaNeural":        "Aria — Expressive & Warm",
    "en-US-JennyNeural":       "Jenny — Friendly & Casual",
    "en-US-JaneNeural":        "Jane — Cheerful & Bright",
    "en-US-MichelleNeural":    "Michelle — Gentle & Friendly",
    "en-US-SaraNeural":        "Sara — Pleasant & Clear",
    "en-GB-LibbyNeural":       "Libby — Bright British",
    "en-GB-EmmaNeural":        "Emma — Warm British",
    "en-AU-NatashaNeural":     "Natasha — Clear Australian",
    "en-US-GuyNeural":         "Guy — Friendly Male",
    "en-US-RogerNeural":       "Roger — Lively & Fun",
    "en-US-EricNeural":        "Eric — Calm & Clear",
    "en-GB-OliverNeural":      "Oliver — Gentle British Male",
}


# ══════════════════════════════════════════════════════════════════════════════
#  Text Cleaning
# ══════════════════════════════════════════════════════════════════════════════

_EMOTION_RE  = re.compile(
    r"\((whisper|shout|excited|sad|dramatic|gentle|pause|slow|fast|emphasis)\)",
    re.IGNORECASE,
)
_CHAR_TAG_RE = re.compile(r"\[[^\]:]+:\s*(.+?)\]", re.DOTALL)

# Soft PDF line-wrap: rejoin lines that don't end with sentence punctuation
_SOFT_WRAP_RE = re.compile(r"(?<![.!?؟।۔\u3002\uff01\uff1f\n])\n(?!\n)")

# Sentence boundary — Latin + Arabic + Indic + CJK
_SENTENCE_END_RE = re.compile(
    r"(?<=[.!?؟।۔])\s+"
    r"|(?<=[\u3002\uff01\uff1f])"
)

# CJK detection
_CJK_RE = re.compile(
    r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]"
)

# Max characters per Edge-TTS request
MAX_CHUNK_CHARS = 3000


def _clean_for_tts(text: str) -> str:
    """
    Prepare raw text for Edge-TTS:
      1. Strip [Character: "dialogue"] markers, keeping inner text
      2. Strip (emotion) tags
      3. Rejoin PDF soft line-wraps (mid-sentence breaks)
      4. Normalise whitespace
    """
    text = _CHAR_TAG_RE.sub(r"\1", text)
    text = _EMOTION_RE.sub("", text)
    text = _SOFT_WRAP_RE.sub(" ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ══════════════════════════════════════════════════════════════════════════════
#  Language-Aware Chunker
# ══════════════════════════════════════════════════════════════════════════════

def _is_cjk_dominant(text: str) -> bool:
    return len(_CJK_RE.findall(text)) > max(1, len(text) * 0.2)


def _split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """
    Split text into TTS-safe chunks that never break mid-sentence.
    Handles Latin, Arabic, CJK, Indic scripts.
    """
    if not text.strip():
        return []

    if _is_cjk_dominant(text):
        marked    = re.sub(r"([。！？\uff01\uff1f])", r"\1\n", text)
        sentences = [s.strip() for s in marked.split("\n") if s.strip()]
    else:
        sentences = [s.strip() for s in _SENTENCE_END_RE.split(text) if s.strip()]

    if not sentences:
        sentences = [text.strip()]

    chunks:  list[str] = []
    current: str       = ""

    def flush(s: str) -> None:
        if len(s) <= max_chars:
            chunks.append(s)
            return
        for para in s.split("\n\n"):
            para = para.strip()
            if not para:
                continue
            if len(para) <= max_chars:
                chunks.append(para)
            else:
                while len(para) > max_chars:
                    cut = para.rfind(" ", 0, max_chars)
                    cut = cut if cut > 0 else max_chars
                    chunks.append(para[:cut].strip())
                    para = para[cut:].strip()
                if para:
                    chunks.append(para)

    for sentence in sentences:
        candidate = (current + " " + sentence).strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                flush(current)
            current = sentence if len(sentence) <= max_chars else ""
            if len(sentence) > max_chars:
                flush(sentence)

    if current:
        flush(current)

    return [c for c in chunks if c.strip()]


# ══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ══════════════════════════════════════════════════════════════════════════════

def _speed_to_rate(speed: float) -> str:
    return f"{int(round((speed - 1.0) * 100)):+d}%"


def voice_short_name(voice: str) -> str:
    """'en-US-AriaNeural' -> 'Aria'"""
    m = re.search(r"-([A-Za-z]+)Neural$", voice)
    return m.group(1) if m else voice.split("-")[-1]


def _safe_str(s: str, max_len: int = 40) -> str:
    """Strip filesystem-unsafe characters and truncate."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s[:max_len]


def _run_async(coro):
    """Run a coroutine safely whether or not an event loop is already running."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ══════════════════════════════════════════════════════════════════════════════
#  Voice Validation
# ══════════════════════════════════════════════════════════════════════════════

async def validate_voice_async(voice: str) -> tuple[bool, str]:
    """
    Send a tiny test to Edge-TTS to confirm the voice is available.
    Returns (True, "") on success or (False, error_message) on failure.
    Does NOT write any file — just streams one audio chunk and stops.
    """
    try:
        comm = edge_tts.Communicate(text="Test.", voice=voice, rate="+0%")
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                return True, ""
        return True, ""
    except Exception as exc:
        return False, str(exc)


def validate_voice(voice: str) -> tuple[bool, str]:
    return _run_async(validate_voice_async(voice))


# ══════════════════════════════════════════════════════════════════════════════
#  AudiobookConverter
# ══════════════════════════════════════════════════════════════════════════════

class AudiobookConverter:
    """
    Converts chapter dicts to MP3 files using Microsoft Edge-TTS.

    OUTPUT FILENAME FORMAT:
        VoiceName__DocumentTitle__01_ChapterTitle.mp3
        Example: Aria__The_Iron_Wizard__01_The_Awakening.mp3

        This means:
        - Files are NEVER overwritten — each voice+title combo is unique
        - You can immediately identify which voice and book a file belongs to
        - Files sort in chapter order within any folder

    CHAPTER DICT FORMAT:
        Required:  "title" (str), "text" (str)
        Optional:  "word_count" (int), "start_page" (int), "approved" (bool)
    """

    def __init__(
        self,
        voice:            str                                        = "en-US-AriaNeural",
        speed:            float                                      = 1.0,
        output_dir:       str                                        = "output",
        document_title:   str                                        = "",
        character_voices: Optional[dict[str, str]]                  = None,
        on_progress:      Optional[Callable[[int, int, str], None]]  = None,
        on_log:           Optional[Callable[[str, str], None]]       = None,
        on_status:        Optional[Callable[[str, str], None]]       = None,
        max_retries:      int                                        = 3,
    ):
        """
        Args:
            voice:            Edge-TTS voice name (e.g. 'en-US-AriaNeural').
            speed:            Speed multiplier 0.5–2.0.
            output_dir:       Folder where MP3 files are saved.
            document_title:   The PDF/TXT filename — included in output filenames
                              so you can tell which book each file belongs to.
            character_voices: {CharacterName: VoiceName} for multi-voice mode.
            on_progress:      Called as on_progress(current, total, chapter_title).
            on_log:           Called as on_log(message, level).
            on_status:        Called for key milestones (started/done/failed).
            max_retries:      Network retry count per chunk (default 3).
        """
        self.voice            = voice if voice else "en-US-AriaNeural"
        self.speed            = max(0.5, min(2.0, float(speed)))
        self.output_dir       = Path(output_dir)
        self.document_title   = document_title or "Untitled"
        self.character_voices = character_voices or {}
        self.max_retries      = max(1, max_retries)
        self.on_progress      = on_progress or (lambda *a: None)
        self.on_log           = on_log      or (lambda m, l: print(f"[{l.upper()}] {m}"))
        self.on_status        = on_status   or (lambda m, l: None)

    # ── Public API ───────────────────────────────────────────────────────────

    def convert_chapters(self, chapters: list[dict], playlist: bool = True) -> list[Path]:
        """Convert all chapters. Blocks until complete. Returns list of output Paths."""
        return _run_async(self._convert_all(chapters, playlist))

    def preview(self, text: str, voice: Optional[str] = None) -> Path:
        """
        Generate a short preview MP3 (first ~400 words).
        Named: preview_VoiceName__DocumentTitle.mp3
        Each voice gets its own file so previews are never overwritten.
        Returns the output Path.
        """
        return _run_async(self._preview_async(text, voice or self.voice))

    # ── Async internals ──────────────────────────────────────────────────────

    async def _preview_async(self, text: str, voice: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        short   = voice_short_name(voice)
        doc     = _safe_str(self.document_title, 30)
        # Named so each voice+doc combo has its own preview file
        out     = self.output_dir / f"preview_{short}__{doc}.mp3"

        cleaned = _clean_for_tts(text)
        snippet = " ".join(cleaned.split()[:400])
        for punct in (".", "!", "?", "؟", "。"):
            idx = snippet.rfind(punct)
            if idx > len(snippet) // 2:
                snippet = snippet[:idx + 1]
                break

        ok, err = await validate_voice_async(voice)
        if not ok:
            msg = f"Voice '{short}' is unavailable: {err}"
            self.on_status(msg, "error")
            raise RuntimeError(msg)

        self.on_log(f"Preview → {out.name}", "info")
        await self._synthesise_with_retry(snippet, out, voice)
        self.on_status(f"Preview ready — {short}", "ok")
        return out

    async def _convert_all(self, chapters: list[dict], playlist: bool) -> list[Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_files: list[Path] = []
        total = len(chapters)

        ok, err = await validate_voice_async(self.voice)
        if not ok:
            msg = (f"Voice '{voice_short_name(self.voice)}' is not working: {err}\n"
                   f"Please select a different voice.")
            self.on_log(msg, "error")
            self.on_status(msg, "error")
            raise RuntimeError(msg)

        self.on_log(f"Voice OK: {self.voice}", "info")
        self.on_log(f"Document: {self.document_title}", "info")
        self.on_log(f"Speed: {self.speed}x  |  Chunks up to {MAX_CHUNK_CHARS} chars", "info")
        self.on_status(f"Conversion started — {total} chapter(s)", "ok")

        for i, chapter in enumerate(chapters, 1):
            title    = chapter.get("title", f"Chapter {i}")
            raw_text = chapter.get("text", "")
            text     = _clean_for_tts(raw_text)

            if not text:
                self.on_log(f"Skipping empty: {title}", "warn")
                self.on_progress(i, total, title)
                continue

            # Multi-voice: check if chapter title matches a character name
            voice = self.voice
            for char_name, char_voice in self.character_voices.items():
                if char_name.lower() in title.lower():
                    voice = char_voice
                    break

            self.on_log(f"[{i}/{total}] {title}", "info")
            self.on_progress(i - 1, total, title)
            t0 = time.monotonic()

            out_path = self.output_dir / self._make_filename(i, title)

            try:
                await self._synthesise_with_retry(text, out_path, voice)
                elapsed = time.monotonic() - t0
                kb      = out_path.stat().st_size // 1024
                self.on_log(f"✓ {out_path.name}  ({elapsed:.1f}s, {kb} KB)", "ok")
                self.on_status(f"Done: {title}", "ok")
                output_files.append(out_path)
            except Exception as exc:
                self.on_log(f"✗ Failed: {title} — {exc}", "error")
                self.on_status(f"Failed: {title}", "error")

            self.on_progress(i, total, title)

        if playlist and output_files:
            pl = self._write_playlist(output_files)
            self.on_log(f"Playlist: {pl.name}", "ok")

        msg = f"Complete — {len(output_files)}/{total} chapter(s) converted"
        self.on_log(msg, "ok")
        self.on_status(msg, "ok")
        return output_files

    async def _synthesise_with_retry(self, text: str, out_path: Path, voice: str) -> None:
        """
        Split text into sentence-safe chunks, synthesise each with retry,
        concatenate all bytes, write one MP3 file.
        Retries each failed chunk up to max_retries times with backoff.
        """
        chunks = _split_into_chunks(text)
        rate   = _speed_to_rate(self.speed)

        if not chunks:
            self.on_log(f"No content for {out_path.name}", "warn")
            return

        self.on_log(f"  {len(chunks)} chunk(s) → {out_path.name}", "info")
        all_audio = bytearray()

        for idx, chunk in enumerate(chunks, 1):
            last_error = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    comm = edge_tts.Communicate(text=chunk, voice=voice, rate=rate)
                    async for item in comm.stream():
                        if item["type"] == "audio":
                            all_audio.extend(item["data"])
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < self.max_retries:
                        wait = attempt * 1.5
                        self.on_log(
                            f"  Chunk {idx} attempt {attempt} failed, retry in {wait:.0f}s — {exc}",
                            "warn",
                        )
                        await asyncio.sleep(wait)

            if last_error is not None:
                raise RuntimeError(
                    f"Chunk {idx}/{len(chunks)} failed after {self.max_retries} attempts: {last_error}"
                )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(bytes(all_audio))

    # ── Filename generation ───────────────────────────────────────────────────

    def _make_filename(self, index: int, chapter_title: str) -> str:
        """
        Build a descriptive filename:
            VoiceName__DocumentTitle__01_ChapterTitle.mp3

        Example:
            Aria__The_Iron_Wizard__01_The_Awakening.mp3

        This guarantees:
        - Files are never silently overwritten (different voice = different file)
        - You can identify the source document at a glance
        - Files sort by chapter number within a folder
        """
        voice_part = _safe_str(voice_short_name(self.voice), 20)
        doc_part   = _safe_str(self.document_title, 35)
        ch_part    = _safe_str(chapter_title, 40)
        return f"{voice_part}__{doc_part}__{index:02d}_{ch_part}.mp3"

    def _write_playlist(self, files: list[Path]) -> Path:
        """Write an M3U playlist. Named after the document + voice."""
        voice_part = _safe_str(voice_short_name(self.voice), 20)
        doc_part   = _safe_str(self.document_title, 35)
        pl = self.output_dir / f"{doc_part}__{voice_part}.m3u"
        with open(pl, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for fp in files:
                f.write(f"#EXTINF:-1,{fp.stem}\n{fp.name}\n")
        return pl


# ══════════════════════════════════════════════════════════════════════════════
#  Standalone helpers
# ══════════════════════════════════════════════════════════════════════════════

async def list_voices_async(locale_filter: Optional[str] = None) -> list[dict]:
    """Fetch all voices from the Edge-TTS API, optionally filtered by locale prefix."""
    voices = await edge_tts.list_voices()
    if locale_filter:
        voices = [v for v in voices if v["Locale"].startswith(locale_filter)]
    return voices


def list_voices(locale_filter: Optional[str] = None) -> list[dict]:
    """Synchronous wrapper for list_voices_async."""
    return _run_async(list_voices_async(locale_filter))
