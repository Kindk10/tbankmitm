"""Smoke for five remaining UI fixes (v26). Exit 0 if all checks pass."""
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

    # 1) Home plaques: light_ib not in inject allowlists; accounts URL blocked
    allow = getattr(history, "_BROWSER_TBANK_INJECT_PATH_OK", ()) or ()
    allow_l = " ".join(str(x).lower() for x in allow)
    if "light_ib" in allow_l or "lightib" in allow_l:
        fails.append("light_ib still in _BROWSER_TBANK_INJECT_PATH_OK")
    if not hasattr(history, "_row_looks_like_account_product"):
        fails.append("missing _row_looks_like_account_product")
    fake_acc = {
        "accountType": "Current",
        "cards": [],
        "availableBalance": {"value": 1},
        "name": "Black",
    }
    if not history._row_looks_like_account_product(fake_acc):
        fails.append("account product row not detected")
    fake_op = {"id": "x", "type": "Debit", "operationTime": {"milliseconds": 1}, "amount": {"value": 1}}
    if history._row_looks_like_account_product(fake_op):
        fails.append("operation row misclassified as account")

    # 2) Income/expense: sticky cleared; sync recomputes
    manual = __import__("controller").config.setdefault("manual", {})
    if manual.get("income") is not None or manual.get("expense") is not None:
        history.sync_manual_ie_panel_aggregate_into_config()
    if manual.get("income") is not None or manual.get("expense") is not None:
        fails.append(f"sticky I/E still set: {manual.get('income')}/{manual.get('expense')}")
    di, de, _, _ = history.get_panel_chart_display_totals()
    if di is None or de is None:
        fails.append(f"display totals None: {di}/{de}")

    # 3) Home-tile typography markers (v26 deltas)
    script = browser_ops_injector._build_script()
    for needle in (
        'data-manual-home-allops-tile="1"',
        "color: #F6F7F8",
        "font: 600 15px",
        "font: 700 17px",
        "margin-top: 8px",
        "manual-payment-history-styles-v26",
        "__manualOpsBrowserInjectorV26",
        "v26-fix-native-detail-receipt",
    ):
        if needle not in script:
            fails.append(f"home-tile/v26 missing: {needle}")

    # 4) Receipt: in-page sheet «Документ по операции», not location.assign to /receipt_viewer
    html = transfer._receipt_viewer_html("smoke_op_1")
    for needle in ("Квитанция", "Закрыть", "payment_receipt_pdf", "iframe"):
        if needle not in html:
            fails.append(f"receipt viewer html missing: {needle}")
    if "openManualPdfDocumentSheet" not in script:
        fails.append("injector missing openManualPdfDocumentSheet")
    if "Документ по операции" not in script:
        fails.append("injector missing Документ по операции overlay title")
    if "window.location.assign(url)" in script and "receipt_viewer" in script[script.find("bindManualCertReceiptClick"):script.find("bindManualCertReceiptClick")+1200]:
        fails.append("cert click still location.assign to viewer as primary UX")
    if "hasNativeElevatedDetailChrome" not in script:
        fails.append("missing hasNativeElevatedDetailChrome")

    # 5) Detail styles Credit/Debit + native preserve
    for needle in (
        "manual-detail-pumba-cards-v26",
        "isManualLikeDetailOp",
        "не любые покупки",
        "hasNativeElevatedDetailChrome",
        "ensureManualRequisitesPanel",
        "Номер телефона",
        "Отправитель",
        "Пополнение",
        "Перевод",
        "data-manual-amount-kind",
        "#3DD68C",
        "MANUAL_ACTIONS_ROW_INNER_HTML",
        "elevateRequisitesPanels",
    ):
        if needle not in script:
            fails.append(f"detail styles missing: {needle}")

    # home totals: no bank aggregate fallback
    fn = script[script.find("finTotalsForMybankHomeFromOperationsApi"): script.find("finTotalsForMybankHomeFromOperationsApi") + 900]
    if "st.income != null && st.expense != null" in fn:
        fails.append("home totals still fall back to stats.income/expense bank aggregate")

    src = open(os.path.join(ROOT, "panel_bridge.py"), encoding="utf-8").read()
    if 'path_only == "/receipt_viewer"' not in src:
        fails.append("panel_bridge missing /receipt_viewer")

    if fails:
        print("FAIL:")
        for f in fails:
            print(" -", f)
        return 1
    print("OK five UI fixes smoke")
    print(f"  totals income={di} expense={de}")
    print(f"  script_len={len(script)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
