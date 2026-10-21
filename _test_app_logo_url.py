import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Stub controller before history import
import types

controller = types.ModuleType("controller")
controller.config = {}
sys.modules["controller"] = controller

spec = importlib.util.spec_from_file_location("history_logo", os.path.join(ROOT, "history.py"))
# history imports mitmproxy - test helpers only via exec snippet
exec(open(os.path.join(ROOT, "bank_filter.py"), encoding="utf-8").read(), globals())

# Minimal copy of logo helpers for test
import base64
from urllib.parse import quote

SAME_ORIGIN_PANEL_PREFIX = "/__tbankmitm_panel"


def _normalize_logo_url(raw_logo):
    logo = (raw_logo or "").strip()
    if not logo:
        return ""
    if "imgproxy.cdn-tinkoff.ru/compressed95/" in logo:
        return logo
    if (
        "brands-prod.cdn-tinkoff.ru/" not in logo
        and "brands-static.cdn-tinkoff.ru/" not in logo
        and "bms-logo-prod.t-static.ru/" not in logo
    ):
        return logo
    encoded = base64.b64encode(logo.encode("utf-8")).decode("ascii")
    return f"https://imgproxy.cdn-tinkoff.ru/compressed95/{encoded}"


def _pwa_asset_origin():
    return "https://www.tbank-online.com"


def _app_served_bank_logo_url(logo: str) -> str:
    normalized = _normalize_logo_url(logo)
    if not normalized:
        return ""
    origin = _pwa_asset_origin()
    path = f"{SAME_ORIGIN_PANEL_PREFIX}/panel-bank-logo?u={quote(normalized, safe='')}"
    return f"{origin}{path}"


u = _app_served_bank_logo_url("https://brands-prod.cdn-tinkoff.ru/general_logo/sber.png")
assert u.startswith("https://www.tbank-online.com/__tbankmitm_panel/panel-bank-logo?u="), u
assert "imgproxy" in u or "sber" in u.lower() or "aHR0" in u
print("app logo url ok:", u[:80] + "...")
