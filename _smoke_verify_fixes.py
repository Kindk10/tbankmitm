"""Offline smoke checks for the five fixes; writes NDJSON to debug-f24997.log."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from _agent_debug_log import dbg
import controller
import func
import panel_bridge


def main():
    # H1 phone sync
    before = (controller.config.get("name") or {}).get("phone_number")
    controller.config.setdefault("name", {})["phone"] = "+79001112233"
    controller.config["name"]["phone_number"] = "9991112233"
    controller.sync_name_phone_number(controller.config["name"])
    after = controller.config["name"].get("phone_number")
    dbg("H1", "smoke.phone", "sync result", {
        "before": before,
        "after": after,
        "expected": "9001112233",
        "ok": after == "9001112233",
    })

    # H2 CORS / totals helpers
    try:
        import history
        di, de, _, _ = history.get_panel_chart_display_totals()
        dbg("H2", "smoke.totals", "chart totals", {
            "income": di,
            "expense": de,
            "expense_ok": de is not None,
        })
    except Exception as e:
        dbg("H2", "smoke.totals", "chart totals failed", {"error_type": type(e).__name__})

    # H3 receipt template resolve + generate does not raise
    tpl = func._resolve_receipt_template_path()
    receipt = None
    try:
        receipt = func.generate_operation_receipt({
            "id": "m_smoketest01",
            "date": "13.07.2026, 12:00:00",
            "amount": 1.0,
            "type": "Debit",
            "bank": "СБП",
            "title": "Smoke",
            "phone": "+79001112233",
        })
        dbg("H3", "smoke.receipt", "generate", {
            "tpl_found": bool(tpl),
            "receipt_ok": receipt is None or os.path.isfile(str(receipt)),
            "raised": False,
        })
    except Exception as e:
        dbg("H3", "smoke.receipt", "generate raised", {"error_type": type(e).__name__})

    # H4 registration address field present in panel HTML
    html = panel_bridge.HTML_PANEL
    dbg("H4", "smoke.statement_ui", "address field", {
        "has_addr_input": 'id="stmt_registration_address"' in html,
        "has_save_fn": "saveStatementProfile" in html,
        "has_panel_fetch_origin": 'id="panel_fetch_origin"' in html,
    })

    # H5 potatso allow
    dbg("H5", "smoke.panel_access", "listen/allow", {
        "allow_any": bool(panel_bridge._PANEL_ALLOW_ANY),
        "listen_host": panel_bridge._LISTEN_HOST,
        "start_bat_has_0_0_0_0": "0.0.0.0" in open(os.path.join(ROOT, "start.bat"), encoding="utf-8", errors="ignore").read(),
        "start_bat_allow_any": "TBANKMITM_PANEL_ALLOW_ANY=1" in open(os.path.join(ROOT, "start.bat"), encoding="utf-8", errors="ignore").read(),
    })

    print("smoke done -> debug-f24997.log")


if __name__ == "__main__":
    main()
