# Changelog — FaMTNarriAI Audiobook Studio

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/)

---

## [Unreleased] — Phase 2 (REST API)
- FastAPI server: POST /convert, POST /convert-pdf, GET /voices
- Authentication via API key
- Postman collection for testing

---

## [1.5.0] — Phase 1 Complete — Version Control & Infrastructure
### Added
- `.github/workflows/test.yml` — CI pipeline runs on every push
  - Tests on Python 3.10, 3.11, 3.12
  - pip caching for faster runs
  - Coverage reporting with artifact upload
- `.github/workflows/docker.yml` — auto-build and push to Docker Hub
- `.github/pull_request_template.md` — PR checklist
- `.github/BRANCH_PROTECTION.md` — branch rule setup guide
- `Dockerfile` — multi-stage build (smaller, faster)
- `.dockerignore` — excludes GUI, tests, audio files from container
- `scripts/setup_github.sh` — one-command GitHub setup (Linux/Mac)
- `scripts/setup_github.bat` — one-command GitHub setup (Windows)
- `scripts/daily_workflow.md` — Git workflow reference

### Changed
- `Dockerfile` upgraded to multi-stage build (40% smaller image)
- CI workflow now caches pip packages (faster subsequent runs)
- CI now tests 3 Python versions in parallel

---

## [1.4.0] — 2026-04
### Added
- Tigrinya language via Amharic voice + Google Translate
- Filipino (fil-PH): BlessicaNeural F, AngeloNeural M
- Kids Section: language selector + translation for stories

---

## [1.3.0]
### Added
- Languages tab: 15+ languages with voice selector
- Translation via deep-translator (Google Translate, no API key)
- Amharic, Swahili, Slovak voices

---

## [1.2.0]
### Added
- Kids Section tab with 3 built-in stories
- Language-aware Kids voice selector
- Story templates: Fantasy, Horror, Children, News

---

## [1.1.0]
### Added
- Voice Tester tab — test any voice with custom sentence
- Page Range tab — convert specific PDF pages
- Emotion tags: whisper, excited, sad, shout, dramatic, gentle, pause

---

## [1.0.0] — Initial Release
### Added
- Desktop GUI with CustomTkinter (dark/light mode)
- Editor tab with emotion tags
- Chapters tab with approve/reject per chapter
- PDF loading with auto-chapter detection
- Edge-TTS neural voices (50+ voices)
- Log tab with timestamps
- CLI mode: python main.py --cli --input book.pdf
