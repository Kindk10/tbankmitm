"""
PWA cold start: подмена service worker на «сеть без кэша», чтобы mitm видел HTML/JS
даже если приложение раньше открывали без Potatso.

Отключить: TBANKMITM_PWA_SW_BYPASS=0
"""
from __future__ import annotations

import os

from mitmproxy import http

from bank_filter import ensure_response_decoded, is_bank_flow

_BYPASS = os.environ.get("TBANKMITM_PWA_SW_BYPASS", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# Минимальный SW: сброс Cache Storage и прокси fetch (без offline-shell).
_MITM_SERVICE_WORKER_JS = """\
'use strict';
self.addEventListener('install', function (event) {
  self.skipWaiting();
});
self.addEventListener('activate', function (event) {
  event.waitUntil((async function () {
    try {
      var keys = await caches.keys();
      await Promise.all(keys.map(function (k) { return caches.delete(k); }));
    } catch (e) {}
    try {
      await self.clients.claim();
      var list = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      list.forEach(function (client) {
        try { client.navigate(client.url); } catch (eNav) {}
      });
    } catch (e2) {}
  })());
});
self.addEventListener('fetch', function (event) {
  event.respondWith(fetch(event.request));
});
"""


def _path_lower(flow: http.HTTPFlow) -> str:
    try:
        raw = flow.request.path or flow.request.pretty_url or ""
    except Exception:
        raw = ""
    return raw.lower().split("?", 1)[0]


def _request_is_service_worker(flow: http.HTTPFlow) -> bool:
    if (flow.request.headers.get("Service-Worker") or "").strip().lower() == "script":
        return True
    dest = (flow.request.headers.get("Sec-Fetch-Dest") or "").lower()
    if dest == "serviceworker":
        return True
    path = _path_lower(flow)
    if not path:
        return False
    if path.endswith(".webmanifest") or "precache-manifest" in path:
        return False
    markers = (
        "service-worker",
        "serviceworker",
        "service_worker",
        "/sw.js",
        "sw.js",
        "/worker.js",
        "workbox",
        "ngsw-worker",
        "ngsw.json",
    )
    return any(m in path for m in markers)


def response(flow: http.HTTPFlow) -> None:
    if not _BYPASS or not is_bank_flow(flow) or not flow.response:
        return
    if not _request_is_service_worker(flow):
        return
    ensure_response_decoded(flow)
    flow.response.status_code = 200
    flow.response.text = _MITM_SERVICE_WORKER_JS
    flow.response.headers["Content-Type"] = "application/javascript; charset=utf-8"
    flow.response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    flow.response.headers["Pragma"] = "no-cache"
