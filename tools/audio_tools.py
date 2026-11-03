"""
Multi-speaker text-to-speech audio synthesis tool for VoiceMock.
Synthesizes post-interview debrief conversations between Lead Interviewer ('Kore')
and Bar Raiser ('Puck') into standard 24 kHz 16-bit mono PCM WAV audio using
the Gemini Preview TTS model (with fallback synthetic audio generator).
"""

from __future__ import annotations
import math
import os
import pathlib
import struct
import sys
import wave
from typing import Any, Dict, Optional
from dotenv import load_dotenv, find_dotenv

PROJECT_DIR = pathlib.Path(__file__).parent.parent.resolve()
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Ensure environment variables are loaded
load_dotenv(find_dotenv())


def write_wave_file(
    filename: str,
    pcm_data: bytes,
    channels: int = 1,
    sample_rate: int = 24000,
    sample_width: int = 2
) -> str:
    """Writes raw PCM audio data into a standard WAV audio container."""
    path = pathlib.Path(filename).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return str(path)


def generate_synthetic_pcm(duration_seconds: float = 2.0, sample_rate: int = 24000) -> bytes:
    """
    Generates deterministic synthetic audio buffer (decaying harmonic chime)
    for offline testing and fallback when the live Gemini API is unreachable.
    """
    num_samples = int(duration_seconds * sample_rate)
    frames = bytearray()
    for i in range(num_samples):
        t = float(i) / sample_rate
        decay = math.exp(-2.5 * t / max(0.1, duration_seconds))
        # 523.25 Hz (C5) + 659.25 Hz (E5) pleasant chime
        sample = int(
            32767.0 * 0.25 * (
                math.sin(2.0 * math.pi * 523.25 * t) +
                0.5 * math.sin(2.0 * math.pi * 659.25 * t)
            ) * decay
        )
        frames.extend(struct.pack("<h", max(-32768, min(32767, sample))))
    return bytes(frames)


def normalize_debrief_script(script_text: str) -> str:
    """
    Normalizes speaker labels in script text so that they strictly match
    'Interviewer:' and 'Bar Raiser:' for Gemini MultiSpeakerVoiceConfig.
    """
    lines = []
    for line in script_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("interviewer") or lower.startswith("host"):
            _, _, text = stripped.partition(":")
            lines.append(f"Interviewer: {text.strip()}")
        elif lower.startswith("bar raiser") or lower.startswith("bar_raiser") or lower.startswith("hiring manager") or lower.startswith("manager"):
            _, _, text = stripped.partition(":")
            lines.append(f"Bar Raiser: {text.strip()}")
        else:
            lines.append(stripped)
    return "\n\n".join(lines)


def synthesize_debrief_audio(
    dialogue_script: str,
    output_filename: str = "interview_debrief.wav",
    force_mock: bool = False,
    tool_context: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Synthesizes a 2-speaker debrief audio WAV file between Interviewer (Kore) and Bar Raiser (Puck).

    Args:
        dialogue_script: Dialogue text alternating between 'Interviewer:' and 'Bar Raiser:'.
        output_filename: Output destination for the WAV audio file.
        force_mock: If True, skips live Gemini API calls and generates synthetic audio.
        tool_context: Optional ADK tool context.

    Returns:
        Dictionary with generation status, audio path, byte size, and engine mode.
    """
    out_path = pathlib.Path(output_filename)
    if not out_path.is_absolute():
        out_path = PROJECT_DIR / out_path
    if not out_path.name.endswith(".wav"):
        out_path = out_path.with_suffix(".wav")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_script = normalize_debrief_script(dialogue_script)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    audio_bytes: Optional[bytes] = None
    engine_mode = "synthetic_fallback"

    if api_key and not force_mock:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            prompt = (
                "TTS the following professional post-interview debrief between Interviewer and Bar Raiser:\n\n"
                f"{normalized_script}"
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=[
                                types.SpeakerVoiceConfig(
                                    speaker="Interviewer",
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                                    )
                                ),
                                types.SpeakerVoiceConfig(
                                    speaker="Bar Raiser",
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                                    )
                                )
                            ]
                        )
                    )
                )
            )

            if (
                response.candidates
                and response.candidates[0].content
                and response.candidates[0].content.parts
                and hasattr(response.candidates[0].content.parts[0], "inline_data")
                and response.candidates[0].content.parts[0].inline_data
            ):
                audio_bytes = response.candidates[0].content.parts[0].inline_data.data
                engine_mode = "live_gemini_tts"
        except Exception as err:
            print(f"[Warning] Live Gemini TTS call encountered an error: {err}. Falling back to synthetic audio.")
            audio_bytes = None

    if not audio_bytes:
        # Generate 2.5s clean synthetic audio
        audio_bytes = generate_synthetic_pcm(duration_seconds=2.5, sample_rate=24000)
        engine_mode = "synthetic_mock" if force_mock else "synthetic_fallback"

    saved_path = write_wave_file(str(out_path), audio_bytes, channels=1, sample_rate=24000, sample_width=2)

    return {
        "status": "success",
        "audio_path": saved_path,
        "byte_size": len(audio_bytes),
        "engine_mode": engine_mode,
        "message": f"Successfully generated debrief audio ({engine_mode}) at {out_path.name}."
    }
