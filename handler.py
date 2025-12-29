"""
RunPod Handler for Chatterbox TTS with Voice Cloning Support

This handler accepts text and an optional reference_audio_base64 parameter for voice cloning.
It decodes the base64 audio, saves it to a temp file, and passes it to Chatterbox.

Includes comprehensive error handling for production use.
"""

import runpod
import torch
import base64
import tempfile
import os
from pathlib import Path
import logging
import librosa

# Import Chatterbox
from chatterbox.tts_turbo import ChatterboxTurboTTS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MIN_VOICE_SAMPLE_DURATION = 5.0  # seconds - required by ChatterboxTurboTTS
MAX_TEXT_LENGTH = 500  # characters - prevent extremely long texts
MIN_TEXT_LENGTH = 1  # characters

# Initialize model (load once on container start)
logger.info("Loading Chatterbox model...")
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Using device: {device}")

try:
    model = ChatterboxTurboTTS.from_pretrained(device=device)
    SAMPLE_RATE = model.sr  # Get sample rate from model (24000)
    logger.info(f"Chatterbox model loaded successfully (sample rate: {SAMPLE_RATE} Hz)")
except Exception as e:
    logger.error(f"FATAL: Failed to load Chatterbox model: {e}", exc_info=True)
    raise


def validate_audio_file(audio_path: str) -> tuple[bool, str]:
    """
    Validate that the audio file is valid and meets requirements

    Args:
        audio_path: Path to audio file

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Try to load the audio file
        audio, sr = librosa.load(audio_path, sr=None)

        # Check duration
        duration = len(audio) / sr
        if duration < MIN_VOICE_SAMPLE_DURATION:
            return False, f"Voice sample too short: {duration:.1f}s (minimum {MIN_VOICE_SAMPLE_DURATION}s required)"

        # Check if audio is silent or corrupted
        if len(audio) == 0:
            return False, "Voice sample is empty"

        logger.info(f"Voice sample validated: {duration:.1f}s at {sr} Hz")
        return True, ""

    except Exception as e:
        return False, f"Invalid audio file: {str(e)}"


def decode_base64_audio(base64_string: str, output_path: str):
    """
    Decode base64 audio string and save to file

    Args:
        base64_string: Base64 encoded audio data
        output_path: Path to save the decoded audio file

    Raises:
        ValueError: If base64 is invalid or empty
    """
    if not base64_string:
        raise ValueError("Empty base64 audio string")

    try:
        # Decode base64 to bytes
        audio_bytes = base64.b64decode(base64_string)

        if len(audio_bytes) == 0:
            raise ValueError("Decoded audio is empty")

        # Write to file
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)

        logger.info(f"Decoded audio saved to {output_path} ({len(audio_bytes)} bytes)")

    except base64.binascii.Error as e:
        raise ValueError(f"Invalid base64 encoding: {e}")
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

        if len(audio_bytes) == 0:
            raise ValueError("Generated audio file is empty")

        base64_string = base64.b64encode(audio_bytes).decode('utf-8')
        logger.info(f"Encoded audio to base64 ({len(base64_string)} chars)")
        return base64_string

    except Exception as e:
        logger.error(f"Failed to encode audio to base64: {e}")
        raise


def handler(job):
    """
    RunPod handler function with comprehensive error handling

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

    Or on error:
    {
        "error": "Error message"
    }
    """
    # Track temp files for cleanup
    temp_files = []

    try:
        job_input = job["input"]

        # Extract parameters
        text = job_input.get("text") or job_input.get("prompt")
        reference_audio_base64 = job_input.get("reference_audio_base64")

        # Validate text
        if not text:
            return {"error": "No text provided"}

        text = text.strip()

        if len(text) < MIN_TEXT_LENGTH:
            return {"error": f"Text too short (minimum {MIN_TEXT_LENGTH} characters)"}

        if len(text) > MAX_TEXT_LENGTH:
            return {"error": f"Text too long (maximum {MAX_TEXT_LENGTH} characters)"}

        logger.info(f"Processing TTS request: {len(text)} chars")
        logger.info(f"Voice cloning: {'ENABLED' if reference_audio_base64 else 'DISABLED'}")

        # Handle reference audio if provided
        audio_prompt_path = None

        if reference_audio_base64:
            try:
                # Create temporary file for reference audio
                temp_ref_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                audio_prompt_path = temp_ref_audio.name
                temp_files.append(audio_prompt_path)
                temp_ref_audio.close()

                logger.info(f"Decoding reference audio ({len(reference_audio_base64)} chars base64)")
                decode_base64_audio(reference_audio_base64, audio_prompt_path)
                logger.info(f"Reference audio saved to: {audio_prompt_path}")

                # Validate the audio file
                is_valid, error_msg = validate_audio_file(audio_prompt_path)
                if not is_valid:
                    return {"error": error_msg}

            except ValueError as e:
                return {"error": f"Invalid voice sample: {str(e)}"}
            except Exception as e:
                logger.error(f"Failed to process voice sample: {e}", exc_info=True)
                return {"error": f"Voice sample processing failed: {str(e)}"}

        # Generate audio with Chatterbox
        logger.info("Generating audio with Chatterbox...")

        try:
            # Generation parameters to aggressively reduce repetition
            gen_params = {
                "repetition_penalty": 2.0,  # Maximum value (default 1.2) to prevent phrase repetition
                "temperature": 0.5,         # Lower than default 0.8 for more consistent output
                "cfg_weight": 0.8,          # Higher than default 0.5 for better pacing/guidance
                "min_p": 0.15,              # Higher than default 0.05 for tighter sampling
                "exaggeration": 0.3,        # Lower than default 0.5 for less expressive, more consistent output
            }

            if audio_prompt_path:
                # Voice cloning mode
                wav = model.generate(text, audio_prompt_path=audio_prompt_path, **gen_params)
            else:
                # Default voice mode
                wav = model.generate(text, **gen_params)

        except torch.cuda.OutOfMemoryError:
            logger.error("GPU out of memory during generation")
            # Clear GPU cache and return error
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            return {"error": "GPU out of memory. Please try with shorter text or wait and retry."}
        except AssertionError as e:
            logger.error(f"Model assertion failed: {e}")
            return {"error": f"Generation failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Generation failed: {e}", exc_info=True)
            return {"error": f"Audio generation failed: {str(e)}"}

        logger.info("Audio generation completed")

        # Convert torch tensor to numpy array for soundfile
        # ChatterboxTurboTTS returns shape (1, samples), need to squeeze
        try:
            if torch.is_tensor(wav):
                wav_numpy = wav.squeeze().cpu().numpy()
            else:
                wav_numpy = wav

            # Validate output
            if wav_numpy.size == 0:
                return {"error": "Generated audio is empty"}

        except Exception as e:
            logger.error(f"Failed to convert audio tensor: {e}")
            return {"error": f"Audio conversion failed: {str(e)}"}

        # Save generated audio to temp file
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        output_path = temp_output.name
        temp_files.append(output_path)
        temp_output.close()

        # Write WAV file
        try:
            import soundfile as sf
            sf.write(output_path, wav_numpy, SAMPLE_RATE)
            logger.info(f"Output audio saved to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to write WAV file: {e}")
            return {"error": f"Failed to save audio: {str(e)}"}

        # Encode output to base64
        try:
            audio_base64 = encode_audio_to_base64(output_path)
        except Exception as e:
            logger.error(f"Failed to encode output: {e}")
            return {"error": f"Failed to encode audio: {str(e)}"}

        # Return result
        return {
            "audio_base64": audio_base64,
            "sample_rate": SAMPLE_RATE
        }

    except Exception as e:
        logger.error(f"Unexpected handler error: {e}", exc_info=True)
        return {"error": f"Unexpected error: {str(e)}"}

    finally:
        # Always cleanup temp files
        for temp_file in temp_files:
            try:
                if temp_file and os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {temp_file}: {e}")


if __name__ == "__main__":
    logger.info("Starting RunPod serverless handler for Chatterbox TTS")
    runpod.serverless.start({"handler": handler})
