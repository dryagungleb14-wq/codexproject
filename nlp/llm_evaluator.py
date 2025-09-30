"""Gemini-based LLM evaluation module."""
from __future__ import annotations

import os
from typing import Any, Dict

from google import genai
from google.genai.types import Content, Part, Schema

from utils.logging import log_json

SYSTEM = (
    "Ты — строгий аудитор качества звонков. На входе: сегменты диалога [speaker, text, ts].\n"
    "Оцени строго по критериям: Empathy, Compliance, Structure (0..1).\n"
    "К каждому пункту чек-листа верни краткую причину и точную цитату с таймкодом.\n"
    "Не выдумывай цитаты — только то, что есть в тексте."
)

score_schema = Schema(
    type="object",
    properties={
        "empathy": Schema(type="number"),
        "compliance": Schema(type="number"),
        "structure": Schema(type="number"),
        "checklist": Schema(
            type="array",
            items=Schema(
                type="object",
                properties={
                    "id": Schema(type="string"),
                    "passed": Schema(type="boolean"),
                    "score": Schema(type="number"),
                    "max": Schema(type="number"),
                    "reason": Schema(type="string"),
                    "evidence": Schema(type="string"),
                    "ts": Schema(type="string"),
                },
            ),
        ),
        "highlights": Schema(
            type="array",
            items=Schema(
                type="object",
                properties={
                    "type": Schema(type="string"),
                    "quote": Schema(type="string"),
                    "ts": Schema(type="string"),
                },
            ),
        ),
    },
    required=["empathy", "compliance", "structure", "checklist"],
)


def _build_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is required for LLM evaluation")
    return genai.Client(api_key=api_key)


def evaluate_transcript(transcript_text: str) -> Dict[str, Any]:
    """Request Gemini evaluation for a transcript."""

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0.1"))

    prompt = (
        "Транскрипт ниже в формате строки с таймкодами и ролями M/C.\n"
        "Верни строго JSON по схеме.\n---\n" + transcript_text
    )

    client = _build_client()
    log_json("llm_request", model=model)
    response = client.models.generate_content(
        model=model,
        contents=[Content(role="user", parts=[Part.from_text(SYSTEM), Part.from_text(prompt)])],
        config={
            "response_mime_type": "application/json",
            "response_schema": score_schema,
            "temperature": temperature,
        },
    )
    log_json("llm_response_received", model=model)
    return response.parsed


__all__ = ["evaluate_transcript", "score_schema", "SYSTEM"]
