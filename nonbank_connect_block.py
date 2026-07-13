"""
Блок CONNECT к не-банковским хостам: открытый прокси на VPS (0.0.0.0:8082) ловит сканеры
(739404.cc и т.п.) — шум в логах и лишняя нагрузка.

Отключить: TBANKMITM_BLOCK_NONBANK=0
"""
from __future__ import annotations

import os

from mitmproxy import http

from bank_filter import _BANK_KEYS

_BLOCK = os.environ.get("TBANKMITM_BLOCK_NONBANK", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
_DEBUG = os.environ.get("BANK_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")


def _host_is_bank(host: str) -> bool:
    h = (host or "").lower().strip()
    if not h:
        return False
    return any(k in h for k in _BANK_KEYS)


def request(flow: http.HTTPFlow) -> None:
    if not _BLOCK:
        return
    if flow.request.method != "CONNECT":
        return
    host = (flow.request.host or flow.request.pretty_host or "").strip()
    if _host_is_bank(host):
        return
    if _DEBUG:
        print(f"[nonbank_connect_block] reject CONNECT host={host!r}")
    flow.response = http.Response.make(403, b"non-bank CONNECT blocked")
