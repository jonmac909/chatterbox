# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a **fork** of Resemble AI's Chatterbox TTS (https://github.com/resemble-ai/chatterbox) customized for RunPod serverless deployment with voice cloning support. The fork adds production-ready error handling and RunPod integration for the HistoryGen AI project.

**Upstream:** `resemble-ai/chatterbox` (open-source TTS models)
**This fork:** `jonmac909/chatterbox` (RunPod deployment with custom handler)

## Project Structure

```
chatterbox/
├── src/chatterbox/           # Core TTS package
│   ├── tts.py               # ChatterboxTTS (original 500M model)
│   ├── tts_turbo.py         # ChatterboxTurboTTS (350M, USED BY RUNPOD)
│   ├── mtl_tts.py           # Multilingual TTS (23+ languages)
│   ├── vc.py                # Voice conversion
│   └── models/              # Model architectures (T3, S3Gen, etc.)
├── handler.py               # RunPod serverless handler (CRITICAL)
├── Dockerfile.runpod        # RunPod deployment Dockerfile (CRITICAL)
├── requirements.txt         # Production dependencies
├── pyproject.toml           # Package metadata
└── example_*.py             # Usage examples (not used in production)
```

## Key Files for RunPod Deployment

### handler.py (CRITICAL)
The RunPod serverless handler that processes TTS jobs with voice cloning. This is the **entry point** for all production requests.

**Key responsibilities:**
- Accepts JSON input: `{ text, reference_audio_base64 }`
- Validates voice samples (≥5 seconds, valid audio format)
- Manages GPU memory (handles OOM gracefully)
- Uses `ChatterboxTurboTTS` (NOT the base `ChatterboxTTS`)
- Returns base64-encoded WAV audio at 24kHz

**Critical constraints:**
- Voice samples MUST be ≥5 seconds (assertion in `tts_turbo.py:221`)
- Text limited to 500 chars per chunk (prevents OOM)
- Always uses `model.sr` for sample rate (don't hardcode)
- Temp files MUST be cleaned up in `finally` block

### Dockerfile.runpod (CRITICAL)
Production Dockerfile for RunPod deployment.

**Key features:**
- Base: `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`
- Pre-downloads ChatterboxTurbo model during build (no runtime auth needed)
- Installs chatterbox package with `pip install -e .`
- Requires `HF_TOKEN` environment variable during build (READ token)

**Version constraints (DO NOT CHANGE):**
- PyTorch: **2.4.0** (must match base image)
- torchvision: **0.19.0** (compatible with PyTorch 2.4.0)
- torchaudio: **2.4.0**
- Mismatch causes: `operator torchvision::nms does not exist` error

## Installation

**Local development:**
```bash
pip install -e .
```

**RunPod deployment:**
```bash
docker build -f Dockerfile.runpod -t username/chatterbox-runpod:latest .
docker push username/chatterbox-runpod:latest
```

## Architecture

### TTS Models (3 variants)

**ChatterboxTurboTTS** (350M params, English only) - **USED IN PRODUCTION**
- Location: `src/chatterbox/tts_turbo.py`
- Features: Paralinguistic tags `[laugh]`, `[chuckle]`, etc.
- Fastest model, lowest VRAM
- Sample rate: 24000 Hz
- Requires 5+ second voice sample for cloning

**ChatterboxTTS** (500M params, English)
- Location: `src/chatterbox/tts.py`
- Features: CFG & exaggeration tuning
- More control, higher quality, slower

**ChatterboxMultilingualTTS** (500M params, 23+ languages)
- Location: `src/chatterbox/mtl_tts.py`
- Supports: ar, da, de, el, en, es, fi, fr, he, hi, it, ja, ko, ms, nl, no, pl, pt, ru, sv, sw, tr, zh

### Model Loading

All models use `.from_pretrained(device="cuda")` which:
1. Downloads from HuggingFace (`ResembleAI/chatterbox-turbo`)
2. Caches to `~/.cache/huggingface/hub/`
3. Loads model weights into GPU memory

**For RunPod:** Model is pre-downloaded during Docker build to avoid runtime auth.

### Voice Cloning Flow

1. **Input:** Base64-encoded audio (WAV/MP3)
2. **Decode:** Convert base64 → temp WAV file
3. **Validate:** Check duration ≥5s with librosa
4. **Prepare conditionals:** Extract voice embeddings
5. **Generate:** TTS with voice cloning
6. **Output:** Base64-encoded WAV at 24kHz

## Common Pitfalls

### 1. Wrong Class Import (CRITICAL)
```python
# ❌ WRONG - doesn't exist
from chatterbox import ChatterboxTurbo

# ✅ CORRECT - used in handler.py
from chatterbox.tts_turbo import ChatterboxTurboTTS
```

The `__init__.py` only exports `ChatterboxTTS`, `ChatterboxVC`, and `ChatterboxMultilingualTTS`. `ChatterboxTurboTTS` must be imported directly.

### 2. Voice Sample Duration
```python
# Will crash with AssertionError if sample < 5 seconds
assert len(s3gen_ref_wav) / _sr > 5.0, "Audio prompt must be longer than 5 seconds!"
```
Always validate duration BEFORE passing to model.

### 3. PyTorch Tensor Output
```python
# ChatterboxTurboTTS.generate() returns torch.Tensor (1, samples)
wav = model.generate(text, audio_prompt_path=path)

# ❌ WRONG - can't write tensor directly
soundfile.write(path, wav, 24000)

# ✅ CORRECT - convert to numpy first
wav_numpy = wav.squeeze().cpu().numpy()
soundfile.write(path, wav_numpy, 24000)
```

### 4. GPU Out of Memory
Always wrap generation in try/except:
```python
try:
    wav = model.generate(text, audio_prompt_path=path)
except torch.cuda.OutOfMemoryError:
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return {"error": "GPU out of memory"}
```

### 5. Hardcoded Sample Rate
```python
# ❌ WRONG - might not match model
soundfile.write(path, wav, 24000)

# ✅ CORRECT - use model's sample rate
soundfile.write(path, wav, model.sr)
```

## RunPod Deployment Workflow

1. **Make changes to handler.py or Dockerfile.runpod**
2. **Commit and push to GitHub:** `git push origin master`
3. **RunPod auto-rebuilds** (if GitHub integration enabled)
4. **Monitor build:** RunPod Dashboard → Endpoint → Build Logs
5. **Check workers:** Should show "Running" status
6. **Test:** Send TTS job via RunPod API

**Build time:** 5-10 minutes (downloads model from HuggingFace)

## Environment Variables (RunPod)

**Build-time (Dockerfile):**
- `HF_TOKEN`: HuggingFace READ token for model download

**Runtime (handler.py):**
- None required (model pre-loaded in image)

## Error Handling Patterns

The handler implements production-grade error handling:

```python
def handler(job):
    temp_files = []  # Track for cleanup
    try:
        # Validate inputs
        if not text:
            return {"error": "No text provided"}

        # Process with error handling
        try:
            wav = model.generate(text, audio_prompt_path=path)
        except torch.cuda.OutOfMemoryError:
            # GPU-specific handling
            torch.cuda.empty_cache()
            return {"error": "GPU OOM"}
        except AssertionError as e:
            # Model requirement violations
            return {"error": f"Generation failed: {e}"}

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        # Always cleanup temp files
        for f in temp_files:
            if os.path.exists(f):
                os.unlink(f)
```

## Integration with HistoryGen AI

This repository is used by the HistoryGen AI project for voice-cloned TTS:

**Supabase Edge Function:** `generate-audio/index.ts`
- Splits scripts into 180-char chunks (Chatterbox limitation)
- Sends chunks to RunPod endpoint sequentially
- Streams progress: 5% → 10% → 15-75% (per chunk) → 80% → 90% → 100%
- Concatenates WAV chunks and uploads to Supabase storage

**RunPod Endpoint ID:** `eitsgz3gndkh3s` (configurable)

## Built-in Features

**PerTh Watermarking:**
All generated audio includes imperceptible neural watermarks via `resemble-perth` package. Extract with:
```python
import perth
watermarker = perth.PerthImplicitWatermarker()
watermark = watermarker.get_watermark(audio, sample_rate=sr)
# Returns: 0.0 (no watermark) or 1.0 (watermarked)
```

## Debugging

**Worker crashes on startup:**
- Check RunPod worker logs (click on crashed worker)
- Common: ImportError → wrong class name
- Common: LocalTokenNotFoundError → HF_TOKEN not set during build

**Jobs fail with 500 error:**
- Check RunPod job logs (click on failed job)
- Common: Voice sample < 5 seconds
- Common: GPU OOM → reduce text length or increase GPU tier
- Common: Invalid audio format → validate with librosa

**Build fails:**
- Check PyTorch version matches base image (2.4.0)
- Check torchvision version (0.19.0)
- Check HF_TOKEN is set in build environment

## Testing

**Local testing:**
```python
from chatterbox.tts_turbo import ChatterboxTurboTTS
import torchaudio as ta

model = ChatterboxTurboTTS.from_pretrained(device="cuda")
text = "Hello, this is a test."
wav = model.generate(text, audio_prompt_path="sample.wav")
ta.save("output.wav", wav, model.sr)
```

**RunPod testing:**
Use RunPod API directly or test via HistoryGen AI frontend.
