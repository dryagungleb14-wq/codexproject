"""Automatic speech recognition via faster-whisper (stub)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from utils.logging import log_json


@dataclass
class Segment:
    start: float
    end: float
    speaker: str
    text: str


@dataclass
class TranscriptResult:
    text: str
    segments: List[Segment]
    language: str


class WhisperTranscriber:
    """Lightweight wrapper around faster-whisper.

    The current implementation is a stub that returns placeholder text. It keeps
    the interface stable for later integration with the actual ASR backend.
    """

    def __init__(self, model_size: str = "small") -> None:
        self.model_size = model_size

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        dummy_text = "[ASR stub] Replace with real transcription output."
        segments = [Segment(start=0.0, end=5.0, speaker="M", text=dummy_text)]
        log_json("asr_transcribed", audio=str(audio_path), tokens=len(dummy_text.split()))
        return TranscriptResult(text=dummy_text, segments=segments, language="ru")


__all__ = ["WhisperTranscriber", "TranscriptResult", "Segment"]
