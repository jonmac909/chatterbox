import base64
import tempfile
import soundfile as sf
import runpod

from chatterbox.tts import ChatterboxTTS

# Lazy-load model to avoid cold-start crash
tts = None

def handler(event):
    global tts

    text = event.get("input", {}).get("text")
    if not text:
        return {"error": "No text provided"}

    if tts is None:
        tts = ChatterboxTTS()

    # Generate audio
    wav, sample_rate = tts.tts(text)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
        sf.write(f.name, wav, sample_rate)
        f.seek(0)
        audio_bytes = f.read()

    return {
        "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
        "sample_rate": sample_rate
    }

runpod.serverless.start({"handler": handler})
