import base64
import tempfile
import soundfile as sf
import runpod

tts = None

def get_tts():
    global tts
    if tts is None:
        from chatterbox.tts import ChatterboxTTS
        tts = ChatterboxTTS.from_pretrained("resemble-ai/chatterbox")
    return tts

def handler(event):
    text = event.get("input", {}).get("text")

    if not text:
        return {"error": "No text provided"}

    tts = get_tts()
    audio = tts.synthesize(text)

    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        sf.write(f.name, audio["audio"], audio["sample_rate"])
        f.seek(0)
        audio_bytes = f.read()

    return {
        "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
        "sample_rate": audio["sample_rate"]
    }

runpod.serverless.start({"handler": handler})
