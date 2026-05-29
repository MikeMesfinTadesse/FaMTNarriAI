"""
api/main.py — FaMTNarriAI REST API  v2.0
═══════════════════════════════════════════════════════════════════════════════

WHAT IS A REST API?
    A REST API is a way for different programs to talk to each other
    over the internet using HTTP — the same protocol your browser uses.

    Without API:  Only your desktop app can use FaMTNarriAI.
    With API:     Any app, website, script, or service anywhere can
                  convert text to audio by sending one HTTP request.

REAL-WORLD EXAMPLE:
    A mobile developer in Japan wants audiobook features in their app.
    Instead of rebuilding everything, they call your API:
        POST https://your-server.com/api/v2/convert
        Body: {"text": "昔むかし...", "voice": "ja-JP-NanamiNeural"}
    They get a job_id back, poll for status, then download the MP3.
    Your Python code powers their app. They never touch your code.

HOW TO START THE API:
    pip install -r requirements.txt
    uvicorn api.main:app --reload --port 8000

    Then open: http://localhost:8000/docs
    FastAPI generates interactive documentation automatically —
    you can test every endpoint in your browser with zero setup.

PHASE 2 ADDITIONS (vs v1):
    - API versioning  : all routes under /api/v2/
    - API key auth    : X-API-Key header (optional, for when you deploy)
    - Rate limiting   : max 10 requests/minute per key (in-memory)
    - /api/v2/stats   : live server statistics endpoint
    - /api/v2/health  : detailed health check with uptime
    - Richer responses: word_count, estimated_duration, language added
    - Better errors   : consistent error envelope {error, detail, hint}
    - CORS configured : ready for browser-based frontends

ENDPOINTS:
    GET  /                          Root redirect to docs
    GET  /api/v2/health             Health + uptime + version
    GET  /api/v2/stats              Live conversion statistics
    GET  /api/v2/voices             List all voices
    GET  /api/v2/voices/{lang}      Voices filtered by language code
    GET  /api/v2/languages          All languages grouped
    POST /api/v2/preview            Short audio preview (~30s)
    POST /api/v2/convert            Convert text → MP3 (async job)
    POST /api/v2/convert-pdf        Upload PDF/TXT → audiobook (async job)
    GET  /api/v2/jobs/{id}          Poll job status
    GET  /api/v2/jobs/{id}/download/{file}  Download completed MP3
    GET  /api/v2/jobs               List all jobs (admin)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import uuid
import time
import asyncio
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi import BackgroundTasks, Request, Depends
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.converter     import AudiobookConverter, VOICES, voice_short_name
from core.pdf_extractor import PDFExtractor, estimate_duration
from core.text_cleaner  import TextCleaner

# ── Constants ────────────────────────────────────────────────────────────────

VERSION     = "2.0.0"
API_PREFIX  = "/api/v2"
SERVER_START = time.time()

# Output directory for generated audio files
OUTPUT_DIR = Path(tempfile.gettempdir()) / "narraai_api_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job store  {job_id: {...}}
# In production Phase 3+ we replace this with Redis or SQLite
jobs: dict[str, dict] = {}

# In-memory stats counter
_stats: dict[str, int] = defaultdict(int)

# Simple in-memory rate limiter  {api_key: [timestamp, ...]}
_rate_limits: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))   # max requests
RATE_LIMIT_WINDOW   = int(os.getenv("RATE_LIMIT_WINDOW",   "60"))    # per N seconds


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "FaMTNarriAI API",
    description = (
        "## Transform text and PDFs into natural audiobooks\n\n"
        "FaMTNarriAI uses Microsoft Edge-TTS neural voices — **no API key required** "
        "for the TTS engine. 70+ voices across 20+ languages including Arabic, "
        "Amharic, Swahili, Japanese, Chinese, Korean.\n\n"
        "### Phase 2 — REST API\n"
        "This is Step 2 of the AI Engineer learning roadmap. "
        "The same core logic that powers the desktop GUI is now exposed as "
        "a REST API that any app can call.\n\n"
        "### Quick start\n"
        "```bash\n"
        "# Preview a voice\n"
        "curl -X POST http://localhost:8000/api/v2/preview \\\\\n"
        "  -H 'Content-Type: application/json' \\\\\n"
        "  -d '{\"text\": \"Hello!\", \"voice\": \"en-US-AriaNeural\"}'\n"
        "```"
    ),
    version     = VERSION,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],   # In production: replace with your frontend URL
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)


# ── Authentication (optional API key) ────────────────────────────────────────
# WHY API KEYS?
#   Without auth, anyone who finds your server URL can use it for free.
#   API keys let you: track who's using it, revoke access, set limits.
#   Here we make it OPTIONAL — no key needed for local development.
#   When you deploy, set API_KEY in your environment to enable it.

import os
_VALID_API_KEY = os.getenv("NARRAAI_API_KEY", "")   # empty = auth disabled

def check_api_key(request: Request) -> Optional[str]:
    """
    Optional API key authentication.
    If NARRAAI_API_KEY env var is set, all requests must include:
        Header: X-API-Key: your-key-here
    If the env var is empty, all requests are allowed (local dev mode).
    """
    if not _VALID_API_KEY:
        return "anonymous"   # auth disabled — local dev mode

    key = request.headers.get("X-API-Key", "")
    if key != _VALID_API_KEY:
        raise HTTPException(
            status_code = 401,
            detail      = {
                "error":  "Unauthorized",
                "detail": "Valid X-API-Key header required.",
                "hint":   "Set NARRAAI_API_KEY env var on the server, "
                          "then include X-API-Key: <key> in your request headers.",
            }
        )
    return key


def check_rate_limit(request: Request, api_key: str = Depends(check_api_key)):
    """
    Simple in-memory rate limiter: max 10 requests per 60 seconds per key.
    WHY RATE LIMITING?
        Prevents abuse, protects server resources, ensures fair usage.
        Real APIs use Redis for rate limiting across multiple servers.
        We use a simple in-memory dict here for learning purposes.
    """
    now       = time.time()
    key_times = _rate_limits[api_key]

    # Remove timestamps older than the window
    _rate_limits[api_key] = [t for t in key_times if now - t < RATE_LIMIT_WINDOW]

    if len(_rate_limits[api_key]) >= RATE_LIMIT_REQUESTS:
        oldest = _rate_limits[api_key][0]
        retry_after = int(RATE_LIMIT_WINDOW - (now - oldest)) + 1
        raise HTTPException(
            status_code = 429,
            detail      = {
                "error":       "Too Many Requests",
                "detail":      f"Rate limit: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s.",
                "retry_after": retry_after,
                "hint":        f"Wait {retry_after} seconds before retrying.",
            },
            headers = {"Retry-After": str(retry_after)},
        )

    _rate_limits[api_key].append(now)
    return api_key


# ── Pydantic Models ───────────────────────────────────────────────────────────
# Pydantic models do three things at once:
#   1. Validate incoming request data (wrong type → automatic 422 error)
#   2. Serialize outgoing response data (Python object → JSON automatically)
#   3. Generate API documentation (FastAPI reads these for /docs)

class ConvertRequest(BaseModel):
    """Request body for text-to-audio conversion."""
    text:  str   = Field(..., min_length=1,  description="Text to convert to audio")
    voice: str   = Field("en-US-AriaNeural", description="Edge-TTS voice ID. Use GET /api/v2/voices to browse all options.")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speed multiplier: 0.5 = slow, 1.0 = normal, 2.0 = fast")
    title: str   = Field("Chapter", description="Used in the output filename")

    model_config = {
        "json_schema_extra": {
            "example": {
                "text":  "(gentle) Once upon a time in a great green forest, there lived a brave little fox.",
                "voice": "en-US-AriaNeural",
                "speed": 1.0,
                "title": "The Brave Little Fox"
            }
        }
    }


class PreviewRequest(BaseModel):
    """Request body for generating a short voice preview."""
    text:  str   = Field(..., min_length=1, description="Text to preview (first 400 chars used)")
    voice: str   = Field("en-US-AriaNeural", description="Edge-TTS voice ID")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speed multiplier")

    model_config = {
        "json_schema_extra": {
            "example": {
                "text":  "Hello! I am your audiobook narrator. How do I sound?",
                "voice": "en-US-GuyNeural",
                "speed": 1.0
            }
        }
    }


class VoiceInfo(BaseModel):
    id:    str = Field(..., description="Voice ID — use this in convert requests")
    label: str = Field(..., description="Human-readable name")


class JobResponse(BaseModel):
    """Returned immediately when a conversion job is started."""
    job_id:   str = Field(..., description="Poll GET /api/v2/jobs/{job_id} with this ID")
    status:   str = Field(..., description="always 'running' when first created")
    message:  str
    poll_url: str = Field(..., description="Full URL to poll for job status")


class JobStatus(BaseModel):
    """Status of a conversion job."""
    job_id:    str
    status:    str = Field(..., description="running | done | failed")
    message:   str
    progress:  Optional[str] = None
    files:     list[str]     = []
    error:     Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


# ── Helper functions ─────────────────────────────────────────────────────────

def _validate_voice(voice: str) -> None:
    """Raise HTTP 400 if voice is not in the catalogue."""
    if voice not in VOICES:
        raise HTTPException(
            status_code = 400,
            detail      = {
                "error":  "Invalid voice",
                "detail": f"Voice '{voice}' is not in the catalogue.",
                "hint":   "Use GET /api/v2/voices to see all valid voice IDs.",
            }
        )

def _job_url(job_id: str) -> str:
    return f"/api/v2/jobs/{job_id}"

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to the interactive API docs."""
    return RedirectResponse(url="/docs")


@app.get(f"{API_PREFIX}/health", tags=["System"])
async def health():
    """
    Detailed health check — confirms the API is running and reports uptime.
    Use this in your monitoring / load balancer health checks.
    """
    uptime_seconds = int(time.time() - SERVER_START)
    hours, rem     = divmod(uptime_seconds, 3600)
    mins, secs     = divmod(rem, 60)
    return {
        "status":        "ok",
        "service":       "FaMTNarriAI API",
        "version":       VERSION,
        "uptime":        f"{hours}h {mins}m {secs}s",
        "uptime_seconds": uptime_seconds,
        "voices_loaded": len(VOICES),
        "jobs_in_memory": len(jobs),
        "auth_enabled":  bool(_VALID_API_KEY),
        "docs_url":      "/docs",
    }


@app.get(f"{API_PREFIX}/stats", tags=["System"])
async def stats(_key: str = Depends(check_rate_limit)):
    """
    Live server statistics — conversions completed, failures, total requests.
    Useful for monitoring how the API is being used.
    """
    done_jobs   = [j for j in jobs.values() if j["status"] == "done"]
    failed_jobs = [j for j in jobs.values() if j["status"] == "failed"]
    total_files = sum(len(j.get("files", [])) for j in done_jobs)

    return {
        "total_jobs":      len(jobs),
        "jobs_running":    sum(1 for j in jobs.values() if j["status"] == "running"),
        "jobs_done":       len(done_jobs),
        "jobs_failed":     len(failed_jobs),
        "total_mp3_files": total_files,
        "requests_served": _stats["requests"],
        "uptime_seconds":  int(time.time() - SERVER_START),
    }


@app.get(f"{API_PREFIX}/voices", response_model=list[VoiceInfo], tags=["Voices"])
async def list_voices(_key: str = Depends(check_rate_limit)):
    """
    List all available neural voices.

    Returns all 70+ voices with their ID and label.
    Use the `id` field in your `/convert` and `/preview` requests.

    **Tip:** Filter by language using `/api/v2/voices/{language_code}`.
    """
    _stats["requests"] += 1
    return [VoiceInfo(id=vid, label=label) for vid, label in VOICES.items()]


@app.get(f"{API_PREFIX}/voices/{{language_code}}", response_model=list[VoiceInfo], tags=["Voices"])
async def list_voices_by_language(
    language_code: str,
    _key: str = Depends(check_rate_limit),
):
    """
    List voices filtered by language code.

    | Code | Language    | Example voice              |
    |------|-------------|----------------------------|
    | en   | English     | en-US-AriaNeural           |
    | ar   | Arabic      | ar-SA-ZariyahNeural        |
    | am   | Amharic     | am-ET-MekdesNeural         |
    | sw   | Swahili     | sw-KE-ZuriNeural           |
    | ja   | Japanese    | ja-JP-NanamiNeural         |
    | zh   | Chinese     | zh-CN-XiaoxiaoNeural       |
    | ko   | Korean      | ko-KR-SunHiNeural          |
    | hi   | Hindi       | hi-IN-SwaraNeural          |
    | fr   | French      | fr-FR-DeniseNeural         |
    | de   | German      | de-DE-KatjaNeural          |
    | es   | Spanish     | es-ES-ElviraNeural         |
    | ru   | Russian     | ru-RU-SvetlanaNeural       |
    """
    _stats["requests"] += 1
    filtered = [
        VoiceInfo(id=vid, label=label)
        for vid, label in VOICES.items()
        if vid.startswith(language_code + "-")
    ]
    if not filtered:
        raise HTTPException(
            status_code = 404,
            detail      = {
                "error":  "Language not found",
                "detail": f"No voices found for language code '{language_code}'.",
                "hint":   "Try: en, ar, am, sw, ja, zh, ko, hi, fr, de, es, ru, it, pt, tr, nl, pl, sv, sk, fil",
            }
        )
    return filtered


@app.get(f"{API_PREFIX}/languages", tags=["Voices"])
async def list_languages(_key: str = Depends(check_rate_limit)):
    """
    List all supported languages, grouped with their voices.

    Returns a map of language code → list of voices.
    Useful for building language-picker dropdowns in your frontend.
    """
    _stats["requests"] += 1
    languages: dict[str, list] = {}
    for vid, label in VOICES.items():
        code = vid.split("-")[0]
        if code not in languages:
            languages[code] = []
        languages[code].append({"id": vid, "label": label})

    return {
        "total_languages": len(languages),
        "total_voices":    len(VOICES),
        "languages":       languages,
    }


@app.post(f"{API_PREFIX}/preview", tags=["Audio"])
async def preview(
    request: PreviewRequest,
    _key: str = Depends(check_rate_limit),
):
    """
    Generate a short audio preview (~30 seconds) to test a voice.

    Use this **before** committing to a full conversion — it's fast and
    lets you hear exactly how a voice sounds with your specific text.

    Returns the MP3 file directly as a download.

    **Tip:** Try 5 different voices on the same sentence to pick the best one.
    """
    _stats["requests"] += 1
    _validate_voice(request.voice)

    try:
        short = voice_short_name(request.voice)
        conv  = AudiobookConverter(
            voice          = request.voice,
            speed          = request.speed,
            output_dir     = str(OUTPUT_DIR),
            document_title = "preview",
        )
        # Use _preview_async directly — avoids asyncio.run() inside running loop
        result = await conv._preview_async(request.text, request.voice)
        _stats["previews"] += 1
        return FileResponse(
            path       = str(result),
            media_type = "audio/mpeg",
            filename   = f"preview_{short}.mp3",
            headers    = {
                "X-Voice": request.voice,
                "X-Speed": str(request.speed),
            },
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"error": "Voice unavailable", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "Preview failed", "detail": str(exc)})


@app.post(f"{API_PREFIX}/convert", response_model=JobResponse, tags=["Audio"])
async def convert_text(
    request: ConvertRequest,
    background_tasks: BackgroundTasks,
    _key: str = Depends(check_rate_limit),
):
    """
    Convert text to a full audiobook MP3.

    **This is an async job** — conversion runs in the background.

    **Flow:**
    1. POST here → get `job_id` immediately (fast, < 100ms)
    2. Poll `GET /api/v2/jobs/{job_id}` every 2–5 seconds
    3. When `status` is `"done"`, use the download URL in `files[]`

    **Why async?** Long texts can take minutes. We return immediately so
    your app stays responsive — no hanging HTTP connections.

    **Emotion tags** — add these to your text for expressive narration:
    `(gentle)`, `(whisper)`, `(excited)`, `(sad)`, `(dramatic)`,
    `(shout)`, `(pause)`, `(slow)`, `(fast)`
    """
    _stats["requests"] += 1
    _validate_voice(request.voice)

    # Count words and estimate duration for the response
    word_count = len(request.text.split())
    est_duration = estimate_duration(request.text)

    job_id = uuid.uuid4().hex
    jobs[job_id] = {
        "status":     "running",
        "files":      [],
        "error":      None,
        "created_at": _now_iso(),
        "meta":       {
            "voice":      request.voice,
            "speed":      request.speed,
            "word_count": word_count,
            "title":      request.title,
            "est_duration": est_duration,
        }
    }

    async def _run():
        try:
            chapter        = {"title": request.title, "text": request.text,
                              "word_count": word_count, "approved": True}
            job_dir        = OUTPUT_DIR / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            conv           = AudiobookConverter(
                voice          = request.voice,
                speed          = request.speed,
                output_dir     = str(job_dir),
                document_title = request.title,
            )
            files = conv.convert_chapters([chapter], playlist=False)
            jobs[job_id]["status"]       = "done"
            jobs[job_id]["files"]        = [f.name for f in files]
            jobs[job_id]["completed_at"] = _now_iso()
            _stats["conversions_done"] += 1
        except Exception as exc:
            jobs[job_id]["status"]       = "failed"
            jobs[job_id]["error"]        = str(exc)
            jobs[job_id]["completed_at"] = _now_iso()
            _stats["conversions_failed"] += 1

    background_tasks.add_task(_run)
    return JobResponse(
        job_id   = job_id,
        status   = "running",
        message  = f"Conversion started. ~{est_duration} for {word_count} words.",
        poll_url = _job_url(job_id),
    )


@app.post(f"{API_PREFIX}/convert-pdf", response_model=JobResponse, tags=["Audio"])
async def convert_pdf(
    background_tasks: BackgroundTasks,
    file:  UploadFile = File(...,  description="PDF or TXT file to convert"),
    voice: str        = Form(default="en-US-AriaNeural", description="Edge-TTS voice ID"),
    speed: float      = Form(default=1.0, ge=0.5, le=2.0, description="Speed multiplier"),
    _key: str = Depends(check_rate_limit),
):
    """
    Upload a PDF or TXT file and convert it to a full audiobook.

    **Flow:**
    1. Upload file here → get `job_id` immediately
    2. The server extracts text, detects chapters, cleans artifacts
    3. Converts each chapter to MP3 in the background
    4. Poll `GET /api/v2/jobs/{job_id}` until `status = "done"`
    5. Download each file from the `files[]` list

    **Supported formats:** `.pdf`, `.txt`
    **Max size:** 50MB
    """
    _stats["requests"] += 1
    _validate_voice(voice)

    filename = file.filename or "upload"
    suffix   = Path(filename).suffix.lower()
    if suffix not in (".pdf", ".txt"):
        raise HTTPException(
            status_code = 400,
            detail      = {
                "error":  "Unsupported file type",
                "detail": f"Got '{suffix}'. Only .pdf and .txt are supported.",
                "hint":   "Convert other formats to PDF first.",
            }
        )

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code = 413,
            detail      = {"error": "File too large", "detail": "Maximum file size is 50MB."}
        )

    upload_path = OUTPUT_DIR / f"upload_{uuid.uuid4().hex}{suffix}"
    upload_path.write_bytes(content)

    job_id = uuid.uuid4().hex
    jobs[job_id] = {
        "status":     "running",
        "files":      [],
        "error":      None,
        "created_at": _now_iso(),
        "meta":       {"voice": voice, "speed": speed, "source_file": filename}
    }

    async def _run():
        try:
            cleaner = TextCleaner()
            if suffix == ".pdf":
                extractor = PDFExtractor(str(upload_path))
                chapters  = extractor.extract_chapters()
                for ch in chapters:
                    ch["text"] = cleaner.clean(ch["text"])
            else:
                raw = upload_path.read_text(encoding="utf-8", errors="replace")
                chapters = [{"title": Path(filename).stem,
                             "text":  cleaner.clean(raw),
                             "word_count": len(raw.split())}]

            jobs[job_id]["meta"]["chapters_found"] = len(chapters)

            job_dir = OUTPUT_DIR / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            conv    = AudiobookConverter(
                voice          = voice,
                speed          = speed,
                output_dir     = str(job_dir),
                document_title = Path(filename).stem,
            )
            files = conv.convert_chapters(chapters, playlist=True)
            jobs[job_id]["status"]       = "done"
            jobs[job_id]["files"]        = [f.name for f in files]
            jobs[job_id]["completed_at"] = _now_iso()
            _stats["pdf_conversions_done"] += 1
        except Exception as exc:
            jobs[job_id]["status"]       = "failed"
            jobs[job_id]["error"]        = str(exc)
            jobs[job_id]["completed_at"] = _now_iso()
            _stats["conversions_failed"] += 1
        finally:
            upload_path.unlink(missing_ok=True)

    background_tasks.add_task(_run)
    return JobResponse(
        job_id   = job_id,
        status   = "running",
        message  = f"'{filename}' uploaded and processing started.",
        poll_url = _job_url(job_id),
    )


@app.get(f"{API_PREFIX}/jobs/{{job_id}}", response_model=JobStatus, tags=["Jobs"])
async def get_job(job_id: str, _key: str = Depends(check_rate_limit)):
    """
    Poll the status of a conversion job.

    **Status values:**
    - `running` — conversion in progress, check again in 2–5 seconds
    - `done`    — conversion complete, files ready to download
    - `failed`  — conversion failed, read the `error` field

    When `done`, build download URLs:
    `GET /api/v2/jobs/{job_id}/download/{filename}`
    """
    _stats["requests"] += 1
    if job_id not in jobs:
        raise HTTPException(
            status_code = 404,
            detail      = {
                "error":  "Job not found",
                "detail": f"No job with id '{job_id}'.",
                "hint":   "Jobs are stored in memory — they are lost on server restart.",
            }
        )

    job      = jobs[job_id]
    messages = {
        "running": "Conversion in progress…",
        "done":    f"Complete — {len(job['files'])} file(s) ready to download.",
        "failed":  f"Failed: {job.get('error', 'unknown error')}",
    }
    return JobStatus(
        job_id       = job_id,
        status       = job["status"],
        message      = messages.get(job["status"], ""),
        files        = [f"/api/v2/jobs/{job_id}/download/{f}" for f in job.get("files", [])],
        error        = job.get("error"),
        created_at   = job.get("created_at"),
        completed_at = job.get("completed_at"),
    )


@app.get(f"{API_PREFIX}/jobs/{{job_id}}/download/{{filename}}", tags=["Jobs"])
async def download_file(
    job_id: str,
    filename: str,
    _key: str = Depends(check_rate_limit),
):
    """
    Download a completed MP3 file.

    Only call this after `GET /api/v2/jobs/{job_id}` returns `status: done`.
    Get valid `filename` values from the `files[]` array in the job status.
    """
    _stats["requests"] += 1
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail={"error": "Job not found"})

    if jobs[job_id]["status"] != "done":
        raise HTTPException(
            status_code = 409,
            detail      = {
                "error":  "Job not ready",
                "detail": f"Job status is '{jobs[job_id]['status']}', not 'done'.",
                "hint":   f"Poll GET /api/v2/jobs/{job_id} and wait for status=done.",
            }
        )

    file_path = OUTPUT_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(
            status_code = 404,
            detail      = {
                "error":  "File not found",
                "detail": f"File '{filename}' does not exist in job '{job_id}'.",
            }
        )

    return FileResponse(
        path       = str(file_path),
        media_type = "audio/mpeg",
        filename   = filename,
    )


@app.get(f"{API_PREFIX}/jobs", tags=["Jobs"])
async def list_jobs(_key: str = Depends(check_rate_limit)):
    """
    List all jobs — useful for debugging and monitoring.

    In production you would filter by user/API key.
    For now returns all jobs in memory.
    """
    _stats["requests"] += 1
    return {
        "total":   len(jobs),
        "running": sum(1 for j in jobs.values() if j["status"] == "running"),
        "done":    sum(1 for j in jobs.values() if j["status"] == "done"),
        "failed":  sum(1 for j in jobs.values() if j["status"] == "failed"),
        "jobs": {
            jid: {
                "status":     j["status"],
                "files":      j.get("files", []),
                "created_at": j.get("created_at"),
                "meta":       j.get("meta", {}),
            }
            for jid, j in jobs.items()
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Phase 2 Addition — ElevenLabs endpoints
#  These are OPTIONAL — they only work if ELEVENLABS_API_KEY is set.
#  If no key is set, they return a clear 503 with setup instructions.
# ══════════════════════════════════════════════════════════════════════════════

def _get_el_key() -> str:
    """
    Return ElevenLabs API key from environment.
    Raises HTTP 503 with setup instructions if not configured.
    """
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code = 503,
            detail = {
                "error":  "ElevenLabs not configured",
                "detail": "ELEVENLABS_API_KEY environment variable is not set.",
                "hint": (
                    "1. Sign up free at https://elevenlabs.io\n"
                    "2. Go to Profile → API Key → copy it\n"
                    "3. Set it:  Windows: set ELEVENLABS_API_KEY=your-key\n"
                    "           Linux/Mac: export ELEVENLABS_API_KEY=your-key\n"
                    "4. Restart the server"
                ),
            }
        )
    return key


@app.get(f"{API_PREFIX}/elevenlabs/voices", tags=["ElevenLabs"])
async def el_list_voices(_key: str = Depends(check_rate_limit)):
    """
    List all ElevenLabs voices available on your account.

    Returns built-in voices plus any cloned voices you have created.
    Requires `ELEVENLABS_API_KEY` environment variable.

    **Free tier** includes 9 built-in voices.
    **Creator plan+** unlocks voice cloning.
    """
    el_key = _get_el_key()
    try:
        from core.elevenlabs_tts import fetch_voices
        voices = fetch_voices(el_key)
        _stats["requests"] += 1
        return {
            "engine":       "elevenlabs",
            "total_voices": len(voices),
            "voices":       voices,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail={"error": "Auth failed", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "Failed", "detail": str(exc)})


class ELConvertRequest(BaseModel):
    """Request body for ElevenLabs text-to-speech conversion."""
    model_config = {"protected_namespaces": ()}
    text:             str   = Field(..., min_length=1, description="Text to convert")
    voice_id:         str   = Field(..., description="ElevenLabs voice ID from GET /elevenlabs/voices")
    voice_name:       str   = Field("ElevenLabs", description="Display name for the output filename")
    model_id:         str   = Field("eleven_multilingual_v2", description="ElevenLabs model")
    stability:        float = Field(0.5, ge=0.0, le=1.0, description="Voice stability 0–1")
    similarity_boost: float = Field(0.75, ge=0.0, le=1.0, description="Similarity boost 0–1")
    title:            str   = Field("Chapter", description="Used in output filename")
    speed:            float = Field(1.0, ge=0.5, le=2.0, description="Speed (not used by ElevenLabs, kept for API consistency)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "text":             "(gentle) Once upon a time in the Enchanted Forest...",
                "voice_id":         "21m00Tcm4TlvDq8ikWAM",
                "voice_name":       "Rachel",
                "model_id":         "eleven_multilingual_v2",
                "stability":        0.5,
                "similarity_boost": 0.75,
                "title":            "Chapter 1"
            }
        }
    }


@app.post(f"{API_PREFIX}/elevenlabs/convert", response_model=JobResponse, tags=["ElevenLabs"])
async def el_convert(
    request: ELConvertRequest,
    background_tasks: BackgroundTasks,
    _key: str = Depends(check_rate_limit),
):
    """
    Convert text to MP3 using ElevenLabs premium neural voices.

    **Why ElevenLabs vs Edge-TTS?**

    | Feature            | Edge-TTS          | ElevenLabs           |
    |--------------------|-------------------|----------------------|
    | Cost               | Free              | Free tier / Paid     |
    | Voice quality      | Very good         | Best available       |
    | Voice cloning      | ❌               | ✅ Creator plan+     |
    | Languages          | 40+               | 29+ (auto-detected)  |
    | Emotion control    | Tags (gentle etc) | Stability slider     |

    **Flow:** Same async job pattern as `/convert`.
    1. POST here → get `job_id`
    2. Poll `GET /api/v2/jobs/{job_id}`
    3. When `done`, download from `files[]`

    **Requires:** `ELEVENLABS_API_KEY` environment variable.
    """
    el_key     = _get_el_key()
    word_count = len(request.text.split())
    job_id     = uuid.uuid4().hex

    jobs[job_id] = {
        "status":     "running",
        "files":      [],
        "error":      None,
        "created_at": _now_iso(),
        "meta": {
            "engine":     "elevenlabs",
            "voice_id":   request.voice_id,
            "voice_name": request.voice_name,
            "model_id":   request.model_id,
            "word_count": word_count,
            "title":      request.title,
        }
    }

    async def _run():
        try:
            from core.elevenlabs_tts import ElevenLabsConverter
            job_dir = OUTPUT_DIR / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            chapter = {"title": request.title, "text": request.text}
            conv    = ElevenLabsConverter(
                api_key          = el_key,
                voice_id         = request.voice_id,
                voice_name       = request.voice_name,
                model_id         = request.model_id,
                stability        = request.stability,
                similarity_boost = request.similarity_boost,
                output_dir       = str(job_dir),
                document_title   = request.title,
            )
            files = conv.convert_chapters([chapter], playlist=False)
            jobs[job_id]["status"]       = "done"
            jobs[job_id]["files"]        = [f.name for f in files]
            jobs[job_id]["completed_at"] = _now_iso()
            _stats["el_conversions_done"] = _stats.get("el_conversions_done", 0) + 1
        except Exception as exc:
            jobs[job_id]["status"]       = "failed"
            jobs[job_id]["error"]        = str(exc)
            jobs[job_id]["completed_at"] = _now_iso()

    background_tasks.add_task(_run)
    return JobResponse(
        job_id   = job_id,
        status   = "running",
        message  = f"ElevenLabs conversion started for {word_count} words.",
        poll_url = _job_url(job_id),
    )


@app.post(f"{API_PREFIX}/elevenlabs/preview", tags=["ElevenLabs"])
async def el_preview(
    request: ELConvertRequest,
    _key: str = Depends(check_rate_limit),
):
    """
    Generate a short ElevenLabs voice preview (~30 seconds).
    Returns the MP3 file directly.

    **Requires:** `ELEVENLABS_API_KEY` environment variable.
    """
    el_key = _get_el_key()
    try:
        from core.elevenlabs_tts import ElevenLabsConverter
        conv = ElevenLabsConverter(
            api_key          = el_key,
            voice_id         = request.voice_id,
            voice_name       = request.voice_name,
            model_id         = request.model_id,
            stability        = request.stability,
            similarity_boost = request.similarity_boost,
            output_dir       = str(OUTPUT_DIR),
            document_title   = "preview",
        )
        result = conv.preview(request.text)
        _stats["el_previews"] = _stats.get("el_previews", 0) + 1
        return FileResponse(
            path       = str(result),
            media_type = "audio/mpeg",
            filename   = result.name,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"error": "ElevenLabs error", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "Preview failed", "detail": str(exc)})


class CloneRequest(BaseModel):
    """Request to clone a voice from audio samples."""
    name:        str  = Field(..., min_length=1, description="Name for the cloned voice")
    description: str  = Field("", description="Optional description")

    model_config = {
        "json_schema_extra": {
            "example": {"name": "My Voice", "description": "My custom cloned voice"}
        }
    }


@app.post(f"{API_PREFIX}/elevenlabs/clone", tags=["ElevenLabs"])
async def el_clone_voice(
    name:        str        = Form(..., description="Name for the cloned voice"),
    description: str        = Form(default=""),
    files:       list[UploadFile] = File(..., description="Audio samples (MP3/WAV, 1–5 files, ~1 min total)"),
    _key: str = Depends(check_rate_limit),
):
    """
    Clone a voice from your audio samples.

    Upload 1–5 clean MP3 or WAV recordings (minimum ~1 minute total audio).
    The cloned voice appears immediately in your ElevenLabs account and
    in the response from `GET /api/v2/elevenlabs/voices`.

    **Requires:**
    - `ELEVENLABS_API_KEY` environment variable
    - ElevenLabs Creator plan or above
    """
    el_key = _get_el_key()
    import tempfile as _tmp
    tmp_paths = []
    try:
        for f in files:
            suffix   = Path(f.filename or "audio.mp3").suffix
            tmp_file = _tmp.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp_file.write(await f.read())
            tmp_file.close()
            tmp_paths.append(tmp_file.name)

        from core.elevenlabs_tts import clone_voice
        result = clone_voice(el_key, name, tmp_paths, description)
        return {
            "success":  True,
            "voice_id": result.get("voice_id"),
            "name":     name,
            "message":  f"Voice '{name}' cloned successfully. Use voice_id in /elevenlabs/convert.",
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail={"error": "Clone failed", "detail": str(exc)})
    finally:
        for p in tmp_paths:
            try:
                Path(p).unlink()
            except Exception:
                pass
