"""Smoke for UI fixes v31. Exit 0 if all checks pass."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import browser_ops_injector
import history
import transfer


def main() -> int:
    fails: list[str] = []

    if not hasattr(history, "_row_looks_like_account_product"):
        fails.append("missing _row_looks_like_account_product")

    manual = __import__("controller").config.setdefault("manual", {})
    history.sync_manual_ie_panel_aggregate_into_config()
    if manual.get("income") is not None or manual.get("expense") is not None:
        fails.append(f"sticky I/E still set: {manual.get('income')}/{manual.get('expense')}")

    di, de, _, _ = history.get_panel_chart_display_totals()
    if di is None or de is None:
        fails.append(f"display totals None: {di}/{de}")

    script = browser_ops_injector._build_script()
    for needle in (
        "__manualOpsBrowserInjectorV31",
        "v31-exact-fast-stable",
        "manual-payment-history-styles-v31",
        "font: 400 14px",
        "font: 600 15px",
        "font: 700 16px",
        "openManualPdfDocumentSheet",
        "Документ по операции",
        "hasNativeElevatedDetailChrome",
        "st.home_mybank_income != null && st.home_mybank_expense != null",
        "lifecycle observer",
    ):
        if needle not in script:
            fails.append(f"missing: {needle}")
    if "abl2_v29I" not in browser_ops_injector._ACCOUNT_CARD_MANUAL_INNER_HTML:
        fails.append("exact CLEAN account card template not loaded")
    if "Пополнение" not in browser_ops_injector._ACCOUNT_CARD_CREDIT_INNER_HTML:
        fails.append("exact CLEAN incoming account template not loaded")
    if "abQ5r0-1o" not in browser_ops_injector._BANK_DETAILS_MANUAL_INNER_HTML:
        fails.append("exact CLEAN requisites template not loaded")
    if "Отправитель" not in browser_ops_injector._BANK_DETAILS_CREDIT_INNER_HTML:
        fails.append("exact CLEAN incoming requisites template not loaded")

    if "window.location.assign(url)" in script[script.find("bindManualCertReceiptClick"): script.find("bindManualCertReceiptClick") + 800]:
        fails.append("cert still uses location.assign")

    html = transfer._receipt_viewer_html("smoke_op_1")
    if "payment_receipt_pdf" not in html:
        fails.append("receipt viewer missing pdf")

    if fails:
        print("FAIL:")
        for f in fails:
            print(" -", f)
        return 1
    print("OK v31 smoke")
    print(f"  totals income={di} expense={de} script_len={len(script)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
