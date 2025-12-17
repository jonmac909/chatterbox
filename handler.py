"""
RunPod Handler for Chatterbox TTS with Voice Cloning Support

This handler accepts text and an optional reference_audio_base64 parameter for voice cloning.
It decodes the base64 audio, saves it to a temp file, and passes it to Chatterbox.
"""

import runpod
import torch
import base64
import tempfile
import os
from pathlib import Path
import logging

# Import Chatterbox
from chatterbox import ChatterboxTurbo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize model (load once on container start)
logger.info("Loading Chatterbox model...")
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

model = ChatterboxTurbo(device=device)
logger.info("Chatterbox model loaded successfully")


def decode_base64_audio(base64_string: str, output_path: str):
    """
    Decode base64 audio string and save to file

    Args:
        base64_string: Base64 encoded audio data
        output_path: Path to save the decoded audio file
    """
    try:
        # Decode base64 to bytes
        audio_bytes = base64.b64decode(base64_string)

        # Write to file
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)

        logger.info(f"Decoded audio saved to {output_path} ({len(audio_bytes)} bytes)")
        return True
    except Exception as e:
        logger.error(f"Failed to decode base64 audio: {e}")
        raise


def encode_audio_to_base64(audio_path: str) -> str:
    """
    Read audio file and encode to base64

    Args:
        audio_path: Path to the audio file

    Returns:
        Base64 encoded string
    """
    try:
        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()

        base64_string = base64.b64encode(audio_bytes).decode('utf-8')
        logger.info(f"Encoded audio to base64 ({len(base64_string)} chars)")
        return base64_string
    except Exception as e:
        logger.error(f"Failed to encode audio to base64: {e}")
        raise


def handler(job):
    """
    RunPod handler function

    Expected input format:
    {
        "text": "Text to synthesize",
        "prompt": "Same as text (for compatibility)",
        "reference_audio_base64": "base64_encoded_audio_data" (optional)
    }

    Returns:
    {
        "audio_base64": "base64_encoded_wav_audio",
        "sample_rate": 24000
    }
    """
    try:
        job_input = job["input"]

        # Extract parameters
        text = job_input.get("text") or job_input.get("prompt")
        reference_audio_base64 = job_input.get("reference_audio_base64")

        if not text:
            return {"error": "No text provided"}

        logger.info(f"Processing TTS request: {len(text)} chars")
        logger.info(f"Voice cloning: {'ENABLED' if reference_audio_base64 else 'DISABLED'}")

        # Handle reference audio if provided
        audio_prompt_path = None
        temp_ref_audio = None

        if reference_audio_base64:
            # Create temporary file for reference audio
            temp_ref_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            audio_prompt_path = temp_ref_audio.name
            temp_ref_audio.close()

            logger.info(f"Decoding reference audio ({len(reference_audio_base64)} chars base64)")
            decode_base64_audio(reference_audio_base64, audio_prompt_path)
            logger.info(f"Reference audio saved to: {audio_prompt_path}")

        # Generate audio with Chatterbox
        logger.info("Generating audio with Chatterbox...")

        if audio_prompt_path:
            # Voice cloning mode
            wav = model.generate(text, audio_prompt_path=audio_prompt_path)
        else:
            # Default voice mode
            wav = model.generate(text)

        logger.info("Audio generation completed")

        # Save generated audio to temp file
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        output_path = temp_output.name
        temp_output.close()

        # Write WAV file
        import soundfile as sf
        sf.write(output_path, wav, 24000)
        logger.info(f"Output audio saved to: {output_path}")

        # Encode output to base64
        audio_base64 = encode_audio_to_base64(output_path)

        # Cleanup temp files
        try:
            os.unlink(output_path)
            if audio_prompt_path:
                os.unlink(audio_prompt_path)
            logger.info("Cleaned up temp files")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {e}")

        # Return result
        return {
            "audio_base64": audio_base64,
            "sample_rate": 24000
        }

    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        return {"error": str(e)}


if __name__ == "__main__":
    logger.info("Starting RunPod serverless handler for Chatterbox TTS")
    runpod.serverless.start({"handler": handler})
