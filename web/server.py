"""FastAPI server that exposes the call quality pipeline with a web UI."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config.settings import get_settings
from pipeline import PipelineError, run_pipeline

app = FastAPI(title="Call Quality Audit", version="0.1.0")

frontend_dir = Path(__file__).parent / "frontend"
settings = get_settings()
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
app.mount("/artifacts", StaticFiles(directory=settings.artifacts_dir), name="artifacts")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_path = frontend_dir / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=500, detail="index.html not found")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze_call(consent: bool = Form(False), file: UploadFile = File(...)) -> JSONResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")

    suffix = Path(file.filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        result = run_pipeline(tmp_path, consent=consent)
    except PipelineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    payload = result.payload

    return JSONResponse({"data": payload})


@app.get("/api/artifacts/{call_id}/{filename}")
def get_artifact(call_id: str, filename: str) -> FileResponse:
    artifact_path = settings.artifacts_dir / call_id / filename
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Артефакт не найден")
    return FileResponse(artifact_path)
