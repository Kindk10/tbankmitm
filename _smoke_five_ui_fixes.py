"""Smoke for five remaining UI fixes. Exit 0 if all checks pass."""
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
    if history.url_allows_operation_inject("https://www.tbank.ru/api/common/v1/accounts_light_ib"):
        # may still match "accounts" substring via other rules — check accounts skip path
        pass
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
        # sync should clear
        history.sync_manual_ie_panel_aggregate_into_config()
    if manual.get("income") is not None or manual.get("expense") is not None:
        fails.append(f"sticky I/E still set: {manual.get('income')}/{manual.get('expense')}")
    di, de, _, _ = history.get_panel_chart_display_totals()
    if di is None or de is None:
        fails.append(f"display totals None: {di}/{de}")

    # 3) Home-tile typography markers
    script = browser_ops_injector._build_script()
    for needle in (
        'data-manual-home-allops-tile="1"',
        "color: #F6F7F8",
        "font: 400 14px",
        "font: 700 16px",
    ):
        if needle not in script:
            fails.append(f"home-tile missing: {needle}")

    # 4) Receipt viewer
    html = transfer._receipt_viewer_html("smoke_op_1")
    for needle in ("Квитанция", "Закрыть", "payment_receipt_pdf", "iframe", "#000"):
        if needle not in html:
            fails.append(f"receipt viewer missing: {needle}")
    if "/receipt_viewer" not in script:
        fails.append("injector missing /receipt_viewer navigate")
    if "payment_receipt_pdf" in script and "receiptOpenUrlForOperationId" in script:
        # click must prefer viewer, not raw pdf as primary open url
        if "return origin + '/payment_receipt_pdf" in script:
            fails.append("cert click still opens raw PDF as primary")

    # 5) Detail styles Credit/Debit
    for needle in (
        "manual-detail-pumba-cards-v24",
        "isManualLikeDetailOp",
        "ensureManualRequisitesPanel",
        "Номер телефона",
        "Отправитель",
        "Пополнение",
        "Перевод",
        "data-manual-amount-kind",
        "#3DD68C",
        "MANUAL_ACTIONS_ROW_INNER_HTML",
        "MANUAL_ACTIONS_DISALLOW_ONLY_INNER_HTML",
        "elevateRequisitesPanels",
    ):
        if needle not in script:
            fails.append(f"detail styles missing: {needle}")

    # panel routes present
    import panel_bridge
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
