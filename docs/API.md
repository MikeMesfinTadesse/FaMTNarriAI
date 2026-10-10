# FaMTNarriAI REST API — Reference

**Version:** 2.0.0  
**Base URL (local):** `http://localhost:8000`  
**Interactive docs:** `http://localhost:8000/docs`  

---

## Start the API

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` — FastAPI generates a full interactive
UI where you can test every endpoint in your browser with no extra tools.

---

## Authentication (optional)

By default auth is **disabled** — no key needed for local development.

To enable, set the environment variable before starting:
```bash
# Windows
set NARRAAI_API_KEY=your-secret-key-here
uvicorn api.main:app --reload

# Linux / Mac
NARRAAI_API_KEY=your-secret-key-here uvicorn api.main:app --reload
```

When enabled, every request must include:
```
X-API-Key: your-secret-key-here
```

---

## Rate Limiting

**10 requests per 60 seconds** per API key (or per IP when auth disabled).

Exceeded limit returns:
```json
HTTP 429 Too Many Requests
Retry-After: 45

{
  "detail": {
    "error": "Too Many Requests",
    "detail": "Rate limit: 10 requests per 60s.",
    "retry_after": 45
  }
}
```

---

## Endpoints

### System

#### `GET /api/v2/health`
Health check with uptime and version.

```bash
curl http://localhost:8000/api/v2/health
```
```json
{
  "status": "ok",
  "version": "2.0.0",
  "uptime": "0h 5m 12s",
  "voices_loaded": 70,
  "auth_enabled": false
}
```

#### `GET /api/v2/stats`
Live conversion statistics.

```json
{
  "total_jobs": 12,
  "jobs_running": 1,
  "jobs_done": 10,
  "jobs_failed": 1,
  "total_mp3_files": 47,
  "uptime_seconds": 3600
}
```

---

### Voices

#### `GET /api/v2/voices`
List all 70+ neural voices.

```bash
curl http://localhost:8000/api/v2/voices
```
```json
[
  {"id": "en-US-AriaNeural",     "label": "Aria (Expressive, F)"},
  {"id": "ar-SA-ZariyahNeural",  "label": "Zariyah (SA, F)"},
  {"id": "am-ET-MekdesNeural",   "label": "Mekdes (ET, F)"},
  ...
]
```

#### `GET /api/v2/voices/{language_code}`
Filter voices by language code.

| Code | Language   | Code | Language |
|------|-----------|------|---------|
| `en` | English   | `ar` | Arabic  |
| `am` | Amharic   | `sw` | Swahili |
| `ja` | Japanese  | `zh` | Chinese |
| `ko` | Korean    | `hi` | Hindi   |
| `fr` | French    | `de` | German  |
| `es` | Spanish   | `ru` | Russian |

```bash
curl http://localhost:8000/api/v2/voices/ar
```

#### `GET /api/v2/languages`
All languages grouped with their voices.

---

### Audio

#### `POST /api/v2/preview`
Generate a short voice preview (~30 seconds). Returns MP3 directly.

```bash
curl -X POST http://localhost:8000/api/v2/preview \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello! How do I sound?", "voice": "en-US-AriaNeural"}' \
  --output preview.mp3
```

**Request body:**
```json
{
  "text":  "Your text here",
  "voice": "en-US-AriaNeural",
  "speed": 1.0
}
```

| Field | Type  | Required | Default           | Range    |
|-------|-------|----------|-------------------|----------|
| text  | str   | ✅       | —                 | min 1 char |
| voice | str   | ❌       | en-US-AriaNeural  | see /voices |
| speed | float | ❌       | 1.0               | 0.5–2.0 |

**Response:** MP3 file download (Content-Type: audio/mpeg)

---

#### `POST /api/v2/convert`
Convert text to a full audiobook MP3. Returns a job ID immediately.

```bash
curl -X POST http://localhost:8000/api/v2/convert \
  -H "Content-Type: application/json" \
  -d '{
    "text":  "(gentle) Once upon a time, in a great green forest...",
    "voice": "en-US-AriaNeural",
    "speed": 1.0,
    "title": "The Forest Story"
  }'
```

**Request body:**
```json
{
  "text":  "Your text here. Can be very long.",
  "voice": "en-US-AriaNeural",
  "speed": 1.0,
  "title": "Chapter Title"
}
```

**Emotion tags** (add anywhere in text):

| Tag          | Effect              |
|--------------|---------------------|
| `(gentle)`   | Slow, soft, warm    |
| `(whisper)`  | Quiet, breathy      |
| `(excited)`  | Fast, high pitch    |
| `(sad)`      | Slow, low pitch     |
| `(dramatic)` | Intense, slow       |
| `(shout)`    | Loud, fast          |
| `(pause)`    | Short silence       |
| `(slow)`     | Very slow           |
| `(fast)`     | Very fast           |

**Response:**
```json
{
  "job_id":   "a1b2c3d4e5f6...",
  "status":   "running",
  "message":  "Conversion started. ~2 min for 1500 words.",
  "poll_url": "/api/v2/jobs/a1b2c3d4e5f6..."
}
```

---

#### `POST /api/v2/convert-pdf`
Upload a PDF or TXT file. Returns a job ID immediately.

```bash
curl -X POST http://localhost:8000/api/v2/convert-pdf \
  -F "file=@mybook.pdf" \
  -F "voice=en-US-AriaNeural" \
  -F "speed=1.0"
```

**Form fields:**

| Field | Type  | Required | Default          |
|-------|-------|----------|------------------|
| file  | file  | ✅       | —                |
| voice | str   | ❌       | en-US-AriaNeural |
| speed | float | ❌       | 1.0              |

**Supported:** `.pdf`, `.txt` — max 50MB

---

### Jobs

#### `GET /api/v2/jobs/{job_id}`
Poll job status. Call every 2–5 seconds until `status` is `done` or `failed`.

```bash
curl http://localhost:8000/api/v2/jobs/a1b2c3d4e5f6
```
```json
{
  "job_id":       "a1b2c3d4e5f6",
  "status":       "done",
  "message":      "Complete — 3 file(s) ready to download.",
  "files":        [
    "/api/v2/jobs/a1b2c3/download/01_Chapter_One.mp3",
    "/api/v2/jobs/a1b2c3/download/02_Chapter_Two.mp3"
  ],
  "created_at":   "2026-05-27T10:00:00Z",
  "completed_at": "2026-05-27T10:02:45Z"
}
```

**Status values:**

| Status    | Meaning                                    |
|-----------|--------------------------------------------|
| `running` | In progress — keep polling                 |
| `done`    | Ready — use the download URLs in `files[]` |
| `failed`  | Error — check the `error` field            |

#### `GET /api/v2/jobs/{job_id}/download/{filename}`
Download a completed MP3. Only works when job status is `done`.

```bash
curl http://localhost:8000/api/v2/jobs/a1b2c3/download/01_Chapter.mp3 \
  --output chapter1.mp3
```

#### `GET /api/v2/jobs`
List all jobs (admin/debug use).

---

## Full workflow example (Python)

```python
import requests
import time

BASE = "http://localhost:8000"

# 1. Start conversion
resp = requests.post(f"{BASE}/api/v2/convert", json={
    "text":  "(gentle) Once upon a time... (excited) She found the treasure!",
    "voice": "en-US-AriaNeural",
    "speed": 1.0,
    "title": "My Story"
})
job_id = resp.json()["job_id"]
print(f"Job started: {job_id}")

# 2. Poll until done
while True:
    status = requests.get(f"{BASE}/api/v2/jobs/{job_id}").json()
    print(f"Status: {status['status']}")
    if status["status"] == "done":
        break
    if status["status"] == "failed":
        print("Error:", status["error"])
        exit(1)
    time.sleep(3)

# 3. Download each file
for file_url in status["files"]:
    filename = file_url.split("/")[-1]
    audio = requests.get(f"{BASE}{file_url}")
    with open(filename, "wb") as f:
        f.write(audio.content)
    print(f"Saved: {filename}")
```

---

## Error responses

All errors return a consistent JSON envelope:

```json
{
  "detail": {
    "error":  "Short error name",
    "detail": "Human-readable explanation",
    "hint":   "What to do to fix it"
  }
}
```

| HTTP Code | Meaning                                    |
|-----------|--------------------------------------------|
| 400       | Bad request (invalid voice, wrong format)  |
| 401       | Missing or invalid API key                 |
| 404       | Job or resource not found                  |
| 409       | Conflict (job not done yet)                |
| 413       | File too large (> 50MB)                    |
| 422       | Validation error (wrong type, out of range)|
| 429       | Rate limit exceeded                        |
| 503       | Voice temporarily unavailable              |
| 500       | Server error                               |
