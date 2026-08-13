from mitmproxy import http
import json
import sys
import os

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

def _effective_balance(base: float) -> float:
    try:
        import history as history_mod

        adj = history_mod.compute_manual_balance_adjustment()
        return round(float(base) + float(adj), 2)
    except Exception:
        return float(base)

def get_config():
    return controller.config["balance"]


def _strip_card_previews(node: dict) -> None:
    """На главной mybank оставляем только одну основную карту-превью без дублей."""
    if not isinstance(node, dict):
        return
    for key in ("cards", "cardList", "previewCards"):
        if key in node and isinstance(node.get(key), list):
            items = [x for x in node[key] if isinstance(x, dict)]
            node[key] = items[:1]
    for key in ("cardsCount", "cardCount"):
        if key in node:
            count = 0
            for list_key in ("cards", "cardList", "previewCards"):
                if isinstance(node.get(list_key), list) and node[list_key]:
                    count = len(node[list_key])
                    break
            node[key] = count


def _patch_first_balance_like_node(node, balance_value: float, collect_sum, card_number: str) -> bool:
    """Фолбэк для новых ответов mybank: патчим первый account/card-like блок с балансом."""
    if isinstance(node, dict):
        has_balance_field = False

        for key in ("availableBalance", "moneyAmount"):
            block = node.get(key)
            if isinstance(block, dict) and "value" in block:
                block["value"] = balance_value
                has_balance_field = True

        if has_balance_field:
            if "collectSum" in node:
                node["collectSum"] = collect_sum
            _strip_card_previews(node)
            cards = node.get("cards")
            if isinstance(cards, list):
                for card in cards:
                    if not isinstance(card, dict):
                        continue
                    if "value" in card:
                        card["value"] = card_number
                    for key in ("availableBalance", "moneyAmount"):
                        block = card.get(key)
                        if isinstance(block, dict) and "value" in block:
                            block["value"] = balance_value
            return True

        for value in node.values():
            if _patch_first_balance_like_node(value, balance_value, collect_sum, card_number):
                return True
        return False

    if isinstance(node, list):
        for item in node:
            if _patch_first_balance_like_node(item, balance_value, collect_sum, card_number):
                return True
    return False

def response(flow: http.HTTPFlow) -> None:
    url = flow.request.pretty_url

    if not is_bank_flow(flow):
        return
    if not flow.response:
        return
    if not is_jsonish_response(flow):
        return
    ensure_response_decoded(flow)
    if not flow.response.text:
        if bank_debug_enabled():
            print(f"[balance] пустой ответ: {url[:120]}")
        return

    if url_prohibit_proxy_json_mutation(url):
        return

    if flow_statements_spravki_context(flow):
        return

    text = flow.response.text
    is_accounts = "moneyAmount" in text and "cards" in text
    is_card_details = "account_cards" in url
    is_accounts_light = "accounts_light_ib" in url
    has_balance_node = "availableBalance" in text or "moneyAmount" in text
    if not (is_accounts or is_card_details or is_accounts_light or has_balance_node):
        return

    try:
        balance_cfg = get_config()
        TEST_DATA = {
            "new_balance": _effective_balance(balance_cfg["new_balance"]),
            "new_card_number": balance_cfg["new_card_number"],
            "new_collect_sum": balance_cfg["new_collect_sum"],
        }
    except Exception:
        return

    try:
        data = json.loads(text)
    except Exception:
        return

    modified = False

    # ===== ОСНОВНОЙ СПИСОК СЧЕТОВ =====
    # Только первый расчётный счёт с картами — иначе все продукты получали один номер/баланс и плодились «лишние» карты в UI.
    if is_accounts and isinstance(data, dict) and isinstance(data.get("payload"), list):
        for account in data["payload"]:
            if not isinstance(account, dict):
                continue
            if "cards" in account and account.get("accountType") == "Current":
                if "moneyAmount" in account and "value" in account["moneyAmount"]:
                    account["moneyAmount"]["value"] = TEST_DATA["new_balance"]
                if "collectSum" in account:
                    account["collectSum"] = TEST_DATA["new_collect_sum"]
                _strip_card_previews(account)
                modified = True
                break
    
    # ===== ДЕТАЛИ КАРТЫ =====
    if is_card_details and isinstance(data, dict) and isinstance(data.get("payload"), list) and data["payload"]:
        card = data["payload"][0]
        if isinstance(card, dict) and "availableBalance" in card:
            ab = card["availableBalance"]
            if isinstance(ab, dict) and "value" in ab:
                ab["value"] = TEST_DATA["new_balance"]
        modified = True
    
    # ===== ЛЕГКИЙ БАЛАНС (главная строка на mybank) =====
    if is_accounts_light and isinstance(data, dict) and isinstance(data.get("payload"), list) and data["payload"]:
        # На главной оставляем одну карточку продукта — без «лишних» дублей в ленте mybank
        pl = data["payload"]
        first = pl[0]
        if len(pl) > 1:
            data["payload"] = [first]
        if isinstance(first, dict) and "availableBalance" in first:
            bal = first["availableBalance"]
            if isinstance(bal, dict) and "value" in bal:
                bal["value"] = TEST_DATA["new_balance"]
        _strip_card_previews(first)
        modified = True

    # ===== ФОЛБЭК ДЛЯ НОВЫХ JSON-ОТВЕТОВ mybank =====
    if has_balance_node and _patch_first_balance_like_node(
        data,
        TEST_DATA["new_balance"],
        TEST_DATA["new_collect_sum"],
        TEST_DATA["new_card_number"],
    ):
        modified = True

    if modified:
        flow.response.text = json.dumps(data, ensure_ascii=False)

print("[+] balance.py загружен (динамический конфиг)")