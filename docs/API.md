# NarraAI REST API Reference

This document describes every endpoint in the NarraAI API.

The API is built with FastAPI. When running locally, visit
**http://localhost:8000/docs** for interactive documentation where
you can test every endpoint directly in your browser — no Postman needed.

---

## How to Start the API Server

```bash
# Install API dependencies
pip install fastapi uvicorn python-multipart httpx

# Start the server (from the narraai/ project root)
uvicorn api.main:app --reload --port 8000

# --reload means the server restarts automatically when you edit code
# --port 8000 means it runs at http://localhost:8000
```

---

## Base URL

```
Local development:   http://localhost:8000
Production (future): https://your-server.com
```

---

## Endpoints

---

### GET /

Health check — confirms the server is running.

**Request:** No body needed.

**Response:**
```json
{
  "status": "ok",
  "service": "NarraAI API",
  "version": "1.0.0",
  "message": "API is running. Visit /docs for interactive documentation."
}
```

**Use case:** Before sending any requests, ping this to confirm the server is up.

---

### GET /voices

List all available neural voices.

**Response:**
```json
[
  {"id": "en-US-AriaNeural",  "label": "Aria (Expressive, F)"},
  {"id": "en-US-GuyNeural",   "label": "Guy (Friendly, M)"},
  {"id": "ar-SA-ZariyahNeural", "label": "Zariyah — Saudi Arabia, F"},
  {"id": "am-ET-MekdesNeural", "label": "Mekdes (ET, F)"},
  ...
]
```

Use the `id` value in your convert requests.

---

### GET /voices/{language_code}

List voices for a specific language.

**URL Parameters:**
| Parameter | Description | Example |
|---|---|---|
| `language_code` | Two-letter language prefix | `en`, `ar`, `am`, `sw`, `ja` |

**Examples:**
```
GET /voices/en   → all English voices
GET /voices/ar   → all Arabic voices
GET /voices/am   → Amharic voices
GET /voices/sw   → Swahili voices
GET /voices/fil  → Filipino voices
```

**Error (404):** Language code not found.

---

### GET /languages

List all supported languages grouped with their voices.

**Response:**
```json
{
  "total_languages": 18,
  "total_voices": 78,
  "languages": {
    "en": [
      {"id": "en-US-AriaNeural", "label": "Aria (Expressive, F)"},
      ...
    ],
    "ar": [...],
    "am": [...]
  }
}
```

---

### POST /preview

Generate a short audio preview (first ~400 words).

Use this to hear how a voice sounds before running a full conversion.

**Request body:**
```json
{
  "text":  "Once upon a time in a great green forest...",
  "voice": "en-US-AriaNeural",
  "speed": 1.0
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `text` | string | ✓ | — | Text to preview |
| `voice` | string | | `en-US-AriaNeural` | Voice ID from GET /voices |
| `speed` | float | | `1.0` | Speed: 0.5 (slow) to 2.0 (fast) |

**Response:** MP3 audio file (direct download)
- Content-Type: `audio/mpeg`
- Header `X-Voice`: voice used
- Header `X-Speed`: speed used

**Error (400):** Unknown voice ID.
**Error (503):** Voice unavailable (Microsoft server issue).

**Example with curl:**
```bash
curl -X POST http://localhost:8000/preview \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello! How do I sound?", "voice": "en-US-AriaNeural"}' \
  --output preview.mp3
```

---

### POST /convert

Convert text to a full audiobook MP3.

This is an **async operation** — you get a `job_id` immediately
and poll `GET /status/{job_id}` to check progress.

**Request body:**
```json
{
  "text":  "Once upon a time in a great green forest, there lived a little fox named Felix...",
  "voice": "en-US-AriaNeural",
  "speed": 1.0,
  "title": "The Brave Little Fox"
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `text` | string | ✓ | — | Text to convert |
| `voice` | string | | `en-US-AriaNeural` | Voice ID |
| `speed` | float | | `1.0` | Speed 0.5–2.0 |
| `title` | string | | `"Chapter"` | Used in the output filename |

**Response:**
```json
{
  "job_id":  "a3f8c2d1e5b94f7a...",
  "status":  "running",
  "message": "Conversion started. Poll GET /status/a3f8c2d1e5b94f7a... to check progress."
}
```

**Workflow:**
```
1. POST /convert            → get job_id
2. GET  /status/{job_id}    → poll until status = "done"
3. GET  /download/{job_id}/{filename}  → download MP3
```

---

### POST /convert-pdf

Upload a PDF or TXT file and convert it to an audiobook.

**Request:** `multipart/form-data`
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | ✓ | PDF or TXT file |
| `voice` | string | | Voice ID (default: `en-US-AriaNeural`) |
| `speed` | float | | Speed 0.5–2.0 (default: `1.0`) |

**Response:**
```json
{
  "job_id":  "b7d3a9f1...",
  "status":  "running",
  "message": "PDF uploaded and processing started. Poll GET /status/b7d3a9f1..."
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8000/convert-pdf \
  -F "file=@mybook.pdf" \
  -F "voice=en-US-AriaNeural" \
  -F "speed=1.1"
```

**Error (400):** Unsupported file type (only `.pdf` and `.txt` accepted).

---

### GET /status/{job_id}

Check the status of a conversion job.

**Response:**
```json
{
  "job_id":  "a3f8c2d1e5b94f7a...",
  "status":  "done",
  "message": "Complete. 3 file(s) ready.",
  "files":   [
    "Aria__MyBook__01_Chapter_One.mp3",
    "Aria__MyBook__02_Chapter_Two.mp3",
    "Aria__MyBook__03_Chapter_Three.mp3"
  ],
  "error":   null
}
```

**Status values:**
| Status | Meaning |
|---|---|
| `running` | Conversion in progress |
| `done` | Complete — use `/download` to get files |
| `failed` | Failed — check `error` field |

**Error (404):** Job ID not found.

---

### GET /download/{job_id}/{filename}

Download a converted audio file.

Only call this when `GET /status/{job_id}` returns `status: "done"`.
The filenames are listed in the `files` array of the status response.

**Response:** MP3 or M3U file (direct download)

**Error (404):** Job or file not found.
**Error (409):** Job not done yet.

---

### GET /jobs

List all jobs and their status. Useful for monitoring.

**Response:**
```json
{
  "total":   5,
  "running": 1,
  "done":    3,
  "failed":  1,
  "jobs": {
    "a3f8c2d1...": {"status": "done",    "files": ["Aria__Book__01.mp3"]},
    "b7d3a9f1...": {"status": "running", "files": []},
    "c1e4b8a2...": {"status": "failed",  "files": []}
  }
}
```

---

## Full Example Workflow

```python
import requests
import time

BASE = "http://localhost:8000"

# 1. Check server is running
resp = requests.get(f"{BASE}/")
print(resp.json()["status"])   # "ok"

# 2. Pick a voice
voices = requests.get(f"{BASE}/voices/en").json()
voice_id = voices[0]["id"]
print(f"Using: {voice_id}")

# 3. Preview the voice
preview = requests.post(f"{BASE}/preview", json={
    "text": "Hello! This is how I sound as your narrator.",
    "voice": voice_id
})
with open("preview.mp3", "wb") as f:
    f.write(preview.content)
print("Preview saved to preview.mp3")

# 4. Submit a full conversion
job = requests.post(f"{BASE}/convert", json={
    "text":  "Chapter one. The story begins on a rainy Tuesday morning...",
    "voice": voice_id,
    "speed": 1.1,
    "title": "My Story"
}).json()
job_id = job["job_id"]
print(f"Job started: {job_id}")

# 5. Poll until done
while True:
    status = requests.get(f"{BASE}/status/{job_id}").json()
    print(f"Status: {status['status']}")
    if status["status"] in ("done", "failed"):
        break
    time.sleep(2)

# 6. Download the file
if status["status"] == "done":
    for filename in status["files"]:
        audio = requests.get(f"{BASE}/download/{job_id}/{filename}")
        with open(filename, "wb") as f:
            f.write(audio.content)
        print(f"Downloaded: {filename}")
```

---

## Error Codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 400 | Bad request — invalid voice, wrong file type |
| 404 | Not found — unknown job ID or language |
| 409 | Conflict — job not done yet |
| 422 | Validation error — missing field, value out of range |
| 500 | Server error — unexpected failure |
| 503 | Service unavailable — Edge-TTS voice not working |
