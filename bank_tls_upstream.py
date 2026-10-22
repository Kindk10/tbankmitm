"""
TLS к банку через mitm: не валидировать upstream-цепочку (отозванные / российские CA).

Клиент (iPhone) доверяет только сертификату mitm — его нужно установить через mitm.it.
Цепочка банка на VPS проверяется mitmproxy с ssl_insecure=true (дублируем в runtime).

Лог SSL-ошибок: TBANKMITM_TLS_DEBUG=1
HTTP/2 к origin (если без него не коннектится): TBANKMITM_HTTP2=1
"""
from __future__ import annotations

import os

from mitmproxy import ctx, http

_TLS_DEBUG = os.environ.get("TBANKMITM_TLS_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
_HTTP2 = os.environ.get("TBANKMITM_HTTP2", "").strip().lower() in ("1", "true", "yes", "on")


def _apply_tls_options() -> None:
    try:
        ctx.options.ssl_insecure = True
        if _HTTP2:
            ctx.options.http2 = True
    except Exception:
        pass


def running() -> None:
    _apply_tls_options()


def configure(updated) -> None:
    if updated:
        _apply_tls_options()


def error(flow: http.HTTPFlow) -> None:
    if not flow.error or not _TLS_DEBUG:
        return
    try:
        msg = str(getattr(flow.error, "msg", None) or flow.error)
    except Exception:
        msg = "unknown"
    low = msg.lower()
    if any(x in low for x in ("certificate", "ssl", "tls", "handshake", "verify")):
        host = getattr(flow.request, "host", "") or ""
        print(f"[bank_tls_upstream] upstream TLS host={host!r}: {msg[:240]}")
