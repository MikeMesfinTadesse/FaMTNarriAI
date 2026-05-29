# Contributing to NarraAI

This document explains how to add new features to NarraAI.
It is written so that anyone — including future you — can pick up the project
and extend it without breaking anything.

---

## How to Set Up Your Development Environment

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/narraai.git
cd narraai

# 2. Create a virtual environment
#    This keeps NarraAI's packages separate from your other Python projects
python -m venv venv

# 3. Activate it
#    On Windows:
venv\Scripts\activate
#    On Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the app to confirm it works
python main.py
```

---

## How to Add a New Language

**File to edit:** `core/converter.py` and `gui/app.py`

### Step 1 — Find the voice ID

Visit: https://tts.travisvn.com/ and find voices for your language.
Voice IDs follow the pattern: `xx-XX-VoiceNameNeural`
Example: `ar-EG-SalmaNeural` = Arabic, Egypt, Salma, Neural voice

### Step 2 — Add to converter.py

Open `core/converter.py` and find the `VOICES` dictionary.
Add your new voices in the correct language section:

```python
# ── Yoruba (example — not real, just showing format) ──────────
"yo-NG-YorubaVoiceNeural":   "VoiceName (NG, F)",
```

### Step 3 — Add to app.py

Open `gui/app.py` and find `MULTILANG_VOICES`. Add a new entry:

```python
"🇳🇬 Yoruba":  [
    ("yo-NG-VoiceNeural", "VoiceName, F"),
],
```

Also add a sample sentence to `LANG_SAMPLES`:

```python
"🇳🇬 Yoruba":  "Ẹ káàbọ̀ sí NarraAI.\nA le yí ọrọ eyikeyi sí ohùn didara.",
```

And a translation code to `LANG_TO_TRANSLATE_CODE`:

```python
"🇳🇬 Yoruba":  "yo",
```

### Step 4 — Test it

Run the app, go to the Languages tab, select your new language,
click "Test voice" and confirm it reads correctly.

---

## How to Add a New Feature

Before writing code, ask these three questions:

1. **Which file does this belong in?**
   - PDF reading logic → `core/pdf_extractor.py`
   - Text cleaning logic → `core/text_cleaner.py`
   - Audio conversion logic → `core/converter.py`
   - UI / buttons / tabs → `gui/app.py`
   - App startup / CLI → `main.py`

2. **Does it break anything existing?**
   - Run `pytest tests/` before and after your change

3. **Did you document it?**
   - Add a docstring to any new function
   - Update `CHANGELOG.md` with what changed

---

## Code Style Rules

We follow these rules so the code is consistent and readable:

```python
# ✓ Good: clear variable names
voice_short_name = "Aria"
conversion_time_seconds = 47.3

# ✗ Bad: cryptic abbreviations
vsn = "Aria"
t = 47.3

# ✓ Good: every function has a docstring
def estimate_duration(text: str, wpm: int = 150) -> str:
    """
    Estimate spoken duration from word count at a given words-per-minute rate.
    Returns a human-readable string like '4m 32s' or '1h 12m'.
    """

# ✓ Good: type hints on all function parameters
def convert_chapters(self, chapters: list[dict], playlist: bool = True) -> list[Path]:

# ✗ Bad: no type hints
def convert_chapters(self, chapters, playlist):
```

---

## Branch Strategy (Git Workflow)

```
main          ← always working, always deployable
  └── feature/add-yoruba-language     ← your new feature
  └── feature/fastapi-endpoint        ← Step 2 of roadmap
  └── fix/arabic-sentence-splitting   ← bug fixes
  └── docs/update-readme              ← documentation only
```

**Never commit directly to `main`.** Always:
1. Create a branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Commit: `git commit -m "Add Yoruba language support"`
4. Push: `git push origin feature/your-feature-name`
5. Open a Pull Request on GitHub

---

## Commit Message Format

```
type: short description (max 60 characters)

Longer explanation if needed. What changed and why.
What problem does this solve? What was the old behaviour?
```

Types:
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `refactor:` — code restructure, no behaviour change
- `test:` — adding or fixing tests
- `chore:` — dependency updates, config changes

Examples:
```
feat: add Tigrinya language via Amharic voice + translation
fix: sentence splitter now handles Arabic punctuation correctly
docs: add CONTRIBUTING.md with language addition guide
refactor: extract _safe_filename into standalone utility function
test: add unit tests for text_cleaner PDF artifact removal
```

---

## File Structure Reference

```
narraai/
├── main.py                    # Entry point — GUI or CLI launcher
├── requirements.txt           # Python package dependencies
├── Dockerfile                 # Container definition for deployment
├── .gitignore                 # Files Git should never track
├── README.md                  # Project overview and quick start
├── CONTRIBUTING.md            # This file — how to develop
├── CHANGELOG.md               # History of all changes by version
│
├── core/                      # Business logic — no UI here
│   ├── __init__.py
│   ├── converter.py           # TTS engine, voice catalogue, chunker
│   ├── pdf_extractor.py       # PDF reading, chapter detection
│   ├── text_cleaner.py        # Text sanitisation pipeline
│   └── ssml_builder.py        # Emotion tag → SSML conversion
│
├── gui/                       # Desktop UI only — no business logic
│   ├── __init__.py
│   └── app.py                 # All tabs, buttons, callbacks
│
├── tests/                     # Automated tests
│   ├── test_text_cleaner.py
│   ├── test_pdf_extractor.py
│   └── test_converter.py
│
├── docs/                      # Extended documentation
│   ├── ARCHITECTURE.md        # System design diagram + explanation
│   ├── ROADMAP.md             # AI Engineer roadmap implementation plan
│   └── API.md                 # REST API reference (Step 2)
│
└── scripts/                   # Utility scripts
    ├── watch_folder.py        # Auto-convert PDFs dropped in a folder
    └── batch_convert.py       # Convert many PDFs at once from CLI
```
