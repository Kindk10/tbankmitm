"""Offline smoke checks for the five fixes; writes NDJSON to debug-f24997.log."""
import json
import os
import re
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

    # H3 receipt template + разные суммы (не залипает 20000)
    tpl = func.ensure_blank_receipt_template()
    tpl_ok = bool(tpl) and os.path.isfile(str(tpl)) and os.path.basename(str(tpl)).lower() == "sbpfinaltbanksend.pdf"
    amounts = (1234.0, 5678.0)
    amount_ok = {}
    try:
        import fitz
        for amt in amounts:
            path = func.generate_operation_receipt({
                "id": f"m_smoke_{int(amt)}",
                "date": "11.08.2026, 12:00:00",
                "amount": amt,
                "type": "Debit",
                "bank": "СБП",
                "title": "Smoke",
                "phone": "+79001112233",
            })
            text = ""
            if path and os.path.isfile(path):
                doc = fitz.open(path)
                text = (doc[0].get_text() or "").replace("\xa0", " ")
                doc.close()
            formatted = f"{int(amt):,}".replace(",", " ")
            has_amt = formatted in text or str(int(amt)) in re.sub(r"\D+", "", text)
            has_20000 = ("20 000" in text) or ("20000" in re.sub(r"\s+", "", text))
            # чужая сумма из другой тестовой генерации
            other = "5678" if int(amt) == 1234 else "1234"
            has_other = other in re.sub(r"\D+", "", text) and str(int(amt)) not in re.sub(r"\D+", "", text)
            amount_ok[str(int(amt))] = bool(path) and has_amt and not has_20000 and not has_other
        dbg("H3", "smoke.receipt", "generate amounts", {
            "tpl_found": tpl_ok,
            "tpl_path": tpl,
            "amount_ok": amount_ok,
            "all_ok": tpl_ok and all(amount_ok.values()),
            "raised": False,
        })
    except Exception as e:
        dbg("H3", "smoke.receipt", "generate raised", {"error_type": type(e).__name__, "error": str(e)[:200]})

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

    # H6 app month filter + fake_history repair
    try:
        import transfer
        import history as hist
        april_ok = hist.app_include_all_operations() or hist.is_current_month("17.04.2026, 02:08:36")
        pending = hist.pending_fake_history_ops(month_restrict=not hist.app_include_all_operations())
        dbg("H6", "smoke.app_filter", "month filter", {
            "show_all": hist.app_include_all_operations(),
            "april_passes": april_ok,
            "fake_pending_count": len(pending),
        })
        dbg("H6", "smoke.fake_repair", "fake_history on disk", {
            "fake_history_len": len(transfer.transfer_data.get("fake_history") or []),
            "transaction_id": transfer.transfer_data.get("transaction_id"),
        })
    except Exception as e:
        dbg("H6", "smoke.app_filter", "failed", {"error_type": type(e).__name__})

    print("smoke done -> debug-f24997.log")


if __name__ == "__main__":
    main()
