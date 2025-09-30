"""Pipeline orchestration helpers for call analysis."""
from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from asr.transcriber import WhisperTranscriber
from config.settings import get_settings
from diarization.diarizer import assign_roles
from ingest.audio_processor import generate_call_id, normalise_audio
from nlp.llm_evaluator import evaluate_transcript
from scoring.metrics import AggregatedReport, build_report
from utils.logging import RequestContext


@dataclass
class TranscriptLine:
    start: float
    end: float
    speaker: str
    text: str

    @property
    def ts(self) -> str:
        return f"{self.start:.2f}-{self.end:.2f}"

    def as_display(self) -> str:
        return f"[{self.ts}] {self.speaker}: {self.text}"


@dataclass
class PipelineArtifacts:
    base_dir: Path
    report_json: Path
    report_html: Path
    transcript_txt: Path
    audio_path: Path


@dataclass
class PipelineResult:
    call_id: str
    consent: bool
    report: AggregatedReport
    llm_payload: Dict[str, Any]
    transcript_lines: List[TranscriptLine]
    artifacts: PipelineArtifacts
    payload: Dict[str, Any]


class PipelineError(RuntimeError):
    """Raised when the pipeline cannot complete successfully."""


def run_pipeline(audio_path: Path, *, output_dir: Optional[Path] = None, consent: bool = False) -> PipelineResult:
    """Execute the full call-audit pipeline and persist artifacts."""

    if not audio_path.exists():
        raise PipelineError(f"Audio file not found: {audio_path}")

    settings = get_settings()
    call_id = generate_call_id()
    context = RequestContext(request_id=call_id, step="pipeline")

    base_output = Path(output_dir) if output_dir else settings.artifacts_dir
    base_dir = base_output / call_id
    audio_dir = base_dir / "input"
    base_dir.mkdir(parents=True, exist_ok=True)

    context.log("pipeline_started", audio=str(audio_path))
    normalised_audio, duration_sec = normalise_audio(audio_path, audio_dir)

    transcriber = WhisperTranscriber()
    transcript_result = transcriber.transcribe(normalised_audio)

    diarization_result = assign_roles(transcript_result.segments)

    transcript_lines: List[TranscriptLine] = [
        TranscriptLine(start=seg.start, end=seg.end, speaker=seg.speaker, text=seg.text)
        for seg in diarization_result.segments
    ]
    transcript_text = "\n".join(line.as_display() for line in transcript_lines)

    try:
        llm_payload = evaluate_transcript(transcript_text)
    except Exception as exc:  # noqa: BLE001 - propagate stub fallback
        context.log("llm_error", error=str(exc))
        llm_payload = {
            "empathy": 0.0,
            "compliance": 0.0,
            "structure": 0.0,
            "checklist": [],
            "highlights": [],
            "partial": True,
            "error": str(exc),
        }

    report = build_report(
        call_id=call_id,
        language=transcript_result.language,
        duration_sec=duration_sec,
        llm_payload=llm_payload,
        segments=diarization_result.segments,
    )

    artifacts = _write_artifacts(
        base_dir=base_dir,
        transcript_text=transcript_text,
        audio_path=normalised_audio,
    )

    payload = _build_payload(
        call_id=call_id,
        consent=consent,
        report=report,
        llm_payload=llm_payload,
        transcript_lines=transcript_lines,
        artifacts=artifacts,
    )

    _persist_payload(artifacts.report_json, payload)
    _persist_html(artifacts.report_html, payload)

    context.log("pipeline_complete", json=str(artifacts.report_json), html=str(artifacts.report_html))

    return PipelineResult(
        call_id=call_id,
        consent=consent,
        report=report,
        llm_payload=llm_payload,
        transcript_lines=transcript_lines,
        artifacts=artifacts,
        payload=payload,
    )


def _write_artifacts(
    *,
    base_dir: Path,
    transcript_text: str,
    audio_path: Path,
) -> PipelineArtifacts:
    artifacts_dir = base_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    transcript_path = artifacts_dir / "transcript.txt"
    transcript_path.write_text(transcript_text, encoding="utf-8")

    return PipelineArtifacts(
        base_dir=artifacts_dir,
        report_json=artifacts_dir / "report.json",
        report_html=artifacts_dir / "report.html",
        transcript_txt=transcript_path,
        audio_path=audio_path,
    )


def _build_payload(
    *,
    call_id: str,
    consent: bool,
    report: AggregatedReport,
    llm_payload: Dict[str, Any],
    transcript_lines: List[TranscriptLine],
    artifacts: PipelineArtifacts,
) -> Dict[str, Any]:
    settings = get_settings()
    segments_payload = [
        {
            "start": line.start,
            "end": line.end,
            "speaker": line.speaker,
            "text": line.text,
            "ts": line.ts,
        }
        for line in transcript_lines
    ]

    artifact_urls = _build_artifact_urls(artifacts, settings.artifacts_dir)

    payload: Dict[str, Any] = {
        "callId": call_id,
        "consent": consent,
        "language": report.language,
        "durationSec": report.duration_sec,
        "scores": {
            "empathy": report.scores.empathy,
            "compliance": report.scores.compliance,
            "structure": report.scores.structure,
            "checklist": report.scores.checklist,
            "highlights": report.scores.highlights,
        },
        "operational": {
            "silencePct": report.operational.silence_pct,
            "overlapPct": report.operational.overlap_pct,
            "speechRateWpm": report.operational.speech_rate_wpm,
            "interruptions": report.operational.interruptions,
        },
        "segments": segments_payload,
        "transcript": {
            "text": "\n".join(line.as_display() for line in transcript_lines),
            "lines": segments_payload,
        },
        "llmRaw": llm_payload,
        "artifacts": {
            "json": {
                "path": str(artifacts.report_json),
                "url": artifact_urls.get("report_json"),
            },
            "html": {
                "path": str(artifacts.report_html),
                "url": artifact_urls.get("report_html"),
            },
            "transcript": {
                "path": str(artifacts.transcript_txt),
                "url": artifact_urls.get("transcript_txt"),
            },
        },
    }
    return payload


def _build_artifact_urls(artifacts: PipelineArtifacts, artifacts_root: Path) -> Dict[str, Optional[str]]:
    mapping = {
        "report_json": artifacts.report_json,
        "report_html": artifacts.report_html,
        "transcript_txt": artifacts.transcript_txt,
    }

    urls: Dict[str, Optional[str]] = {}
    for key, file_path in mapping.items():
        try:
            relative = file_path.relative_to(artifacts_root)
        except ValueError:
            urls[key] = None
        else:
            urls[key] = f"/artifacts/{relative.as_posix()}"
    return urls


def _persist_payload(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _persist_html(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    html = _render_html(payload)
    path.write_text(html, encoding="utf-8")


def _render_html(payload: Dict[str, Any]) -> str:
    scores = payload["scores"]
    operational = payload["operational"]
    segments = payload.get("segments", [])

    checklist_rows = "".join(
        f"<tr><td>{escape(str(item.get('id', '')))}</td>"
        f"<td>{'✅' if item.get('passed') else '⚠️'}</td>"
        f"<td>{escape(str(item.get('reason', '')))}</td>"
        f"<td>{escape(str(item.get('evidence', '')))}</td>"
        f"<td>{escape(str(item.get('ts', '')))}</td></tr>"
        for item in scores.get("checklist", [])
    )

    highlight_items = "".join(
        f"<li><strong>{escape(str(item.get('type', '')))}</strong>: "
        f"{escape(str(item.get('quote', '')))} <em>{escape(str(item.get('ts', '')))}</em></li>"
        for item in scores.get("highlights", [])
    )

    segment_rows = "".join(
        f"<tr><td>{escape(seg['ts'])}</td><td>{escape(seg['speaker'])}</td><td>{escape(seg['text'])}</td></tr>"
        for seg in segments
    )

    html = f"""
    <!doctype html>
    <html lang=\"ru\">
    <head>
        <meta charset=\"utf-8\" />
        <title>Call report {escape(payload['callId'])}</title>
        <style>
            body {{ font-family: 'Inter', Arial, sans-serif; margin: 2rem; color: #0f172a; background: #f8fafc; }}
            h1, h2 {{ color: #0f172a; }}
            .score-card {{ display: flex; gap: 1.5rem; margin-bottom: 1.5rem; }}
            .score {{ background: #fff; padding: 1rem; border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.1); }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; background: #fff; border-radius: 0.75rem; overflow: hidden; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.1); }}
            th, td {{ padding: 0.75rem 1rem; border-bottom: 1px solid #e2e8f0; text-align: left; }}
            th {{ background: #e2e8f0; font-weight: 600; }}
            ul {{ background: #fff; padding: 1rem 1.25rem; border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.1); }}
            .meta {{ margin-bottom: 1.5rem; }}
        </style>
    </head>
    <body>
        <h1>Call report — {escape(payload['callId'])}</h1>
        <div class=\"meta\">
            <p><strong>Language:</strong> {escape(str(payload.get('language', '')))}</p>
            <p><strong>Duration (sec):</strong> {payload.get('durationSec', 0):.2f}</p>
        </div>
        <section class=\"score-card\">
            <div class=\"score\"><h2>Empathy</h2><p>{scores.get('empathy', 0):.2f}</p></div>
            <div class=\"score\"><h2>Compliance</h2><p>{scores.get('compliance', 0):.2f}</p></div>
            <div class=\"score\"><h2>Structure</h2><p>{scores.get('structure', 0):.2f}</p></div>
        </section>
        <section>
            <h2>Operational metrics</h2>
            <p>Silence %: {operational.get('silencePct', 0):.2f}</p>
            <p>Overlap %: {operational.get('overlapPct', 0):.2f}</p>
            <p>Speech rate (manager/client): {escape(str(operational.get('speechRateWpm', {})))}</p>
            <p>Interruptions (manager/client): {escape(str(operational.get('interruptions', {})))}</p>
        </section>
        <section>
            <h2>Checklist</h2>
            <table>
                <thead><tr><th>ID</th><th>Status</th><th>Reason</th><th>Evidence</th><th>TS</th></tr></thead>
                <tbody>{checklist_rows or '<tr><td colspan="5">No checklist items</td></tr>'}</tbody>
            </table>
        </section>
        <section>
            <h2>Highlights</h2>
            <ul>{highlight_items or '<li>No highlights</li>'}</ul>
        </section>
        <section>
            <h2>Transcript</h2>
            <table>
                <thead><tr><th>TS</th><th>Speaker</th><th>Text</th></tr></thead>
                <tbody>{segment_rows or '<tr><td colspan="3">No transcript segments</td></tr>'}</tbody>
            </table>
        </section>
    </body>
    </html>
    """
    return html


__all__ = [
    "PipelineResult",
    "PipelineArtifacts",
    "TranscriptLine",
    "PipelineError",
    "run_pipeline",
]
