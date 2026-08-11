"""Regression smoke after perf + UI fixes (v26)."""
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
        compact = s.replace(" ", "")
        if "observe(r,{childList:true,subtree:true,characterData:true})" in compact:
            fails.append("home MO still uses characterData")
    if "setInterval(patchDetailDom, 1100)" in s or "setTimeout(patchDetailDom, 42)" in s:
        fails.append("old aggressive detail timers still present")
    if "setInterval(tick, 900)" in s:
        fails.append("old 900ms fin interval still present")
    if "setTimeout(run, 180)" in s:
        fails.append("detail debounce still 180ms (want >=300)")
    if "manual-payment-history-styles-v26" not in s:
        fails.append("missing one-shot style marker v26")
    if "__manualOpsBrowserInjectorV26" not in s:
        fails.append("missing V26 guard")

    # home_mybank first, no bank aggregate fallback
    fn = s[s.find("finTotalsForMybankHomeFromOperationsApi"): s.find("finTotalsForMybankHomeFromOperationsApi") + 900]
    if "home_mybank_income" not in fn:
        fails.append("home_mybank preference missing")
    if "st.income != null && st.expense != null" in fn:
        fails.append("home still falls back to stats.income")

    # Home tile white + deltas
    if "data-manual-home-allops-tile" not in s or "#F6F7F8" not in s:
        fails.append("home tile white styles missing")
    if "font: 700 17px" not in s or "font: 600 15px" not in s:
        fails.append("home typography deltas 17/15/600 missing")

    # Receipt: overlay sheet, not assign to /receipt_viewer as primary
    if "openManualPdfDocumentSheet" not in s or "Документ по операции" not in s:
        fails.append("native-like PDF sheet overlay missing")
    if "payment_receipt_pdf" not in s:
        fails.append("raw pdf url for iframe missing")

    # Detail gate narrower + native early-return
    if "не любые покупки" not in s:
        fails.append("isManualLikeDetailOp comment/narrowing missing")
    if "hasNativeElevatedDetailChrome" not in s:
        fails.append("hasNativeElevatedDetailChrome missing")

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
