"""Speaker diarisation placeholder."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from asr.transcriber import Segment
from utils.logging import log_json


@dataclass
class DiarizationResult:
    segments: List[Segment]


def assign_roles(segments: Iterable[Segment]) -> DiarizationResult:
    """Assign manager/client roles to ASR segments.

    The placeholder implementation alternates between Manager (M) and Client (C).
    """

    result: List[Segment] = []
    role_cycle = ["M", "C"]
    for idx, seg in enumerate(segments):
        role = role_cycle[idx % 2]
        result.append(Segment(start=seg.start, end=seg.end, speaker=role, text=seg.text))
    log_json("diarization_complete", segments=len(result))
    return DiarizationResult(segments=result)


__all__ = ["assign_roles", "DiarizationResult"]
