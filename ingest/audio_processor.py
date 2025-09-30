"""Audio ingestion and normalisation utilities."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Tuple

from utils.logging import log_json

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1


def normalise_audio(input_path: Path, output_dir: Path) -> Tuple[Path, float]:
    """Normalise input audio into mono 16kHz WAV.

    The MVP implementation simply copies the file into the artifacts directory to
    keep the pipeline operable in environments without FFmpeg. The function
    returns the destination path and a dummy duration in seconds so the rest of
    the pipeline can proceed. Real deployments should replace this stub with a
    call to FFmpeg or a dedicated audio processing library.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    dest_path = output_dir / "audio.wav"
    shutil.copyfile(input_path, dest_path)
    # Dummy duration - in a real implementation calculate from waveform metadata.
    duration_sec = 0.0
    log_json("audio_normalised", source=str(input_path), dest=str(dest_path))
    return dest_path, duration_sec


def generate_call_id() -> str:
    return f"c_{uuid.uuid4().hex[:8]}"


__all__ = ["normalise_audio", "generate_call_id", "TARGET_SAMPLE_RATE", "TARGET_CHANNELS"]
