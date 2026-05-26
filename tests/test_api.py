"""
tests/test_api.py
═══════════════════════════════════════════════════════════════

WHAT IS BEING TESTED HERE?
    The FastAPI endpoints — the HTTP routes that external apps call.

HOW DOES THIS WORK WITHOUT A RUNNING SERVER?
    FastAPI includes a TestClient that simulates HTTP requests
    without actually starting a server. You can test every endpoint
    the same way a real client would call it — in milliseconds.

    This is called "integration testing" — you test that all the
    pieces work together, not just individual functions.

HOW TO RUN:
    pip install pytest httpx fastapi
    pytest tests/test_api.py -v
═══════════════════════════════════════════════════════════════
"""

import sys
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock edge_tts before any imports that depend on it
sys.modules['edge_tts'] = unittest.mock.MagicMock()

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


# ── Health check ─────────────────────────────────────────────────────────────

def test_health_check_returns_ok():
    """GET / should return status ok."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "NarraAI" in data["service"]


# ── Voices endpoints ──────────────────────────────────────────────────────────

def test_list_voices_returns_list():
    """GET /voices should return a non-empty list."""
    response = client.get("/voices")
    assert response.status_code == 200
    voices = response.json()
    assert isinstance(voices, list)
    assert len(voices) > 0


def test_list_voices_have_id_and_label():
    """Each voice should have an 'id' and 'label' field."""
    response = client.get("/voices")
    voices = response.json()
    for voice in voices[:5]:  # check first 5
        assert "id"    in voice
        assert "label" in voice
        assert len(voice["id"]) > 0
        assert len(voice["label"]) > 0


def test_list_voices_includes_aria():
    """en-US-AriaNeural should be in the voice list."""
    response = client.get("/voices")
    voice_ids = [v["id"] for v in response.json()]
    assert "en-US-AriaNeural" in voice_ids


def test_list_voices_includes_amharic():
    """Amharic voice should be in the list."""
    response = client.get("/voices")
    voice_ids = [v["id"] for v in response.json()]
    assert "am-ET-MekdesNeural" in voice_ids


def test_list_voices_includes_swahili():
    """Swahili voice should be in the list."""
    response = client.get("/voices")
    voice_ids = [v["id"] for v in response.json()]
    assert "sw-KE-ZuriNeural" in voice_ids


def test_list_voices_by_language_english():
    """GET /voices/en should return only English voices."""
    response = client.get("/voices/en")
    assert response.status_code == 200
    voices = response.json()
    assert len(voices) > 0
    for voice in voices:
        assert voice["id"].startswith("en-")


def test_list_voices_by_language_arabic():
    """GET /voices/ar should return only Arabic voices."""
    response = client.get("/voices/ar")
    assert response.status_code == 200
    voices = response.json()
    for voice in voices:
        assert voice["id"].startswith("ar-")


def test_list_voices_unknown_language_returns_404():
    """GET /voices/xx for unknown language should return 404."""
    response = client.get("/voices/xx")
    assert response.status_code == 404


def test_list_languages_structure():
    """GET /languages should return grouped language data."""
    response = client.get("/languages")
    assert response.status_code == 200
    data = response.json()
    assert "total_languages" in data
    assert "total_voices"    in data
    assert "languages"       in data
    assert data["total_languages"] > 0
    assert data["total_voices"]    > 0


# ── Preview endpoint ──────────────────────────────────────────────────────────

def test_preview_invalid_voice_returns_400():
    """Preview with unknown voice should return 400."""
    response = client.post("/preview", json={
        "text":  "Hello world",
        "voice": "xx-XX-FakeVoiceNeural",
        "speed": 1.0
    })
    assert response.status_code == 400


def test_preview_empty_text_returns_422():
    """Preview with empty text should fail validation (422 = Unprocessable Entity)."""
    response = client.post("/preview", json={
        "text":  "",
        "voice": "en-US-AriaNeural",
        "speed": 1.0
    })
    assert response.status_code == 422


def test_preview_speed_out_of_range_returns_422():
    """Preview with speed > 2.0 should fail validation."""
    response = client.post("/preview", json={
        "text":  "Hello",
        "voice": "en-US-AriaNeural",
        "speed": 5.0   # too fast — max is 2.0
    })
    assert response.status_code == 422


# ── Convert endpoint ──────────────────────────────────────────────────────────

def test_convert_invalid_voice_returns_400():
    """Convert with unknown voice should return 400."""
    response = client.post("/convert", json={
        "text":  "Hello world",
        "voice": "xx-XX-FakeVoiceNeural",
        "speed": 1.0,
        "title": "Test"
    })
    assert response.status_code == 400


def test_convert_empty_text_returns_422():
    """Convert with empty text should fail validation."""
    response = client.post("/convert", json={
        "text":  "",
        "voice": "en-US-AriaNeural",
        "speed": 1.0,
        "title": "Test"
    })
    assert response.status_code == 422


def test_convert_valid_request_returns_job_id():
    """Valid convert request should return a job_id immediately."""
    response = client.post("/convert", json={
        "text":  "Once upon a time there was a brave little fox.",
        "voice": "en-US-AriaNeural",
        "speed": 1.0,
        "title": "Test Story"
    })
    assert response.status_code == 200
    data = response.json()
    assert "job_id"  in data
    assert "status"  in data
    assert "message" in data
    assert len(data["job_id"]) > 0
    assert data["status"] in ("running", "done")


# ── Status endpoint ───────────────────────────────────────────────────────────

def test_status_unknown_job_returns_404():
    """Checking status of non-existent job should return 404."""
    response = client.get("/status/nonexistent-job-id-12345")
    assert response.status_code == 404


def test_status_known_job_returns_data():
    """After submitting a job, status endpoint should return its data."""
    # First create a job
    convert_response = client.post("/convert", json={
        "text":  "The dragon soared above the mountains.",
        "voice": "en-US-AriaNeural",
        "speed": 1.0,
        "title": "Dragon Story"
    })
    job_id = convert_response.json()["job_id"]

    # Then check its status
    status_response = client.get(f"/status/{job_id}")
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["job_id"] == job_id
    assert data["status"] in ("running", "done", "failed")


# ── Jobs list ─────────────────────────────────────────────────────────────────

def test_list_all_jobs_returns_summary():
    """GET /jobs should return a summary of all jobs."""
    response = client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "total"   in data
    assert "running" in data
    assert "done"    in data
    assert "failed"  in data
    assert "jobs"    in data


# ── Convert PDF endpoint ──────────────────────────────────────────────────────

def test_convert_pdf_wrong_file_type_returns_400():
    """Uploading a non-PDF/TXT file should return 400."""
    response = client.post(
        "/convert-pdf",
        files={"file": ("image.jpg", b"fake image content", "image/jpeg")},
        data={"voice": "en-US-AriaNeural"}
    )
    assert response.status_code == 400


def test_convert_pdf_txt_file_accepted():
    """Uploading a TXT file should be accepted and return a job_id."""
    txt_content = b"Once upon a time there was a brave little fox named Felix."
    response = client.post(
        "/convert-pdf",
        files={"file": ("story.txt", txt_content, "text/plain")},
        data={"voice": "en-US-AriaNeural", "speed": "1.0"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data


def test_convert_pdf_invalid_voice_returns_400():
    """Uploading with invalid voice should return 400."""
    response = client.post(
        "/convert-pdf",
        files={"file": ("story.txt", b"Some text", "text/plain")},
        data={"voice": "xx-FAKE-VoiceNeural"}
    )
    assert response.status_code == 400
