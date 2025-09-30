"""Call scoring utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from asr.transcriber import Segment
from utils.logging import log_json


@dataclass
class OperationalMetrics:
    silence_pct: float
    overlap_pct: float
    speech_rate_wpm: Dict[str, float]
    interruptions: Dict[str, int]


@dataclass
class ScoreCard:
    empathy: float
    compliance: float
    structure: float
    checklist: List[Dict[str, object]]
    highlights: List[Dict[str, object]]


@dataclass
class AggregatedReport:
    call_id: str
    language: str
    duration_sec: float
    scores: ScoreCard
    operational: OperationalMetrics


SPEECH_RATE_BASE = 120.0


def compute_operational_metrics(segments: Iterable[Segment]) -> OperationalMetrics:
    speech_rate = {"manager": SPEECH_RATE_BASE, "client": SPEECH_RATE_BASE}
    interruptions = {"byManager": 0, "byClient": 0}
    metrics = OperationalMetrics(
        silence_pct=0.0,
        overlap_pct=0.0,
        speech_rate_wpm=speech_rate,
        interruptions=interruptions,
    )
    return metrics


def build_report(call_id: str, language: str, duration_sec: float, llm_payload: Dict[str, object], segments: Iterable[Segment]) -> AggregatedReport:
    operational = compute_operational_metrics(segments)
    score_card = ScoreCard(
        empathy=float(llm_payload.get("empathy", 0.0)),
        compliance=float(llm_payload.get("compliance", 0.0)),
        structure=float(llm_payload.get("structure", 0.0)),
        checklist=list(llm_payload.get("checklist", [])),
        highlights=list(llm_payload.get("highlights", [])),
    )
    log_json("scoring_complete", call_id=call_id)
    return AggregatedReport(
        call_id=call_id,
        language=language,
        duration_sec=duration_sec,
        scores=score_card,
        operational=operational,
    )


__all__ = ["AggregatedReport", "build_report"]
