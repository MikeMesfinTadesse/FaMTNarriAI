"""
core/elevenlabs_tts.py — ElevenLabs TTS Integration for NarraAI
═══════════════════════════════════════════════════════════════════════════════

PURPOSE:
    Drop-in ElevenLabs audio generation engine. Mirrors the interface of
    AudiobookConverter so it can be used from any tab without refactoring.

KEY FEATURES:
    • Fetch all available ElevenLabs voices (built-in + cloned)
    • Voice clone upload via the ElevenLabs API
    • Text-to-speech with eleven_multilingual_v2 (29+ languages)
    • Streaming MP3 output, chunk-safe (same chunker as Edge-TTS module)
    • Per-chunk retry with backoff (up to 3×)
    • Preview generation (first ~400 words)

DEPENDENCIES:
    pip install elevenlabs requests
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os
import re
import time
import threading
from pathlib import Path
from typing import Callable, Optional

# ── ElevenLabs SDK (optional — guarded import) ────────────────────────────
try:
    from elevenlabs.client import ElevenLabs as _ELClient
    from elevenlabs import VoiceSettings
    ELEVENLABS_SDK = True
except ImportError:
    ELEVENLABS_SDK = False

# ── requests fallback for raw HTTP calls ──────────────────────────────────
try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
#  Constants
# ══════════════════════════════════════════════════════════════════════════════

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL        = "eleven_multilingual_v2"
MAX_CHUNK_CHARS      = 2500   # ElevenLabs recommends ≤2500 chars per request

# Sentence splitter — same as core/converter.py
_SENTENCE_END_RE = re.compile(
    r"(?<=[.!?؟।۔])\s+"
    r"|(?<=[\u3002\uff01\uff1f])"
)
_CJK_RE = re.compile(
    r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]"
)
_SOFT_WRAP_RE = re.compile(r"(?<![.!?؟।۔\u3002\uff01\uff1f\n])\n(?!\n)")


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _safe_str(s: str, max_len: int = 40) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s[:max_len]


def _is_cjk_dominant(text: str) -> bool:
    return len(_CJK_RE.findall(text)) > max(1, len(text) * 0.2)


def _split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Sentence-boundary-safe chunker (mirrors core/converter.py)."""
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


def _clean_for_tts(text: str) -> str:
    """Strip NarraAI markup so ElevenLabs gets plain readable text."""
    text = re.sub(r"\[[^\]:]+:\s*(.+?)\]", r"\1", text, flags=re.DOTALL)
    text = re.sub(
        r"\((whisper|shout|excited|sad|dramatic|gentle|pause|slow|fast|emphasis)\)",
        "", text, flags=re.IGNORECASE
    )
    text = _SOFT_WRAP_RE.sub(" ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ══════════════════════════════════════════════════════════════════════════════
#  ElevenLabs API helpers (SDK + raw-HTTP fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _get_client(api_key: str):
    """Return an ElevenLabs SDK client, or None if SDK not installed."""
    if not ELEVENLABS_SDK:
        return None
    return _ELClient(api_key=api_key)


def fetch_voices(api_key: str) -> list[dict]:
    """
    Return a list of voice dicts:
        {"voice_id": str, "name": str, "category": str, "labels": dict}

    Works via SDK if available, otherwise raw HTTP.
    Raises RuntimeError on auth / network failure.
    """
    if not api_key or not api_key.strip():
        raise RuntimeError("No API key provided. Enter your ElevenLabs API key.")

    if ELEVENLABS_SDK:
        client = _get_client(api_key)
        try:
            result = client.voices.get_all()
            return [
                {
                    "voice_id": v.voice_id,
                    "name":     v.name,
                    "category": getattr(v, "category", "premade"),
                    "labels":   dict(getattr(v, "labels", {}) or {}),
                }
                for v in result.voices
            ]
        except Exception as exc:
            raise RuntimeError(f"ElevenLabs API error: {exc}") from exc

    if not REQUESTS_AVAILABLE:
        raise RuntimeError(
            "Install 'elevenlabs' or 'requests' to use ElevenLabs:\n"
            "  pip install elevenlabs"
        )
    resp = _requests.get(
        f"{ELEVENLABS_API_BASE}/voices",
        headers={"xi-api-key": api_key},
        timeout=15,
    )
    if resp.status_code == 401:
        raise RuntimeError("Invalid ElevenLabs API key.")
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "voice_id": v["voice_id"],
            "name":     v["name"],
            "category": v.get("category", "premade"),
            "labels":   v.get("labels", {}),
        }
        for v in data.get("voices", [])
    ]


def clone_voice(api_key: str, name: str, file_paths: list[str],
                description: str = "") -> dict:
    """
    Upload audio samples and create a cloned voice.
    Returns the new voice dict {"voice_id": str, "name": str}.
    Requires ElevenLabs Creator plan or above.
    """
    if not api_key:
        raise RuntimeError("API key required.")

    if ELEVENLABS_SDK:
        client = _get_client(api_key)
        files  = [open(p, "rb") for p in file_paths]
        try:
            voice = client.clone(name=name, files=files, description=description)
            return {"voice_id": voice.voice_id, "name": voice.name}
        finally:
            for f in files:
                f.close()

    if not REQUESTS_AVAILABLE:
        raise RuntimeError("pip install elevenlabs  or  pip install requests")

    files_payload = [
        ("files", (Path(p).name, open(p, "rb"), "audio/mpeg"))
        for p in file_paths
    ]
    data = {"name": name, "description": description}
    resp = _requests.post(
        f"{ELEVENLABS_API_BASE}/voices/add",
        headers={"xi-api-key": api_key},
        data=data,
        files=files_payload,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def _synthesise_chunk(api_key: str, text: str, voice_id: str,
                       model_id: str, stability: float,
                       similarity_boost: float) -> bytes:
    """
    Call ElevenLabs TTS for one chunk. Returns raw MP3 bytes.
    Uses SDK if available, else raw HTTP.
    """
    if ELEVENLABS_SDK:
        client = _get_client(api_key)
        audio  = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
            voice_settings=VoiceSettings(
                stability=stability,
                similarity_boost=similarity_boost,
            ),
            output_format="mp3_44100_128",
        )
        # SDK may return a generator or bytes
        if hasattr(audio, "__iter__") and not isinstance(audio, (bytes, bytearray)):
            return b"".join(audio)
        return bytes(audio)

    # Raw HTTP fallback
    if not REQUESTS_AVAILABLE:
        raise RuntimeError("pip install elevenlabs  or  pip install requests")
    resp = _requests.post(
        f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}",
        headers={
            "xi-api-key":   api_key,
            "Content-Type": "application/json",
            "Accept":       "audio/mpeg",
        },
        json={
            "text":       text,
            "model_id":   model_id,
            "voice_settings": {
                "stability":        stability,
                "similarity_boost": similarity_boost,
            },
        },
        timeout=60,
    )
    if resp.status_code == 401:
        raise RuntimeError("Invalid ElevenLabs API key.")
    resp.raise_for_status()
    return resp.content


# ══════════════════════════════════════════════════════════════════════════════
#  ElevenLabsConverter  —  same interface as AudiobookConverter
# ══════════════════════════════════════════════════════════════════════════════

class ElevenLabsConverter:
    """
    Converts chapter dicts to MP3 files using ElevenLabs TTS.

    OUTPUT FILENAME FORMAT (same as AudiobookConverter):
        VoiceName__DocumentTitle__01_ChapterTitle.mp3

    CHAPTER DICT FORMAT:
        Required:  "title" (str), "text" (str)
        Optional:  "word_count" (int), "approved" (bool)
    """

    def __init__(
        self,
        api_key:          str,
        voice_id:         str,
        voice_name:       str                                       = "ElevenLabs",
        model_id:         str                                       = DEFAULT_MODEL,
        stability:        float                                     = 0.5,
        similarity_boost: float                                     = 0.75,
        output_dir:       str                                       = "output",
        document_title:   str                                       = "",
        on_progress:      Optional[Callable[[int, int, str], None]] = None,
        on_log:           Optional[Callable[[str, str], None]]      = None,
        on_status:        Optional[Callable[[str, str], None]]      = None,
        max_retries:      int                                       = 3,
    ):
        self.api_key          = api_key.strip()
        self.voice_id         = voice_id
        self.voice_name       = voice_name
        self.model_id         = model_id
        self.stability        = max(0.0, min(1.0, stability))
        self.similarity_boost = max(0.0, min(1.0, similarity_boost))
        self.output_dir       = Path(output_dir)
        self.document_title   = document_title or "Untitled"
        self.max_retries      = max(1, max_retries)
        self.on_progress      = on_progress or (lambda *a: None)
        self.on_log           = on_log      or (lambda m, l: print(f"[{l.upper()}] {m}"))
        self.on_status        = on_status   or (lambda m, l: None)

    # ── Public API ───────────────────────────────────────────────────────────

    def convert_chapters(self, chapters: list[dict], playlist: bool = True) -> list[Path]:
        """Convert all chapters synchronously. Returns list of output Paths."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_files: list[Path] = []
        total = len(chapters)

        self.on_log(f"ElevenLabs | voice: {self.voice_name} | model: {self.model_id}", "info")
        self.on_log(f"Document: {self.document_title}", "info")
        self.on_status(f"Conversion started — {total} chapter(s)", "ok")

        for i, chapter in enumerate(chapters, 1):
            title    = chapter.get("title", f"Chapter {i}")
            raw_text = chapter.get("text", "")
            text     = _clean_for_tts(raw_text)

            if not text:
                self.on_log(f"Skipping empty: {title}", "warn")
                self.on_progress(i, total, title)
                continue

            self.on_log(f"[{i}/{total}] {title}", "info")
            self.on_progress(i - 1, total, title)
            t0       = time.monotonic()
            out_path = self.output_dir / self._make_filename(i, title)

            try:
                self._synthesise_with_retry(text, out_path)
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

    def preview(self, text: str) -> Path:
        """Generate a short preview MP3 (first ~400 words). Returns output Path."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        vn  = _safe_str(self.voice_name, 20)
        doc = _safe_str(self.document_title, 30)
        out = self.output_dir / f"el_preview_{vn}__{doc}.mp3"

        cleaned = _clean_for_tts(text)
        snippet = " ".join(cleaned.split()[:400])
        for punct in (".", "!", "?", "؟", "。"):
            idx = snippet.rfind(punct)
            if idx > len(snippet) // 2:
                snippet = snippet[:idx + 1]
                break

        self.on_log(f"ElevenLabs preview → {out.name}", "info")
        self._synthesise_with_retry(snippet, out)
        self.on_status(f"Preview ready — {self.voice_name}", "ok")
        return out

    # ── Internal ─────────────────────────────────────────────────────────────

    def _synthesise_with_retry(self, text: str, out_path: Path) -> None:
        chunks    = _split_into_chunks(text)
        all_audio = bytearray()

        if not chunks:
            self.on_log(f"No content for {out_path.name}", "warn")
            return

        self.on_log(f"  {len(chunks)} chunk(s) → {out_path.name}", "info")

        for idx, chunk in enumerate(chunks, 1):
            last_error = None
            for attempt in range(1, self.max_retries + 1):
                try:
                    data = _synthesise_chunk(
                        api_key=self.api_key,
                        text=chunk,
                        voice_id=self.voice_id,
                        model_id=self.model_id,
                        stability=self.stability,
                        similarity_boost=self.similarity_boost,
                    )
                    all_audio.extend(data)
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < self.max_retries:
                        wait = attempt * 2.0
                        self.on_log(
                            f"  Chunk {idx} attempt {attempt} failed, retry in {wait:.0f}s — {exc}",
                            "warn",
                        )
                        time.sleep(wait)

            if last_error is not None:
                raise RuntimeError(
                    f"Chunk {idx}/{len(chunks)} failed after {self.max_retries} attempts: {last_error}"
                )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(bytes(all_audio))

    def _make_filename(self, index: int, chapter_title: str) -> str:
        vn  = _safe_str(self.voice_name, 20)
        doc = _safe_str(self.document_title, 35)
        ch  = _safe_str(chapter_title, 40)
        return f"{vn}__{doc}__{index:02d}_{ch}.mp3"

    def _write_playlist(self, files: list[Path]) -> Path:
        vn  = _safe_str(self.voice_name, 20)
        doc = _safe_str(self.document_title, 35)
        pl  = self.output_dir / f"{doc}__{vn}.m3u"
        with open(pl, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for fp in files:
                f.write(f"#EXTINF:-1,{fp.stem}\n{fp.name}\n")
        return pl
