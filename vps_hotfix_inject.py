#!/usr/bin/env python3
"""
Хотфикс после git clone https://github.com/Kindk10/tbankmitm
(на GitHub ещё блокируется inject для WebView/Chrome UA).

На VPS:
  cd ~/tbankmitm/tbankmitm
  # скопируй этот файл с ПК или создай через nano
  python3 vps_hotfix_inject.py
  pkill -f mitm_run_dump || true
  bash start_vps.sh
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def patch_history() -> None:
    path = os.path.join(ROOT, "history.py")
    src = _read(path)
    orig = src

    # 1) Не выходить, если manual_operations пуст
    src2, n = re.subn(
        r"(ensure_manual_operations_fresh\(\)\n)"
        r"[ \t]+if not manual_operations:\n"
        r"[ \t]+return False\n",
        r"\1",
        src,
        count=1,
    )
    if n:
        src = src2
        print("[OK] history: removed early `if not manual_operations`")
    else:
        print("[..] history: early manual_operations guard already gone or missing")

    # 2) Главный баг: полный return на desktop/WebView UA
    if "is_strict_ops_feed" not in src:
        src2, n = re.subn(
            r"([ \t]+)page_kind = _mybank_page_kind\(referer\)\n"
            r"[ \t]+if _ua_looks_like_desktop_browser\(user_agent\):\n"
            r"[ \t]+return False\n"
            r"([ \t]+)request_feed_like = _request_looks_like_operations_feed\(request_text\)\n",
            (
                r"\1page_kind = _mybank_page_kind(referer)\n"
                r"\2request_feed_like = _request_looks_like_operations_feed(request_text)\n"
                r"\2product_surface = _response_looks_like_product_surface(data)\n"
                r"\2if page_kind == \"\" and request_feed_like and not product_surface:\n"
                r"\2    page_kind = \"operations\"\n"
                r"\2candidates = _candidate_operation_lists_from_data(\n"
                r"\2    data,\n"
                r"\2    allow_graphql_edges=(page_kind != \"mybank\"),\n"
                r"\2    allow_widget_containers=(page_kind == \"operations\" and not product_surface),\n"
                r"\2)\n"
                r"\2has_operation_candidates = bool(candidates)\n"
                r"\2url_u = (url or \"\").lower()\n"
                r"\2is_strict_ops_feed = \"/api/common/v1/operations\" in url_u and \"operations_category_list\" not in url_u\n"
                r"\2# WebView/Chrome UA: inject на ленте операций не отключаем\n"
                r"\2if _ua_looks_like_desktop_browser(user_agent) and not (\n"
                r"\2    is_strict_ops_feed or has_operation_candidates or page_kind == \"operations\"\n"
                r"\2):\n"
                r"\2    return False\n"
                r"\2# HOTFIX_SKIP_DUP_START\n"
                r"\2request_feed_like = _request_looks_like_operations_feed(request_text)\n"
            ),
            src,
            count=1,
        )
        if n:
            src = src2
            # убрать дублирующий кусок product_surface/candidates после маркера
            src = re.sub(
                r"[ \t]+# HOTFIX_SKIP_DUP_START\n"
                r"[ \t]+request_feed_like = _request_looks_like_operations_feed\(request_text\)\n"
                r"[ \t]+product_surface = _response_looks_like_product_surface\(data\)\n"
                r"[ \t]+if page_kind == \"\" and request_feed_like and not product_surface:\n"
                r"[ \t]+page_kind = \"operations\"\n"
                r"[ \t]+candidates = _candidate_operation_lists_from_data\(\n"
                r"[ \t]+data,\n"
                r"[ \t]+allow_graphql_edges=\(page_kind != \"mybank\"\),\n"
                r"[ \t]+allow_widget_containers=\(page_kind == \"operations\" and not product_surface\),\n"
                r"[ \t]+\)\n"
                r"[ \t]+has_operation_candidates = bool\(candidates\)\n",
                "",
                src,
                count=1,
            )
            print("[OK] history: WebView UA inject unblocked")
        else:
            print("[FAIL] history: UA return-False block not found")
            print("       grep -n '_ua_looks_like_desktop_browser' history.py")
    else:
        print("[OK] history: is_strict_ops_feed already present")

    # 3) url_u уже может быть выше — убрать повторное присвоение если дубль подряд
    src = re.sub(
        r"([ \t]+url_u = \(url or \"\"\)\.lower\(\)\n)"
        r"([ \t]+# Не использовать подстроку \"transfer\".*?\n)"
        r"\1",
        r"\1\2",
        src,
        count=1,
        flags=re.S,
    )

    if src != orig:
        _write(path, src)
        # syntax check
        compile(src, path, "exec")
        print("[OK] history.py written + syntax OK")
    else:
        print("[SKIP] history.py unchanged")


def patch_sbp() -> None:
    path = os.path.join(ROOT, "tbank_sbp_debit_injector.py")
    src = _read(path)
    if 'if "/mybank" in ref:' in src or "if '/mybank' in ref:" in src:
        print("[OK] sbp: /mybank referer already ok")
        return
    src2, n = re.subn(
        r"(if not ref:\n[ \t]+return True\n)"
        r"([ \t]+)return \"/mybank/operations\" in ref\n",
        r'\1\2if "/mybank" in ref:\n\2    return True\n\2return "/mybank/operations" in ref\n',
        src,
        count=1,
    )
    if not n:
        print("[FAIL] sbp: referer gate not found")
        return
    compile(src2, path, "exec")
    _write(path, src2)
    print("[OK] tbank_sbp_debit_injector.py referer broadened")


def patch_panel_bridge() -> None:
    path = os.path.join(ROOT, "panel_bridge.py")
    src = _read(path)
    if 'path_only.startswith("/api/")' in src or "path_only.startswith('/api/')" in src:
        print("[OK] panel_bridge: /api exempt already present")
        return
    src2, n = re.subn(
        r"(if not _client_ok_for_panel\(client_ip\):\n)"
        r"([ \t]+)(# #region agent log\n|"
        r"flow\.response = http\.Response\.make\(403)",
        r'\1\2if flow.response is not None:\n\2    return\n'
        r'\2path_only = _panel_request_path_only(flow.request.path)\n'
        r'\2if path_only.startswith("/api/"):\n\2    return\n\2\3',
        src,
        count=1,
    )
    if not n:
        # simpler insert
        src2, n = re.subn(
            r"(if not _client_ok_for_panel\(client_ip\):\n)",
            r'\1        if flow.response is not None:\n'
            r'            return\n'
            r'        _po = _panel_request_path_only(flow.request.path)\n'
            r'        if _po.startswith("/api/"):\n'
            r'            return\n',
            src,
            count=1,
        )
    if not n:
        print("[WARN] panel_bridge: IP gate pattern not found")
        return
    compile(src2, path, "exec")
    _write(path, src2)
    print("[OK] panel_bridge.py: do not 403 over /api")


def patch_tls() -> None:
    path = os.path.join(ROOT, "tls_passthrough_hosts.py")
    if not os.path.isfile(path):
        return
    src = _read(path)
    if "tmsg.tbank.ru" in src:
        print("[OK] tls: tmsg already listed")
        return
    src2, n = re.subn(
        r'("s3\.tbank\.ru",\n)(\))',
        r'\1    "tmsg.tbank.ru",\n    "tmsg.tinkoff.ru",\n\2',
        src,
        count=1,
    )
    if not n:
        print("[WARN] tls: SNI list not patched")
        return
    _write(path, src2)
    print("[OK] tls_passthrough: added tmsg")


def ensure_nonbank() -> None:
    path = os.path.join(ROOT, "nonbank_connect_block.py")
    if not os.path.isfile(path):
        _write(
            path,
            '''"""Блок CONNECT к не-банковским хостам (сканеры на открытом прокси)."""
from __future__ import annotations
import os
from mitmproxy import http
from bank_filter import _BANK_KEYS

_BLOCK = os.environ.get("TBANKMITM_BLOCK_NONBANK", "1").strip().lower() not in ("0", "false", "no", "off")
_DEBUG = os.environ.get("BANK_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")


def _host_is_bank(host: str) -> bool:
    h = (host or "").lower().strip()
    return bool(h) and any(k in h for k in _BANK_KEYS)


def request(flow: http.HTTPFlow) -> None:
    if not _BLOCK or flow.request.method != "CONNECT":
        return
    host = (flow.request.host or getattr(flow.request, "pretty_host", None) or "").strip()
    if _host_is_bank(host):
        return
    if _DEBUG:
        print(f"[nonbank_connect_block] reject CONNECT host={host!r}")
    flow.response = http.Response.make(403, b"non-bank CONNECT blocked")
''',
        )
        print("[OK] created nonbank_connect_block.py")
    chain = os.path.join(ROOT, "mitm_addon_chain.py")
    src = _read(chain)
    if "nonbank_connect_block.py" not in src:
        src2 = src.replace(
            '"tls_passthrough_hosts.py",\n    "transfer.py",',
            '"tls_passthrough_hosts.py",\n    "nonbank_connect_block.py",\n    "transfer.py",',
        )
        if src2 == src:
            print("[WARN] mitm_addon_chain: could not insert nonbank script")
        else:
            _write(chain, src2)
            print("[OK] mitm_addon_chain: nonbank added")
    else:
        print("[OK] mitm_addon_chain already has nonbank")


def patch_config() -> None:
    path = os.path.join(ROOT, "config.json")
    if not os.path.isfile(path):
        return
    src = _read(path)
    if '"browser_finanalytics_dom_patch": false' in src:
        _write(path, src.replace('"browser_finanalytics_dom_patch": false', '"browser_finanalytics_dom_patch": true', 1))
        print("[OK] config: browser_finanalytics_dom_patch=true")
    else:
        print("[OK] config finanalytics flag ok")


def verify() -> None:
    hist = _read(os.path.join(ROOT, "history.py"))
    bad = re.search(
        r"if _ua_looks_like_desktop_browser\(user_agent\):\n[ \t]+return False\n",
        hist,
    )
    if bad and "is_strict_ops_feed" not in hist:
        print("[VERIFY FAIL] UA still hard-blocks inject")
        sys.exit(2)
    if "if not manual_operations:\n" in hist and "inject_manual_into_response" in hist:
        # check specifically early in inject
        m = re.search(
            r"def inject_manual_into_response[\s\S]{0,400}?if not manual_operations:\n[ \t]+return False",
            hist,
        )
        if m:
            print("[VERIFY FAIL] inject still returns when manual_operations empty")
            sys.exit(2)
    print("[VERIFY OK] critical inject gates fixed")


def main() -> int:
    os.chdir(ROOT)
    print("=== VPS hotfix in", ROOT, "===")
    patch_history()
    patch_sbp()
    patch_panel_bridge()
    patch_tls()
    ensure_nonbank()
    patch_config()
    verify()
    print()
    print("Restart mitm:")
    print("  pkill -f mitm_run_dump || true")
    print("  export BANK_DEBUG=1")
    print("  bash start_vps.sh")
    print()
    print("Check API:")
    print("  curl -s http://127.0.0.1:8082/api/operations | head -c 400")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
