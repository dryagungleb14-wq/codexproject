"""Reusable pipeline orchestration utilities for the call audit MVP."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from asr.transcriber import Segment, WhisperTranscriber
from config.settings import get_settings
from diarization.diarizer import assign_roles
from ingest.audio_processor import generate_call_id, normalise_audio
from nlp.llm_evaluator import evaluate_transcript
from scoring.metrics import AggregatedReport, build_report
from utils.logging import RequestContext, log_json


@dataclass
class PipelineResult:
    """Container with artefacts produced by :func:`run_pipeline`."""

    call_id: str
    report: AggregatedReport
    transcript: List[Dict[str, Any]]
    json_payload: Dict[str, Any]
    json_path: Path
    html_path: Path
    report_html: str
    context: RequestContext = field(repr=False)

    def to_response(self) -> Dict[str, Any]:
        """Serialise result for API consumers."""

        payload = dict(self.json_payload)
        payload["transcript"] = self.transcript
        payload["reportHtml"] = self.report_html
        payload["artifacts"] = {
            "json": str(self.json_path),
            "html": str(self.html_path),
        }
        return payload


def _build_transcript_segments(segments: List[Segment]) -> Dict[str, Any]:
    transcript_lines: List[str] = []
    transcript_view: List[Dict[str, Any]] = []
    for seg in segments:
        transcript_lines.append(f"[{seg.start:.2f}-{seg.end:.2f}] {seg.speaker}: {seg.text}")
        transcript_view.append(
            {
                "start": seg.start,
                "end": seg.end,
                "speaker": seg.speaker,
                "text": seg.text,
            }
        )
    transcript_blob = "\n".join(transcript_lines)
    return {"blob": transcript_blob, "view": transcript_view}


def _build_html(report: AggregatedReport, transcript: List[Dict[str, Any]]) -> str:
    checklist_rows = "".join(
        f"<tr><td>{item.get('id', '')}</td><td>{'✅' if item.get('passed') else '⚠️'}</td>"
        f"<td>{item.get('score', 0)}/{item.get('max', 0)}</td><td>{item.get('reason', '')}</td>"
        f"<td>{item.get('evidence', '')}</td><td>{item.get('ts', '')}</td></tr>"
        for item in report.scores.checklist
    )
    transcript_rows = "".join(
        f"<tr><td>{seg['start']:.2f}</td><td>{seg['end']:.2f}</td><td>{seg['speaker']}</td><td>{seg['text']}</td></tr>"
        for seg in transcript
    )
    html = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Call report {report.call_id}</title>
  <style>
    body {{ font-family: 'Inter', system-ui, sans-serif; margin: 2rem; line-height: 1.5; }}
    h1 {{ font-size: 1.75rem; margin-bottom: 1rem; }}
    section {{ margin-bottom: 2rem; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #d4d4d8; padding: 0.5rem; text-align: left; }}
    th {{ background: #f4f4f5; }}
  </style>
</head>
<body>
  <h1>Call report {report.call_id}</h1>
  <section>
    <p><strong>Language:</strong> {report.language}</p>
    <p><strong>Duration:</strong> {report.duration_sec:.2f} sec</p>
    <p><strong>Scores:</strong> Empathy {report.scores.empathy:.2f}, Compliance {report.scores.compliance:.2f}, Structure {report.scores.structure:.2f}</p>
  </section>
  <section>
    <h2>Checklist</h2>
    <table>
      <thead>
        <tr><th>ID</th><th>Status</th><th>Score</th><th>Reason</th><th>Evidence</th><th>Timestamp</th></tr>
      </thead>
      <tbody>
        {checklist_rows}
      </tbody>
    </table>
  </section>
  <section>
    <h2>Transcript</h2>
    <table>
      <thead>
        <tr><th>Start</th><th>End</th><th>Speaker</th><th>Text</th></tr>
      </thead>
      <tbody>
        {transcript_rows}
      </tbody>
    </table>
  </section>
</body>
</html>
"""
    return html


def run_pipeline(audio_path: Path, *, artifacts_root: Optional[Path] = None, consent: bool = False) -> PipelineResult:
    """Execute the offline pipeline and persist artefacts."""

    if artifacts_root is None:
        settings = get_settings()
        base_output = settings.artifacts_dir
    else:
        base_output = artifacts_root
    call_id = generate_call_id()
    context = RequestContext(request_id=call_id, step="pipeline")

    output_dir = base_output / call_id
    normalised_audio, duration_sec = normalise_audio(audio_path, output_dir)

    transcriber = WhisperTranscriber()
    transcript_result = transcriber.transcribe(normalised_audio)
    diarization_result = assign_roles(transcript_result.segments)

    transcript_data = _build_transcript_segments(diarization_result.segments)
    transcript_blob = transcript_data["blob"]
    transcript_view = transcript_data["view"]

    llm_payload: Dict[str, Any]
    try:
        llm_payload = evaluate_transcript(transcript_blob)
        partial = bool(llm_payload.get("partial", False))
    except Exception as exc:  # noqa: BLE001
        log_json("llm_error", error=str(exc))
        llm_payload = {
            "empathy": 0.0,
            "compliance": 0.0,
            "structure": 0.0,
            "checklist": [],
            "highlights": [],
            "partial": True,
        }
        partial = True

    report = build_report(
        call_id=call_id,
        language=transcript_result.language,
        duration_sec=duration_sec,
        llm_payload=llm_payload,
        segments=diarization_result.segments,
    )

    json_payload: Dict[str, Any] = {
        "callId": report.call_id,
        "lang": report.language,
        "durationSec": report.duration_sec,
        "scores": {
            "empathy": report.scores.empathy,
            "compliance": report.scores.compliance,
            "structure": report.scores.structure,
        },
        "operational": {
            "silencePct": report.operational.silence_pct,
            "overlapPct": report.operational.overlap_pct,
            "speechRateWpm": report.operational.speech_rate_wpm,
            "interruptions": report.operational.interruptions,
        },
        "checklist": report.scores.checklist,
        "highlights": report.scores.highlights,
        "consent": consent,
    }
    if partial:
        json_payload["partial"] = True

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False))

    report_html = _build_html(report, transcript_view)
    html_path = output_dir / "report.html"
    html_path.write_text(report_html)

    context.log(
        "pipeline_complete",
        call_id=call_id,
        json=str(json_path),
        html=str(html_path),
        consent=consent,
    )

    return PipelineResult(
        call_id=call_id,
        report=report,
        transcript=transcript_view,
        json_payload=json_payload,
        json_path=json_path,
        html_path=html_path,
        report_html=report_html,
        context=context,
    )


__all__ = ["PipelineResult", "run_pipeline"]
