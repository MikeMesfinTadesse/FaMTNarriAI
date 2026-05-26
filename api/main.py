"""
api/main.py — NarraAI REST API
═══════════════════════════════════════════════════════════════

WHAT IS A REST API?
    A REST API is a way for different programs to talk to each other
    over the internet using HTTP (the same protocol your browser uses).

    Without API:   Only your desktop app can use NarraAI.
    With API:      Any app, website, or script anywhere can use NarraAI
                   by sending an HTTP request and getting audio back.

REAL-WORLD EXAMPLE:
    A mobile app developer in Japan wants to add audiobook features.
    Instead of rebuilding everything, they call your API:
      POST https://your-server.com/convert
      Body: {"text": "Once upon a time...", "voice": "ja-JP-NanamiNeural"}
    They get an MP3 back. Done. Your Python code powers their app.

HOW TO RUN THIS API:
    pip install fastapi uvicorn python-multipart
    uvicorn api.main:app --reload --port 8000

    Then open: http://localhost:8000/docs
    FastAPI automatically generates interactive API documentation!
    You can test every endpoint directly in your browser.

HOW TO TEST WITH CURL:
    curl -X POST http://localhost:8000/convert \
      -H "Content-Type: application/json" \
      -d '{"text": "Hello world", "voice": "en-US-AriaNeural"}'

AI ENGINEER CONTEXT:
    This is Step 2 of the roadmap: "Turn ML models into APIs/tools"
    The core logic (converter.py) did not change at all.
    We just added a new front door — the API — that any app can use.
    This is the correct pattern: separate business logic from interface.

ENDPOINTS:
    GET  /                  Health check — is the server running?
    GET  /voices            List all available voices
    GET  /voices/{language} List voices for a specific language
    GET  /languages         List all supported languages
    POST /preview           Generate a short audio preview (< 30 sec)
    POST /convert           Convert text to a full MP3 audiobook
    POST /convert-pdf       Upload a PDF and convert it to audio
    GET  /status/{job_id}   Check status of a running conversion

═══════════════════════════════════════════════════════════════
"""

import sys
import uuid
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

# Add project root to path so we can import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.converter     import AudiobookConverter, VOICES, voice_short_name
from core.pdf_extractor import PDFExtractor, estimate_duration
from core.text_cleaner  import TextCleaner


# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NarraAI API",
    description=(
        "Convert text and PDF documents to audiobooks using neural voices.\n\n"
        "**AI Engineer Roadmap — Step 2:** Wrapping an ML pipeline as a REST API.\n\n"
        "All audio is generated using Microsoft Edge-TTS neural voices. "
        "No API key required."
    ),
    version="1.0.0",
    docs_url="/docs",      # Interactive docs at /docs
    redoc_url="/redoc",    # Alternative docs at /redoc
)

# CORS: allows web browsers from other origins to call this API
# In production, replace "*" with your specific frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output directory for generated audio files
OUTPUT_DIR = Path(tempfile.gettempdir()) / "narraai_api_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job tracker (in production, use Redis or a database)
# Structure: {job_id: {"status": "running"|"done"|"failed", "files": [], "error": ""}}
jobs: dict[str, dict] = {}


# ── Request / Response Models ─────────────────────────────────────────────────
# Pydantic models define exactly what JSON shape the API accepts and returns.
# FastAPI uses these for automatic validation AND automatic documentation.

class ConvertRequest(BaseModel):
    """Request body for text-to-audio conversion."""
    text:     str   = Field(..., description="Text to convert to audio", min_length=1)
    voice:    str   = Field("en-US-AriaNeural", description="Edge-TTS voice name")
    speed:    float = Field(1.0, ge=0.5, le=2.0, description="Speed multiplier 0.5–2.0")
    title:    str   = Field("Chapter", description="Used in the output filename")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Once upon a time in a great green forest...",
                "voice": "en-US-AriaNeural",
                "speed": 1.0,
                "title": "The Brave Little Fox"
            }
        }


class PreviewRequest(BaseModel):
    """Request body for generating a short preview clip."""
    text:  str   = Field(..., description="Text to preview (first 400 words used)", min_length=1)
    voice: str   = Field("en-US-AriaNeural", description="Edge-TTS voice name")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speed multiplier")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello! I am your audiobook narrator. How do I sound?",
                "voice": "en-US-GuyNeural",
                "speed": 1.0
            }
        }


class VoiceInfo(BaseModel):
    """Information about a single voice."""
    id:    str = Field(..., description="Edge-TTS voice ID")
    label: str = Field(..., description="Human-readable label")


class ConvertResponse(BaseModel):
    """Response from a text conversion request."""
    job_id:   str = Field(..., description="Use this ID to check job status")
    status:   str = Field(..., description="running | done | failed")
    message:  str = Field(..., description="Human-readable status message")


class JobStatus(BaseModel):
    """Status of a conversion job."""
    job_id:    str
    status:    str
    message:   str
    files:     list[str] = []
    error:     Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def health_check():
    """
    Health check — confirms the API is running.
    Use this to verify your server is up before sending requests.
    """
    return {
        "status":  "ok",
        "service": "NarraAI API",
        "version": "1.0.0",
        "message": "API is running. Visit /docs for interactive documentation."
    }


@app.get("/voices", response_model=list[VoiceInfo], tags=["Voices"])
async def list_voices():
    """
    List all available neural voices.

    Returns every voice NarraAI supports, with its ID and human label.
    Use the 'id' value in your convert requests.
    """
    return [
        VoiceInfo(id=voice_id, label=label)
        for voice_id, label in VOICES.items()
    ]


@app.get("/voices/{language_code}", response_model=list[VoiceInfo], tags=["Voices"])
async def list_voices_by_language(language_code: str):
    """
    List voices filtered by language code.

    Examples:
    - /voices/en    → all English voices
    - /voices/ar    → all Arabic voices
    - /voices/am    → Amharic voices
    - /voices/sw    → Swahili voices
    - /voices/ja    → Japanese voices
    """
    filtered = [
        VoiceInfo(id=vid, label=label)
        for vid, label in VOICES.items()
        if vid.startswith(language_code + "-")
    ]
    if not filtered:
        raise HTTPException(
            status_code=404,
            detail=f"No voices found for language code '{language_code}'. "
                   f"Try 'en', 'ar', 'am', 'sw', 'ja', 'zh', 'ko', 'hi', 'fr', 'de', 'es'."
        )
    return filtered


@app.get("/languages", tags=["Voices"])
async def list_languages():
    """
    List all supported language codes and their available voices.
    Grouped by language for easy browsing.
    """
    # Group voices by language prefix (e.g. "en", "ar", "am")
    languages: dict[str, list] = {}
    for vid, label in VOICES.items():
        lang_code = vid.split("-")[0]  # "en-US-AriaNeural" → "en"
        if lang_code not in languages:
            languages[lang_code] = []
        languages[lang_code].append({"id": vid, "label": label})

    return {
        "total_languages": len(languages),
        "total_voices":    len(VOICES),
        "languages":       languages
    }


@app.post("/preview", tags=["Audio"])
async def preview_voice(request: PreviewRequest):
    """
    Generate a short audio preview (first ~400 words of text).

    Use this to test how a voice sounds before committing to a full conversion.
    Returns the audio file directly as an MP3 download.

    Tip: Try multiple voices on the same text to compare them.
    """
    # Validate voice
    if request.voice not in VOICES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown voice '{request.voice}'. "
                   f"Use GET /voices to see all valid voice IDs."
        )

    try:
        short   = voice_short_name(request.voice)
        out_path = OUTPUT_DIR / f"preview_{short}_{uuid.uuid4().hex[:8]}.mp3"

        conv = AudiobookConverter(
            voice=request.voice,
            speed=request.speed,
            output_dir=str(OUTPUT_DIR),
            document_title="preview",
        )
        result = conv.preview(request.text, voice=request.voice)

        # Move to unique filename so concurrent requests don't collide
        result.rename(out_path)

        return FileResponse(
            path=str(out_path),
            media_type="audio/mpeg",
            filename=f"preview_{short}.mp3",
            headers={"X-Voice": request.voice, "X-Speed": str(request.speed)},
        )

    except RuntimeError as exc:
        # Voice validation failed
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Preview failed: {exc}")


@app.post("/convert", response_model=ConvertResponse, tags=["Audio"])
async def convert_text(request: ConvertRequest, background_tasks: BackgroundTasks):
    """
    Convert text to a full audiobook MP3.

    This is an **async job** — the conversion runs in the background.
    You get a job_id immediately. Poll GET /status/{job_id} to check progress.
    When status is 'done', use GET /download/{job_id} to get your file.

    Why async? Long texts can take minutes. We don't make you wait
    with an open HTTP connection — you check back when it's ready.
    """
    if request.voice not in VOICES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown voice '{request.voice}'. Use GET /voices to list valid IDs."
        )

    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "running", "files": [], "error": None}

    async def run_conversion():
        try:
            chapter = {
                "title":      request.title,
                "text":       request.text,
                "word_count": len(request.text.split()),
                "approved":   True,
            }
            job_output_dir = OUTPUT_DIR / job_id
            job_output_dir.mkdir(parents=True, exist_ok=True)

            conv = AudiobookConverter(
                voice=request.voice,
                speed=request.speed,
                output_dir=str(job_output_dir),
                document_title=request.title,
            )
            files = conv.convert_chapters([chapter], playlist=False)
            jobs[job_id]["status"] = "done"
            jobs[job_id]["files"]  = [f.name for f in files]
        except Exception as exc:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"]  = str(exc)

    background_tasks.add_task(run_conversion)

    return ConvertResponse(
        job_id=job_id,
        status="running",
        message=f"Conversion started. Poll GET /status/{job_id} to check progress."
    )


@app.post("/convert-pdf", response_model=ConvertResponse, tags=["Audio"])
async def convert_pdf(
    background_tasks: BackgroundTasks,
    file:  UploadFile = File(..., description="PDF or TXT file to convert"),
    voice: str        = Form(default="en-US-AriaNeural", description="Edge-TTS voice ID"),
    speed: float      = Form(default=1.0, ge=0.5, le=2.0, description="Speed multiplier"),
):
    """
    Upload a PDF or TXT file and convert it to an audiobook.

    The file is processed automatically:
    1. Text extracted from PDF
    2. Chapters detected
    3. Text cleaned (removes URLs, page numbers, artifacts)
    4. Each chapter converted to MP3

    Returns a job_id — poll GET /status/{job_id} to check progress.
    """
    if voice not in VOICES:
        raise HTTPException(status_code=400, detail=f"Unknown voice '{voice}'.")

    # Validate file type
    filename = file.filename or "upload"
    suffix   = Path(filename).suffix.lower()
    if suffix not in (".pdf", ".txt"):
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF and TXT files are supported. Got: {suffix}"
        )

    # Save uploaded file to a temp location
    upload_path = OUTPUT_DIR / f"upload_{uuid.uuid4().hex}{suffix}"
    content = await file.read()
    upload_path.write_bytes(content)

    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "running", "files": [], "error": None}

    async def run_pdf_conversion():
        try:
            cleaner = TextCleaner()

            if suffix == ".pdf":
                extractor = PDFExtractor(str(upload_path))
                chapters  = extractor.extract_chapters()
                for ch in chapters:
                    ch["text"] = cleaner.clean(ch["text"])
            else:
                raw_text = upload_path.read_text(encoding="utf-8", errors="replace")
                chapters = [{"title": Path(filename).stem,
                             "text": cleaner.clean(raw_text),
                             "word_count": len(raw_text.split())}]

            job_output_dir = OUTPUT_DIR / job_id
            job_output_dir.mkdir(parents=True, exist_ok=True)

            conv  = AudiobookConverter(
                voice=voice,
                speed=speed,
                output_dir=str(job_output_dir),
                document_title=Path(filename).stem,
            )
            files = conv.convert_chapters(chapters, playlist=True)
            jobs[job_id]["status"]   = "done"
            jobs[job_id]["files"]    = [f.name for f in files]
            jobs[job_id]["chapters"] = len(chapters)

        except Exception as exc:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"]  = str(exc)
        finally:
            # Clean up the uploaded temp file
            upload_path.unlink(missing_ok=True)

    background_tasks.add_task(run_pdf_conversion)

    return ConvertResponse(
        job_id=job_id,
        status="running",
        message=f"PDF uploaded and processing started. Poll GET /status/{job_id}."
    )


@app.get("/status/{job_id}", response_model=JobStatus, tags=["Jobs"])
async def get_job_status(job_id: str):
    """
    Check the status of a conversion job.

    Status values:
    - **running** — conversion is in progress
    - **done**    — conversion complete, files ready for download
    - **failed**  — conversion failed, check the 'error' field

    Poll this endpoint every 2–5 seconds until status is 'done' or 'failed'.
    """
    if job_id not in jobs:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found. "
                   f"Jobs are kept in memory — they are lost if the server restarts."
        )

    job = jobs[job_id]
    messages = {
        "running": "Conversion in progress...",
        "done":    f"Complete. {len(job['files'])} file(s) ready.",
        "failed":  f"Failed: {job.get('error', 'unknown error')}",
    }

    return JobStatus(
        job_id=job_id,
        status=job["status"],
        message=messages.get(job["status"], "Unknown status"),
        files=job.get("files", []),
        error=job.get("error"),
    )


@app.get("/download/{job_id}/{filename}", tags=["Jobs"])
async def download_file(job_id: str, filename: str):
    """
    Download a converted audio file.

    First check GET /status/{job_id} — only call this when status is 'done'.
    The 'files' list in the status response gives you the valid filenames.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if jobs[job_id]["status"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Job '{job_id}' is not done yet. Status: {jobs[job_id]['status']}"
        )

    file_path = OUTPUT_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found in job '{job_id}'."
        )

    media_type = "audio/mpeg" if filename.endswith(".mp3") else "application/octet-stream"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )


@app.get("/jobs", tags=["Jobs"])
async def list_all_jobs():
    """
    List all jobs and their current status.
    Useful for monitoring and debugging.
    """
    return {
        "total":   len(jobs),
        "running": sum(1 for j in jobs.values() if j["status"] == "running"),
        "done":    sum(1 for j in jobs.values() if j["status"] == "done"),
        "failed":  sum(1 for j in jobs.values() if j["status"] == "failed"),
        "jobs":    {jid: {"status": j["status"], "files": j.get("files", [])}
                    for jid, j in jobs.items()},
    }
