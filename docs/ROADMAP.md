# NarraAI — AI Engineer Roadmap

This document tracks the implementation of all 7 steps of the
AI Engineer roadmap using NarraAI as the learning project.

Each step teaches real skills, produces a real deliverable,
and makes NarraAI genuinely better.

---

## Status Key
- ✅ Complete
- 🔄 In progress
- 📋 Planned

---

## Step 1 — Build & Manage AI Infrastructure
**Skills:** Git, GitHub, Docker, Cloud Deployment
**Status:** 🔄 In progress

### Deliverables
- [x] Professional `.gitignore`
- [x] `requirements.txt` with documented dependencies
- [x] `Dockerfile` for containerised deployment
- [x] `CONTRIBUTING.md` — how to develop on the project
- [x] `CHANGELOG.md` — version history
- [x] `docs/ARCHITECTURE.md` — system design documentation
- [ ] GitHub repository created and code pushed
- [ ] `README.md` updated with badges and architecture diagram
- [ ] Streamlit web version deployed to Streamlit Cloud

### How to run with Docker (once built)
```bash
# Build the container
docker build -t narraai .

# Convert a PDF (mounts your local output folder)
docker run -v $(pwd)/output:/app/output narraai \
  --input /app/input/mybook.pdf \
  --voice en-US-AriaNeural

# It just works — same on any machine
```

### Key learning from this step
Git teaches you to track every change you ever make.
If you break something, you can always go back.
Docker teaches you that "it works on my machine" is not good enough —
your code must work on every machine, automatically.

---

## Step 2 — Turn ML Models into APIs
**Skills:** FastAPI, REST APIs, HTTP, Postman, Authentication
**Status:** 📋 Planned

### What we will build
A FastAPI server that wraps NarraAI so any app can use it:

```
POST /convert          Send text + voice → receive MP3
POST /convert-pdf      Send PDF file → receive audiobook ZIP
GET  /voices           List all available voices
GET  /languages        List supported languages
POST /preview          Send text → receive 30-second preview
```

### Files to create
- `api/main.py` — FastAPI application
- `api/routes/convert.py` — conversion endpoints
- `api/routes/voices.py` — voice listing endpoints
- `docs/API.md` — API reference documentation

### Key learning from this step
This is how every professional AI product works.
The AI logic lives in Python. The API is the door.
Anyone — a website, a mobile app, another script — can
send a request and get audio back without knowing Python.

---

## Step 3 — Automate AI Workflows
**Skills:** Automation, Scheduling, MLflow, Pipeline Design
**Status:** 📋 Planned

### What we will build
- `scripts/watch_folder.py` — drop PDF in folder → MP3 appears automatically
- `scripts/batch_convert.py` — convert 100 PDFs in one command
- MLflow integration — track every conversion as an "experiment"

### Key learning from this step
Automation removes the human from repetitive tasks.
MLflow teaches you to track AI system performance over time —
essential for knowing if a change made things better or worse.

---

## Step 4 — Run Statistical Analysis for Decisions
**Skills:** Pandas, Matplotlib, SQLite, Data Analysis
**Status:** 📋 Planned

### What we will build
- SQLite database logging every conversion
- Pandas analysis: which voice is fastest, which language fails most
- Matplotlib charts: conversion time, success rate, word count distribution
- Streamlit analytics dashboard

### Key learning from this step
Data tells you what is actually happening, not what you assume.
After 100 conversions you will know: which voice is most reliable,
which language needs the most retries, what chunk size works best.

---

## Step 5 — Develop AI/ML/DL Models
**Skills:** Hugging Face, LangChain, RAG, Scikit-learn, Vector Databases
**Status:** 📋 Planned

### What we will build

**Feature A — Auto language detection**
User loads Arabic PDF → app detects Arabic → selects correct voice automatically.
Uses Hugging Face `papluca/xlm-roberta-base-language-detection`.

**Feature B — PDF question answering (RAG)**
User asks "what happens in chapter 3?" → app searches the PDF → answers from real content.
Uses LangChain + ChromaDB vector database + OpenAI/Claude API.
This is the core skill from Turing College Sprint 2.

**Feature C — Conversion quality predictor**
Before converting, app predicts: "this will take ~4 minutes, 8% retry risk."
Uses Scikit-learn trained on data collected in Step 4.

### Key learning from this step
This is where NarraAI becomes genuinely intelligent.
Steps 1-4 made it professional. Step 5 makes it smart.
RAG (Retrieval-Augmented Generation) is the most in-demand
AI engineering skill of 2025-2026.

---

## Step 6 — Work with PMs to Make Prototypes
**Skills:** Gradio, Streamlit, Rapid Prototyping
**Status:** 📋 Planned

### What we will build
A Gradio web demo at a public URL:
- Upload PDF or type text
- Select language and voice
- Click Convert
- Download MP3 — all in a browser, no installation

```python
import gradio as gr
demo = gr.Interface(
    fn=convert_for_demo,
    inputs=[gr.File(), gr.Dropdown(voices), gr.Dropdown(languages)],
    outputs=gr.Audio(),
    title="NarraAI — PDF to Audiobook"
)
demo.launch(share=True)  # public URL instantly
```

### Key learning from this step
A prototype that non-technical people can use in a browser
is worth more than perfect code they can't access.
This is how you show your work in interviews and to stakeholders.

---

## Step 7 — Collaborate to Scale AI & Improve Practices
**Skills:** pytest, GitHub Actions, CI/CD, MLOps, Documentation
**Status:** 📋 Planned

### What we will build
- `tests/test_text_cleaner.py` — automated tests
- `tests/test_pdf_extractor.py` — automated tests
- `tests/test_converter.py` — automated tests
- `.github/workflows/test.yml` — GitHub Actions: runs tests on every commit
- Deployment pipeline: push to GitHub → tests run → Docker image built

### Key learning from this step
CI/CD (Continuous Integration / Continuous Deployment) means
your code is always tested, always deployable.
Every professional software team uses this.
When you work with others, automated tests catch bugs before
they reach users.

---

## Portfolio Summary (after all 7 steps)

When complete, NarraAI demonstrates:

| Skill | Evidence |
|---|---|
| Cloud infrastructure | Docker container + Streamlit Cloud deployment |
| REST API development | FastAPI server with 5 documented endpoints |
| Pipeline automation | Folder watcher + nightly batch + MLflow tracking |
| Data analysis | SQLite + Pandas + Matplotlib analytics dashboard |
| ML model integration | Hugging Face language detection + RAG Q&A |
| Rapid prototyping | Gradio public web demo |
| Professional practices | pytest + GitHub Actions + full documentation |

This is a complete AI Engineer portfolio from one real project.
