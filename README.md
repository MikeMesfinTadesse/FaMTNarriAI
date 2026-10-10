# 🎙️ FaMTNarriAI — Audiobook Studio

> Transform any text or PDF into a natural-sounding audiobook using Microsoft Edge-TTS neural voices.

![CI Status](https://img.shields.io/github/actions/workflow/status/YOUR_USERNAME/FaMTNarriAI/test.yml?label=tests&style=flat-square)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?style=flat-square&logo=docker)

> **Replace `YOUR_USERNAME` with your GitHub username after pushing.**

---

## ✨ Features

| Tab | What it does |
|-----|-------------|
| ✏️ **Editor** | Type/paste text, add emotion tags, convert to audio |
| 📑 **Chapters** | Load PDF → auto-detect chapters → approve/reject each |
| 📄 **Page Range** | Convert any specific page range from a PDF |
| 🎤 **Voice Tester** | Preview any of 50+ voices with your own sentence |
| 🌍 **Languages** | Convert in 15+ languages with optional translation |
| 🧒 **Kids Section** | Children's stories with warm voices + translation |
| ⚡ **Templates** | One-click sample texts to get started |
| 📋 **Log** | Timestamped record of all activity |

---

## 🚀 Quick Start

### Option A — Desktop App (recommended)

```bash
# 1. Install Python 3.10+ from python.org

# 2. Install dependencies
pip install -r requirements.txt
pip install deep-translator    # optional: enables Translate button

# 3. Run
python main.py
```

### Option B — CLI (no GUI, great for scripts)

```bash
python main.py --cli --input mybook.pdf --voice en-US-AriaNeural
python main.py --cli --input chapter.txt --voice ar-SA-ZariyahNeural --speed 0.9
python main.py --cli --help
```

### Option C — Docker (no Python install needed)

```bash
docker pull YOUR_USERNAME/famtnarriai
docker run -v $(pwd)/output:/app/output YOUR_USERNAME/famtnarriai \
  --input /app/output/mybook.pdf --voice en-US-AriaNeural
```

---

## 🎭 Emotion Tags

Add these anywhere in your text to change how it sounds:

| Tag | Effect | Example |
|-----|--------|---------|
| `(whisper)` | Soft and quiet | `(whisper) It was a secret.` |
| `(excited)` | Fast and high | `(excited) She found the treasure!` |
| `(gentle)` | Slow and warm | `(gentle) Once upon a time…` |
| `(dramatic)` | Slow and intense | `(dramatic) The door creaked open.` |
| `(sad)` | Slow and low | `(sad) He never returned.` |
| `(shout)` | Loud and fast | `(shout) Run!` |
| `(pause)` | Short silence | `He waited. (pause) Nothing.` |

---

## 🌍 Supported Languages

Arabic · Japanese · Chinese · French · German · Spanish · Russian · Korean · Hindi · Turkish · Slovak · Swahili · Amharic · Filipino · Tigrinya · English (US, GB, AU, CA, IE, IN) + more

---

## 🏗️ Architecture

```
User
 │
 ▼
gui/app.py  (Desktop window — CustomTkinter)
 │
 ▼
core/
  pdf_extractor.py  → reads PDFs, finds chapters
  text_cleaner.py   → removes URLs, fixes PDF artifacts
  ssml_builder.py   → converts emotion tags to SSML
  converter.py      → sends to Edge-TTS, saves MP3
 │
 ▼
Microsoft Edge-TTS (free, no API key)
 │
 ▼
Output MP3 files  ~/NarraAI_Output/
```

---

## 🔬 Running Tests

```bash
pip install pytest
pytest tests/ -v
```

Tests cover: text cleaning, chunking, PDF extraction, filename generation.

---

## 🐳 Docker

```bash
# Build locally
docker build -t famtnarriai .

# Convert a PDF
docker run -v $(pwd)/output:/app/output famtnarriai \
  --input /app/output/book.pdf --voice en-US-AriaNeural
```

---

## 🗺️ Roadmap

| Phase | Status | What |
|-------|--------|------|
| 1 — Version Control | ✅ Done | Git + GitHub + Docker + CI |
| 2 — REST API | 📋 Next | FastAPI: POST /convert, GET /voices |
| 3 — Automation | 📋 | Folder watcher + MLflow tracking |
| 4 — Analytics | 📋 | SQLite + Pandas + Matplotlib dashboard |
| 5 — ML Models | 📋 | Auto language detection + RAG Q&A |
| 6 — Web Demo | 📋 | Gradio public demo |
| 7 — Scale | 📋 | Kubernetes + Argo CD + Prometheus |

---

## 📁 Output Files

Audio files are saved to `~/NarraAI_Output/` (changeable in the app).

Filename format: `VoiceName__DocumentTitle__01_ChapterTitle.mp3`

Example: `Aria__The_Iron_Wizard__01_The_Awakening.mp3`

Files are **never overwritten** — each conversion gets a unique name.

---

## 📄 License

MIT — free to use, modify, and distribute.
