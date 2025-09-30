"""Structured logging helpers."""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, asdict
from typing import Any, Dict

_LOGGER = logging.getLogger("call_audit")
if not _LOGGER.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.INFO)


def log_json(event: str, **fields: Any) -> None:
    payload: Dict[str, Any] = {"event": event, **fields}
    _LOGGER.info(json.dumps(payload, ensure_ascii=False))


@dataclass
class RequestContext:
    request_id: str
    step: str

    def log(self, event: str, **fields: Any) -> None:
        log_json(event, request_id=self.request_id, step=self.step, **fields)


__all__ = ["log_json", "RequestContext"]
