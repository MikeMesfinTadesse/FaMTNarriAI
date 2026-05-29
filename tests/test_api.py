"""
tests/test_api.py — FaMTNarriAI API Tests (Phase 2)
═══════════════════════════════════════════════════════════════

Tests cover all Phase 2 endpoints:
  - Health & stats
  - Voices & languages
  - Preview (validation only — audio mocked)
  - Convert text (validation + job lifecycle)
  - Convert PDF (file upload + validation)
  - Job status & download

HOW THE MOCK WORKS:
    edge_tts makes real network calls to Microsoft servers.
    In tests we don't want network calls — tests must be:
      - Fast (< 1 second each)
      - Reliable (no network = no test failure)
      - Deterministic (same result every run)
    So we mock edge_tts before importing the app.
    The mock replaces edge_tts.Communicate with a fake that
    creates a tiny real MP3 file instead of calling Microsoft.

HOW TO RUN:
    pip install pytest httpx fastapi python-multipart
    pytest tests/test_api.py -v
═══════════════════════════════════════════════════════════════
"""

import sys
import io
import time
import struct
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Mock edge_tts before importing the app ────────────────────────────────────
# A minimal valid MP3 file (ID3 header + one silent MPEG frame)
_SILENT_MP3 = (
    b"ID3\x03\x00\x00\x00\x00\x00\x00"   # ID3v2.3 header (10 bytes)
    + b"\xff\xfb\x90\x00"                  # MPEG1 Layer3 frame header
    + b"\x00" * 413                         # silent frame data
)

class _FakeCommunicate:
    """Fake edge_tts.Communicate — writes silent MP3, supports stream() for validation."""
    def __init__(self, text, voice, **kwargs):
        self.text  = text
        self.voice = voice

    async def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(_SILENT_MP3)

    async def stream(self):
        """Yield one fake audio chunk so validate_voice_async() returns (True, '')."""
        yield {"type": "audio", "data": _SILENT_MP3}

_mock_edge = unittest.mock.MagicMock()
_mock_edge.Communicate = _FakeCommunicate
sys.modules["edge_tts"] = _mock_edge

# ── Now import the app ────────────────────────────────────────────────────────
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)
API = "/api/v2"


# ════════════════════════════════════════════════════════════════════════════
# HEALTH & SYSTEM
# ════════════════════════════════════════════════════════════════════════════

def test_root_redirects_to_docs():
    """GET / should redirect to /docs."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (301, 302, 307, 308)


def test_health_check_returns_ok():
    """GET /api/v2/health should return status ok."""
    r = client.get(f"{API}/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"]  == "ok"
    assert d["version"] == "2.0.0"
    assert "uptime"         in d
    assert "voices_loaded"  in d
    assert d["voices_loaded"] > 0


def test_stats_returns_summary():
    """GET /api/v2/stats should return job statistics."""
    r = client.get(f"{API}/stats")
    assert r.status_code == 200
    d = r.json()
    assert "total_jobs"    in d
    assert "jobs_running"  in d
    assert "jobs_done"     in d
    assert "jobs_failed"   in d


# ════════════════════════════════════════════════════════════════════════════
# VOICES & LANGUAGES
# ════════════════════════════════════════════════════════════════════════════

def test_list_voices_returns_list():
    r = client.get(f"{API}/voices")
    assert r.status_code == 200
    voices = r.json()
    assert isinstance(voices, list)
    assert len(voices) > 0


def test_list_voices_have_id_and_label():
    r = client.get(f"{API}/voices")
    for voice in r.json()[:5]:
        assert "id"    in voice
        assert "label" in voice
        assert len(voice["id"]) > 0


def test_list_voices_includes_aria():
    r      = client.get(f"{API}/voices")
    ids    = [v["id"] for v in r.json()]
    assert "en-US-AriaNeural" in ids


def test_list_voices_includes_amharic():
    r   = client.get(f"{API}/voices")
    ids = [v["id"] for v in r.json()]
    assert "am-ET-MekdesNeural" in ids


def test_list_voices_includes_swahili():
    r   = client.get(f"{API}/voices")
    ids = [v["id"] for v in r.json()]
    assert "sw-KE-ZuriNeural" in ids


def test_voices_by_language_english():
    r = client.get(f"{API}/voices/en")
    assert r.status_code == 200
    for v in r.json():
        assert v["id"].startswith("en-")


def test_voices_by_language_arabic():
    r = client.get(f"{API}/voices/ar")
    assert r.status_code == 200
    for v in r.json():
        assert v["id"].startswith("ar-")


def test_voices_by_language_amharic():
    r = client.get(f"{API}/voices/am")
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_voices_by_language_swahili():
    r = client.get(f"{API}/voices/sw")
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_voices_unknown_language_returns_404():
    r = client.get(f"{API}/voices/xx")
    assert r.status_code == 404
    assert "error" in r.json()["detail"]


def test_languages_structure():
    r = client.get(f"{API}/languages")
    assert r.status_code == 200
    d = r.json()
    assert "total_languages" in d
    assert "total_voices"    in d
    assert "languages"       in d
    assert d["total_languages"] > 0
    assert d["total_voices"]    > 0


# ════════════════════════════════════════════════════════════════════════════
# PREVIEW
# ════════════════════════════════════════════════════════════════════════════

def test_preview_invalid_voice_returns_400():
    r = client.post(f"{API}/preview", json={
        "text": "Hello world", "voice": "xx-XX-FakeVoice", "speed": 1.0
    })
    assert r.status_code == 400
    assert "error" in r.json()["detail"]


def test_preview_empty_text_returns_422():
    r = client.post(f"{API}/preview", json={
        "text": "", "voice": "en-US-AriaNeural", "speed": 1.0
    })
    assert r.status_code == 422


def test_preview_speed_too_high_returns_422():
    r = client.post(f"{API}/preview", json={
        "text": "Hello", "voice": "en-US-AriaNeural", "speed": 9.9
    })
    assert r.status_code == 422


def test_preview_speed_too_low_returns_422():
    r = client.post(f"{API}/preview", json={
        "text": "Hello", "voice": "en-US-AriaNeural", "speed": 0.1
    })
    assert r.status_code == 422


def test_preview_valid_request_returns_audio():
    """Valid preview should return audio/mpeg."""
    r = client.post(f"{API}/preview", json={
        "text": "Hello! Testing this voice now.", "voice": "en-US-AriaNeural", "speed": 1.0
    })
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"


# ════════════════════════════════════════════════════════════════════════════
# CONVERT TEXT
# ════════════════════════════════════════════════════════════════════════════

def test_convert_invalid_voice_returns_400():
    r = client.post(f"{API}/convert", json={
        "text": "Hello", "voice": "xx-FAKE-VoiceNeural", "speed": 1.0, "title": "Test"
    })
    assert r.status_code == 400
    d = r.json()
    assert "error" in d["detail"]


def test_convert_empty_text_returns_422():
    r = client.post(f"{API}/convert", json={
        "text": "", "voice": "en-US-AriaNeural", "speed": 1.0, "title": "Test"
    })
    assert r.status_code == 422


def test_convert_returns_job_id_immediately():
    """Valid request should return a job_id without waiting."""
    r = client.post(f"{API}/convert", json={
        "text": "Once upon a time there was a brave little fox.",
        "voice": "en-US-AriaNeural", "speed": 1.0, "title": "Test Story"
    })
    assert r.status_code == 200
    d = r.json()
    assert "job_id"   in d
    assert "status"   in d
    assert "poll_url" in d
    assert len(d["job_id"]) > 0
    assert d["status"] in ("running", "done")


def test_convert_response_has_poll_url():
    r = client.post(f"{API}/convert", json={
        "text": "The dragon soared.", "voice": "en-US-AriaNeural",
        "speed": 1.0, "title": "Dragon"
    })
    d = r.json()
    assert d["poll_url"].startswith("/api/v2/jobs/")


def test_convert_arabic_voice():
    """Arabic voice should be accepted."""
    r = client.post(f"{API}/convert", json={
        "text": "مرحبا بالعالم", "voice": "ar-SA-ZariyahNeural",
        "speed": 1.0, "title": "Arabic Test"
    })
    assert r.status_code == 200
    assert "job_id" in r.json()


def test_convert_amharic_voice():
    """Amharic voice should be accepted."""
    r = client.post(f"{API}/convert", json={
        "text": "ሰላም ዓለም", "voice": "am-ET-MekdesNeural",
        "speed": 1.0, "title": "Amharic Test"
    })
    assert r.status_code == 200
    assert "job_id" in r.json()


def test_convert_with_emotion_tags():
    """Emotion tags in text should be accepted."""
    r = client.post(f"{API}/convert", json={
        "text": "(gentle) Once upon a time. (pause) (excited) She found treasure!",
        "voice": "en-US-AriaNeural", "speed": 1.0, "title": "Emotional Story"
    })
    assert r.status_code == 200


# ════════════════════════════════════════════════════════════════════════════
# JOB STATUS
# ════════════════════════════════════════════════════════════════════════════

def test_status_unknown_job_returns_404():
    r = client.get(f"{API}/jobs/nonexistent-id-99999")
    assert r.status_code == 404
    assert "error" in r.json()["detail"]


def test_status_known_job_returns_data():
    """After submitting, status endpoint should return job data."""
    create = client.post(f"{API}/convert", json={
        "text": "The mountain was tall.", "voice": "en-US-AriaNeural",
        "speed": 1.0, "title": "Mountain"
    })
    job_id = create.json()["job_id"]

    r = client.get(f"{API}/jobs/{job_id}")
    assert r.status_code == 200
    d = r.json()
    assert d["job_id"] == job_id
    assert d["status"] in ("running", "done", "failed")
    assert "created_at" in d


def test_status_done_job_has_download_urls():
    """When job is done, files[] should contain download URLs."""
    create = client.post(f"{API}/convert", json={
        "text": "Short story.", "voice": "en-US-AriaNeural",
        "speed": 1.0, "title": "Short"
    })
    job_id = create.json()["job_id"]

    # Wait for background task to complete
    for _ in range(20):
        r = client.get(f"{API}/jobs/{job_id}")
        if r.json()["status"] in ("done", "failed"):
            break
        time.sleep(0.1)

    r = client.get(f"{API}/jobs/{job_id}")
    d = r.json()
    if d["status"] == "done":
        assert len(d["files"]) > 0
        for url in d["files"]:
            assert "/download/" in url


def test_list_all_jobs():
    """GET /api/v2/jobs should return job summary."""
    r = client.get(f"{API}/jobs")
    assert r.status_code == 200
    d = r.json()
    assert "total"   in d
    assert "running" in d
    assert "done"    in d
    assert "failed"  in d
    assert "jobs"    in d


# ════════════════════════════════════════════════════════════════════════════
# CONVERT PDF
# ════════════════════════════════════════════════════════════════════════════

def test_convert_pdf_wrong_type_returns_400():
    r = client.post(
        f"{API}/convert-pdf",
        files={"file": ("image.jpg", b"fake image", "image/jpeg")},
        data={"voice": "en-US-AriaNeural"},
    )
    assert r.status_code == 400
    assert "error" in r.json()["detail"]


def test_convert_pdf_invalid_voice_returns_400():
    r = client.post(
        f"{API}/convert-pdf",
        files={"file": ("story.txt", b"Some text here.", "text/plain")},
        data={"voice": "xx-FAKE-VoiceNeural"},
    )
    assert r.status_code == 400
    assert "error" in r.json()["detail"]


def test_convert_pdf_txt_accepted():
    """TXT file upload should be accepted and return job_id."""
    r = client.post(
        f"{API}/convert-pdf",
        files={"file": ("story.txt", b"Once upon a time there was a brave little fox named Felix.", "text/plain")},
        data={"voice": "en-US-AriaNeural", "speed": "1.0"},
    )
    assert r.status_code == 200
    d = r.json()
    assert "job_id"   in d
    assert "poll_url" in d


def test_convert_pdf_speed_validation():
    """Speed out of range should return 422."""
    r = client.post(
        f"{API}/convert-pdf",
        files={"file": ("story.txt", b"Hello world.", "text/plain")},
        data={"voice": "en-US-AriaNeural", "speed": "9.9"},
    )
    assert r.status_code == 422


# ════════════════════════════════════════════════════════════════════════════
# RATE LIMITING (auth disabled in test — rate limiter still active)
# ════════════════════════════════════════════════════════════════════════════

def test_rate_limit_not_triggered_on_normal_use():
    """Normal usage (< 10 requests) should not trigger rate limiting."""
    for _ in range(5):
        r = client.get(f"{API}/health")
        assert r.status_code == 200


# ════════════════════════════════════════════════════════════════════════════
# ELEVENLABS ENDPOINTS (Phase 2 Addition)
# ════════════════════════════════════════════════════════════════════════════
# These tests run WITHOUT an ElevenLabs API key.
# They verify:
#   - 503 is returned when key is missing (correct behaviour)
#   - Validation (bad input → 422) still works even without key
# When ELEVENLABS_API_KEY is set, the 503 tests would need to be skipped.

def test_el_voices_without_key_returns_503():
    """No ELEVENLABS_API_KEY → 503 with setup instructions."""
    import os
    os.environ.pop("ELEVENLABS_API_KEY", None)
    r = client.get(f"{API}/elevenlabs/voices")
    assert r.status_code == 503
    d = r.json()["detail"]
    assert "error"  in d
    assert "hint"   in d


def test_el_convert_without_key_returns_503():
    """No ELEVENLABS_API_KEY → 503."""
    import os
    os.environ.pop("ELEVENLABS_API_KEY", None)
    r = client.post(f"{API}/elevenlabs/convert", json={
        "text":     "Hello world",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "title":    "Test",
    })
    assert r.status_code == 503


def test_el_preview_without_key_returns_503():
    """No ELEVENLABS_API_KEY → 503."""
    import os
    os.environ.pop("ELEVENLABS_API_KEY", None)
    r = client.post(f"{API}/elevenlabs/preview", json={
        "text":     "Hello",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "title":    "Test",
    })
    assert r.status_code == 503


def test_el_convert_empty_text_returns_422():
    """Empty text → 422 validation error (before key is even checked)."""
    r = client.post(f"{API}/elevenlabs/convert", json={
        "text":     "",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "title":    "Test",
    })
    assert r.status_code == 422


def test_el_convert_stability_out_of_range_returns_422():
    """Stability > 1.0 → 422."""
    r = client.post(f"{API}/elevenlabs/convert", json={
        "text":      "Hello",
        "voice_id":  "21m00Tcm4TlvDq8ikWAM",
        "stability": 1.5,
        "title":     "Test",
    })
    assert r.status_code == 422
