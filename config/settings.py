"""Application configuration management."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()


def _get_env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    llm_temperature: float
    postgres_dsn: str
    s3_endpoint: str
    s3_bucket: str
    pipeline_max_runtime_min: int

    artifacts_dir: Path = BASE_DIR / "artifacts"

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            gemini_api_key=_get_env("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            postgres_dsn=_get_env("POSTGRES_DSN", ""),
            s3_endpoint=_get_env("S3_ENDPOINT", ""),
            s3_bucket=_get_env("S3_BUCKET", ""),
            pipeline_max_runtime_min=int(os.getenv("PIPELINE_MAX_RUNTIME_MIN", "10")),
        )


def get_settings() -> Settings:
    return Settings.load()


__all__ = ["Settings", "get_settings", "BASE_DIR"]
