"""
core/pdf_extractor.py — NarraAI
Improved chapter detection algorithm:

  Phase 1 — Candidate scan: find all lines matching heading patterns
  Phase 2 — TOC suppression: discard heading hits that are clustered
             within the first ~5% of the document (table of contents)
  Phase 3 — Duplicate merge: if the same heading appears twice
             (once in TOC, once in body), keep only the second occurrence
  Phase 4 — Stub filter: discard sections with < MIN_CHAPTER_WORDS words
             or < MIN_CHAPTER_FRACTION of the longest chapter
  Phase 5 — Fallback: if still <2 chapters, split by page blocks

Requires: pymupdf (pip install pymupdf)
"""

import re
from pathlib import Path
from typing import Optional


# ── Heading patterns ──────────────────────────────────────────────────── #

CHAPTER_PATTERNS = [
    # "Chapter 1", "Chapter 1:", "Chapter One — Title", "CHAPTER 12"
    re.compile(
        r"^chapter\s+(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten"
        r"|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen"
        r"|nineteen|twenty(?:[-\s](?:one|two|three|four|five|six|seven|eight|nine))?"
        r"|thirty|forty|fifty)[\s\-–—:\.]*.*$",
        re.IGNORECASE,
    ),
    # "Part I", "Part 2", "Part Three"
    re.compile(
        r"^part\s+(\d{1,2}|[ivxlcdmIVXLCDM]{1,6}|one|two|three|four|five"
        r"|six|seven|eight|nine|ten)[\s\-–—:\.]*.*$",
        re.IGNORECASE,
    ),
    # Standalone structural labels
    re.compile(
        r"^(prologue|epilogue|introduction|preface|afterword|foreword"
        r"|interlude|intermission|coda|appendix\s*\w*)$",
        re.IGNORECASE,
    ),
]

MIN_CHAPTER_WORDS    = 250   # below this → stub / TOC entry
MIN_CHAPTER_FRACTION = 0.04  # must be ≥4% of longest chapter's word count
TOC_PAGE_FRACTION    = 0.06  # first 6% of pages treated as potential TOC zone


class PDFExtractor:

    def __init__(self, path: str):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        self._doc = None

    # ── Public API ───────────────────────────────────────────────────────

    def extract_raw(self) -> str:
        return "\n".join(p.get_text("text") for p in self._open())

    def extract_pages(self) -> list[dict]:
        return [
            {"page": i + 1, "text": p.get_text("text")}
            for i, p in enumerate(self._open())
        ]

    def extract_page_range(self, start_page: int, end_page: int) -> str:
        doc   = self._open()
        total = len(doc)
        s     = max(1, min(start_page, total)) - 1
        e     = max(s + 1, min(end_page, total))
        return "\n".join(doc[i].get_text("text") for i in range(s, e)).strip()

    def extract_chapters(self) -> list[dict]:
        raw_pages = self.extract_pages()
        chapters  = self._detect_chapters(raw_pages)
        if not chapters:
            chapters = self._split_by_pages(raw_pages, group_size=20)
        return chapters

    def page_count(self) -> int:
        return len(self._open())

    # ── Detection algorithm ───────────────────────────────────────────── #

    def _detect_chapters(self, raw_pages: list[dict]) -> list[dict]:
        total_pages = len(raw_pages)
        toc_cutoff  = max(3, int(total_pages * TOC_PAGE_FRACTION))

        # ── Phase 1: build global line array with page mapping ──────────
        all_lines:    list[str] = []
        line_to_page: dict[int, int] = {}
        for p in raw_pages:
            for ln in p["text"].split("\n"):
                line_to_page[len(all_lines)] = p["page"]
                all_lines.append(ln)

        # ── Phase 2: find all candidate heading lines ────────────────────
        candidates: list[dict] = []   # {title, line, page}
        for i, line in enumerate(all_lines):
            stripped = line.strip()
            if not stripped or len(stripped) > 90:
                continue
            for pat in CHAPTER_PATTERNS:
                if pat.match(stripped):
                    candidates.append({
                        "title": _title_case(stripped),
                        "line":  i,
                        "page":  line_to_page.get(i, 1),
                    })
                    break

        if len(candidates) < 2:
            return []

        # ── Phase 3: TOC suppression ─────────────────────────────────────
        # If a heading appears both inside the TOC zone AND later in the body,
        # discard the TOC occurrence and keep only the body one.
        # Also discard headings that appear only in the TOC zone.
        toc_titles  = {c["title"].lower() for c in candidates if c["page"] <= toc_cutoff}
        body_titles = {c["title"].lower() for c in candidates if c["page"] >  toc_cutoff}

        filtered: list[dict] = []
        for c in candidates:
            title_lc = c["title"].lower()
            if c["page"] <= toc_cutoff:
                # Keep only if it does NOT also appear in the body (i.e. it's real)
                if title_lc not in body_titles:
                    filtered.append(c)
                # Otherwise silently drop — body copy will be kept
            else:
                filtered.append(c)

        if len(filtered) < 2:
            # Fall back to all candidates if filtering removed too much
            filtered = candidates

        # ── Phase 4: deduplicate consecutive identical titles ────────────
        deduped: list[dict] = []
        for c in filtered:
            if deduped and deduped[-1]["title"].lower() == c["title"].lower():
                deduped[-1] = c   # keep the later occurrence
            else:
                deduped.append(c)

        # ── Phase 5: slice text between headings ─────────────────────────
        raw_chapters: list[dict] = []
        for idx, hit in enumerate(deduped):
            start      = hit["line"] + 1
            end        = deduped[idx + 1]["line"] if idx + 1 < len(deduped) else len(all_lines)
            text       = "\n".join(all_lines[start:end]).strip()
            word_count = len(text.split())
            raw_chapters.append({
                "title":      hit["title"],
                "text":       text,
                "start_page": hit["page"],
                "word_count": word_count,
                "approved":   True,
            })

        # ── Phase 6: stub filter ─────────────────────────────────────────
        raw_chapters = [c for c in raw_chapters if c["word_count"] >= MIN_CHAPTER_WORDS]
        if not raw_chapters:
            return []

        max_words = max(c["word_count"] for c in raw_chapters)
        threshold = max(MIN_CHAPTER_WORDS, int(max_words * MIN_CHAPTER_FRACTION))
        raw_chapters = [c for c in raw_chapters if c["word_count"] >= threshold]

        return raw_chapters

    # ── Fallback ─────────────────────────────────────────────────────────

    def _split_by_pages(self, raw_pages: list[dict], group_size: int) -> list[dict]:
        chapters = []
        for i in range(0, len(raw_pages), group_size):
            group = raw_pages[i: i + group_size]
            text  = "\n".join(p["text"] for p in group).strip()
            if not text:
                continue
            chapters.append({
                "title":      f"Pages {group[0]['page']}–{group[-1]['page']}",
                "text":       text,
                "start_page": group[0]["page"],
                "word_count": len(text.split()),
                "approved":   True,
            })
        return chapters

    # ── Helpers ──────────────────────────────────────────────────────────

    def _open(self):
        if self._doc is None:
            try:
                import fitz
            except ImportError as e:
                raise ImportError("pip install pymupdf") from e
            self._doc = fitz.open(str(self.path))
        return self._doc

    def __del__(self):
        if self._doc:
            try:
                self._doc.close()
            except Exception:
                pass


# ── Module-level helpers ──────────────────────────────────────────────── #

def extract_short_story(path: str) -> Optional[dict]:
    ex    = PDFExtractor(path)
    raw   = ex.extract_raw()
    lines = [l for l in raw.split("\n") if l.strip()]
    if len(lines) / max(ex.page_count(), 1) <= 5 or len(lines) <= 15:
        return {"title": Path(path).stem, "text": raw,
                "start_page": 1, "word_count": len(raw.split()), "approved": True}
    return None


def estimate_duration(text: str, wpm: int = 150) -> str:
    """
    Estimate spoken narration duration from word count.
    Uses ~150 words-per-minute (average audiobook pace).
    Returns human-readable string: '4m 32s', '1h 12m', '0s'.
    """
    words = len(text.split())
    if words == 0:
        return "0s"
    mins = words / wpm
    h, m = divmod(int(mins), 60)
    s    = int((mins * 60) % 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{max(s, 1)}s"


def _title_case(s: str) -> str:
    small = {"a","an","the","and","but","or","for","nor","on","at","to","by","in","of","up"}
    words = s.split()
    return " ".join(
        w.capitalize() if i == 0 or w.lower() not in small else w.lower()
        for i, w in enumerate(words)
    )
