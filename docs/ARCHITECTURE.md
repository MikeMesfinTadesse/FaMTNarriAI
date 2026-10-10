# NarraAI — Architecture

This document explains how all parts of NarraAI connect.
Reading this gives you a mental map before touching any code.

---

## The Big Picture

```
User
  │
  ▼
┌─────────────────────────────────────────┐
│            gui/app.py                   │
│         (Desktop Interface)             │
│  Tabs: Editor, Chapters, Languages,     │
│         Kids, Voice Tester, Log         │
└──────────────┬──────────────────────────┘
               │ calls
               ▼
┌──────────────────────────────────────────────────────────────┐
│                        core/                                 │
│                                                              │
│  pdf_extractor.py  →  text_cleaner.py  →  converter.py      │
│  (Read PDF)           (Clean text)        (Make audio)       │
│                                                              │
│                       ssml_builder.py                        │
│                       (Emotion tags)                         │
└──────────────────────────────────┬───────────────────────────┘
                                   │ calls
                                   ▼
                     ┌─────────────────────────┐
                     │   Microsoft Edge-TTS    │
                     │   (Cloud API — free)    │
                     │   Neural voice engine   │
                     └─────────────────────────┘
                                   │
                                   ▼
                          Output MP3 files
                          + M3U playlist
```

---

## Data Flow — What Happens When You Click "Convert"

```
1. User loads a PDF
        │
        ▼
2. pdf_extractor.py reads the file
   • Extracts text page by page (PyMuPDF)
   • Detects chapter headings using regex patterns
   • Estimates word count and duration per chapter
        │
        ▼
3. text_cleaner.py sanitises the text
   • Removes URLs, email addresses
   • Removes page numbers and Roman numerals
   • Fixes PDF soft line-wraps (mid-sentence breaks)
   • Strips NarraAI emotion tags from raw text
        │
        ▼
4. converter.py prepares the audio request
   • Splits text into safe chunks (max 3000 chars)
   • Handles CJK (Chinese/Japanese/Korean) differently
     — splits on 。！？ instead of spaces
   • Converts speed slider to Edge-TTS rate string (+20%)
   • Validates the selected voice actually works
        │
        ▼
5. Edge-TTS API (Microsoft cloud)
   • Receives chunk of clean text + voice name + speed
   • Returns MP3 audio bytes
   • We retry failed chunks up to 3 times
        │
        ▼
6. converter.py assembles the output
   • Concatenates all chunk audio into one MP3
   • Names file: VoiceName__DocumentTitle__01_Chapter.mp3
   • Writes M3U playlist
        │
        ▼
7. gui/app.py updates the UI
   • Progress bar fills
   • Log tab records each step with timestamp
   • "Done!" dialog opens output folder
```

---

## File Responsibilities (The One-Sentence Rule)

| File | One sentence |
|---|---|
| `main.py` | Decides whether to launch the GUI or the CLI |
| `core/pdf_extractor.py` | Opens PDFs and finds chapters |
| `core/text_cleaner.py` | Makes text safe to read aloud |
| `core/ssml_builder.py` | Converts emotion tags into SSML markup |
| `core/converter.py` | Sends text to Edge-TTS and saves audio |
| `gui/app.py` | Shows the window and connects buttons to actions |

---

## Design Principles

**1. Core has no UI code. GUI has no business logic.**
The `core/` folder knows nothing about buttons, colours, or windows.
The `gui/` folder knows nothing about MP3 files or PDF parsing.
This separation means you can add a web API (FastAPI) or CLI without
touching the GUI, and redesign the GUI without touching the converter.

**2. Every file documents itself.**
Every function has a docstring explaining what it does, what it takes
as input, and what it returns. Future developers (including future you)
can understand any function in 30 seconds.

**3. Errors are logged, not silently ignored.**
Every exception is caught, logged to the Log tab, and reported to the
user with a clear message. The app never crashes silently.

**4. Files are never overwritten.**
Output filenames include the voice name and document title, so converting
the same PDF with two different voices produces two different files.

---

## AI Engineer Roadmap — Architecture Evolution

As we implement the roadmap, the architecture grows:

```
Current (v1.x):
  GUI App → core modules → Edge-TTS

After Step 2 (REST API):
  GUI App  ─┐
  Web App   ├→ FastAPI server → core modules → Edge-TTS
  Mobile    ─┘

After Step 3 (Automation):
  Folder watcher → pipeline → core modules → Edge-TTS
  MLflow ← tracks all conversions

After Step 4 (Analytics):
  SQLite database ← all conversions log here
  Pandas dashboard reads from SQLite

After Step 5 (ML Models):
  Hugging Face detector → auto-selects voice
  LangChain + RAG → answers questions about the PDF
  Scikit-learn → predicts conversion quality

After Step 6 (Web Demo):
  Gradio interface → core modules → Edge-TTS
  Public URL, no installation needed

After Step 7 (Scale):
  GitHub Actions → runs tests on every commit
  Docker Hub → stores container image
  Cloud server → runs 24/7
```

Each step adds a new "entry point" to the core — the core itself
barely changes. This is what good architecture looks like.
