"""FastAPI application that exposes the pipeline through a simple web UI."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from pipeline import run_pipeline

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
INDEX_PATH = FRONTEND_DIR / "index.html"

app = FastAPI(title="Call Quality Audit", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def _load_index() -> str:
    if INDEX_PATH.exists():
        return INDEX_PATH.read_text(encoding="utf-8")
    return "<h1>Frontend bundle not found</h1>"


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(_load_index())


@app.get("/api/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(audio: UploadFile = File(...), consent: bool = Form(False)) -> Dict[str, object]:
    if not audio.filename:
        raise HTTPException(status_code=400, detail="Audio file is required")

    suffix = Path(audio.filename).suffix or ".wav"
    tmp_path: Path | None = None
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        while chunk := await audio.read(1024 * 1024):
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    if tmp_path is None:
        await audio.close()
        raise HTTPException(status_code=500, detail="Не удалось сохранить загруженный файл")

    try:
        result = run_pipeline(tmp_path, consent=consent)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await audio.close()
        tmp_path.unlink(missing_ok=True)

    return result.to_response()


__all__ = ["app"]
