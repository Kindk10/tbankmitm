"""Smoke checks for transfer detail parity (API + injector assets)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import history
import operation_detail
import browser_ops_injector as inj


def main() -> None:
    # 1) resolve fake UNIFIED id
    oid = "UNIFIED_1776358055809"
    assert history.op_id_in_fake_history_files(oid), "fake id missing from last_transfer"
    rec = history.resolve_overlay_record_by_id(oid)
    assert rec, "resolve_overlay_record_by_id failed"
    assert rec.get("type") == "Debit"
    assert float(rec.get("amount") or 0) > 0
    assert (rec.get("requisite_phone") or rec.get("phone")), "phone missing"
    print("OK resolve fake:", oid, rec.get("title"), rec.get("amount"), rec.get("phone"))

    # 2) rewritable id helpers
    assert operation_detail._is_rewritable_detail_id(oid)
    assert operation_detail._resolve_detail_overlay(oid)

    # 3) overlay flags for debit
    template = {
        "id": "ref",
        "type": "Credit",
        "amount": {"value": 1, "currency": {"code": 643, "name": "RUB", "strCode": "643"}},
        "description": "x",
        "isTemplatable": False,
    }
    merged = history.overlay_manual_on_template(template, oid, rec, clamp_to_wall_ms=False)
    assert merged.get("isTemplatable") is True, merged.get("isTemplatable")
    assert merged.get("id") == oid
    assert merged.get("type") == "Debit"
    print("OK overlay isTemplatable=True for debit")

    # 4) sidecar assets
    actions = inj._action_buttons_row_inner_html()
    assert "operation-action-templatable" in actions
    assert "aboVRe6CK" in actions or "ab9a57KC0" in actions
    assert actions.count("operation-action-") >= 5
    header = inj._detail_header_inner_html()
    assert "mobile-pumba-detail-operation" in header
    assert "tui/block-details" in header
    assert "Переводы" in header
    disallow = inj._action_buttons_disallow_only_inner_html()
    assert "operation-action-disallow" in disallow
    print("OK sidecars: actions", len(actions), "header", len(header), "disallow", len(disallow))

    # 5) detail ops payload includes amount for fake
    snap = inj._detail_ops_by_id_payload()
    if oid in snap:
        assert "amount" in snap[oid]
        print("OK DETAIL_OPS amount for", oid, snap[oid]["amount"])
    else:
        print("WARN: fake id not in month-filtered DETAIL_OPS (ok if month_only)")

    # 6) script builds and contains new helpers
    script = inj._build_script()
    assert "ensureDetailHeaderMolecule" in script
    assert "MANUAL_DETAIL_HEADER_INNER_HTML" in script
    assert "data-manual-actions-wrapper" in script
    assert "manual-detail-pumba-cards-v25" in script
    assert "data-manual-detail-active" in script
    print("OK injector script length", len(script))

    # 7) m_* still resolves when present
    history.ensure_manual_operations_fresh()
    mids = list(history.manual_operations.keys())[:1]
    if mids:
        m = history.resolve_overlay_record_by_id(mids[0])
        assert m
        assert operation_detail._is_rewritable_detail_id(mids[0])
        print("OK manual resolve", mids[0])
    else:
        print("WARN: no manual_operations — skip m_* check")

    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
