# ElevenLabs Integration — NarraAI

## What it adds

A new **🎧 ElevenLabs** tab gives access to ElevenLabs' premium AI voices alongside the existing Edge-TTS engine. Key features:

- Browse all ElevenLabs voices (pre-made + your clones) live from the API
- Clone your own voice by uploading audio samples
- `eleven_multilingual_v2` — 29+ languages from one model, auto-detected
- Stability and Similarity Boost sliders for fine-tuned voice control
- Preview before full conversion
- Load PDF or TXT directly in the tab
- Outputs the same `VoiceName__Title__01_Chapter.mp3` format as Edge-TTS

---

## Setup

### 1. Install the SDK

```bash
pip install elevenlabs
```

A `requests` fallback is also supported if the SDK cannot be installed.

### 2. Get your API key

1. Go to [elevenlabs.io](https://elevenlabs.io) and sign in.
2. Click your avatar → **Profile** → copy the **API Key**.

### 3. Run NarraAI

```bash
python main.py
```

Open the **🎧 ElevenLabs** tab, paste your API key, and click **Load Voices**.

---

## Voice Cloning

Cloning requires an **ElevenLabs Creator plan** or above.

1. Click **🎤 Clone a Voice** in the ElevenLabs tab.
2. Enter a name and upload 1–5 clean MP3/WAV recordings (minimum ~1 minute total).
3. Click **Clone Voice**. The new voice appears at the top of the voice list immediately.

---

## Models

| Model | Best for |
|---|---|
| `eleven_multilingual_v2` | Any language — recommended default |
| `eleven_monolingual_v1` | English only, very natural |
| `eleven_turbo_v2` | Low latency |
| `eleven_turbo_v2_5` | Faster + multilingual |

---

## Voice Settings

| Slider | Effect |
|---|---|
| **Stability** (0–1) | Higher = more consistent, lower = more expressive |
| **Similarity Boost** (0–1) | Higher = closer to original voice, lower = more creative |

Good starting point: Stability `0.5`, Similarity `0.75`.

---

## Files added / changed

| File | Change |
|---|---|
| `core/elevenlabs_tts.py` | **New** — ElevenLabsConverter class + API helpers |
| `gui/app.py` | **Modified** — added ElevenLabs tab + callbacks |
| `requirements.txt` | **Modified** — `elevenlabs` added as optional dependency |
| `docs/ELEVENLABS.md` | **New** — this file |
