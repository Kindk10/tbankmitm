"""Tiny NDJSON debug logger for session f24997. Do not log secrets/PII."""
from __future__ import annotations

import json
import time
from pathlib import Path

_LOG = Path(__file__).resolve().parent / "debug-f24997.log"
_SESSION = "f24997"


def dbg(hypothesis_id: str, location: str, message: str, data=None, run_id: str = "verify1"):
    try:
        payload = {
            "sessionId": _SESSION,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
