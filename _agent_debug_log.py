"""Tiny NDJSON debug logger for session 3b3112. Do not log secrets/PII."""
from __future__ import annotations

import json
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_LOG = _ROOT / "debug-3b3112.log"
_SESSION = "3b3112"


def dbg(hypothesis_id: str, location: str, message: str, data=None, run_id: str = "pre"):
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
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
