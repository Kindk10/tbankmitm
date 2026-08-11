"""Regression smoke after perf + UI fixes."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import browser_ops_injector as inj
import history


def main() -> int:
    fails = []
    s = inj._build_script()

    # Perf markers
    if "characterData: true" in s and "__homeFinReassertMo" in s:
        # home observer must NOT use characterData
        if "observe(r, { childList: true, subtree: true, characterData: true })" in s.replace(" ", ""):
            fails.append("home MO still uses characterData")
    if "setInterval(patchDetailDom, 1100)" in s or "setTimeout(patchDetailDom, 42)" in s:
        fails.append("old aggressive detail timers still present")
    if "setInterval(tick, 900)" in s:
        fails.append("old 900ms fin interval still present")
    if 'span, div' in s and "titleSel" in s:
        # check narrowed selector
        if '[data-qa-type="title"], span, div' in s:
            fails.append("home still scans all span,div")
    if "manual-payment-history-styles-v3" not in s:
        fails.append("missing one-shot style marker v3")
    if "home_mybank_income" not in s or "НЕ bank+manual" not in s and "не bank+manual" not in s.lower():
        # prefer home_mybank first
        idx_home = s.find("st.home_mybank_income")
        idx_inc = s.find("st.income != null && st.expense != null")
        if idx_home < 0 or (idx_inc >= 0 and idx_home > idx_inc and "home_mybank" in s[idx_inc:idx_inc+400]):
            # verify order in finTotals function
            fn = s[s.find("finTotalsForMybankHomeFromOperationsApi"):s.find("finTotalsForMybankHomeFromOperationsApi")+900]
            if fn.find("home_mybank_income") > fn.find("st.income != null"):
                fails.append("home still prefers stats.income before home_mybank")

    # Home tile white
    if "data-manual-home-allops-tile" not in s or "#F6F7F8" not in s:
        fails.append("home tile white styles missing")
    if 'color: rgba(0,0,0,0.55)' in s and 'mobile-pumba-payment-history"] [data-manual-ph-amt]' in s:
        fails.append("global gray ph-amt still present")

    # Receipt
    if "/receipt_viewer" not in s:
        fails.append("receipt viewer navigate missing")
    if "payment_receipt_pdf" not in s:
        fails.append("raw pdf still needed for iframe ok")

    # Detail gate narrower
    if "любые покупки с телефоном" not in s and "не любые покупки" not in s:
        fails.append("isManualLikeDetailOp comment/narrowing missing")

    # History plaques
    if not hasattr(history, "_row_looks_like_account_product"):
        fails.append("missing account product detector")
    src = open(os.path.join(ROOT, "history.py"), encoding="utf-8").read()
    if "плоский список похож на счета" not in src:
        fails.append("flat account list skip missing")
    if "operation_row_kind(fake_item)" not in src:
        fails.append("fake inject still unguarded")

    # sticky I/E
    history.sync_manual_ie_panel_aggregate_into_config()
    m = __import__("controller").config.get("manual") or {}
    if m.get("income") is not None or m.get("expense") is not None:
        fails.append(f"sticky I/E: {m.get('income')}/{m.get('expense')}")

    di, de, _, _ = history.get_panel_chart_display_totals()
    print(f"totals income={di} expense={de} script_len={len(s)}")

    if fails:
        print("FAIL:")
        for f in fails:
            print(" -", f)
        return 1
    print("OK regression smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
