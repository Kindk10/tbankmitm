"""
Подмена JSON для экрана операции, чека/справки и вложенных структур по id ручных операций (m_...).
Загружать в mitm ПОСЛЕ history.py.
"""
from mitmproxy import http
import json
import copy
import re
import sys
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import history
import controller
from bank_filter import (
    is_bank_flow,
    ensure_response_decoded,
    bank_debug_enabled,
    is_jsonish_response,
    flow_statements_spravki_context,
    url_prohibit_proxy_json_mutation,
)

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
)
_MANUAL_RE = re.compile(r"\bm_[a-zA-Z0-9_]+\b")
_UNIFIED_RE = re.compile(r"\bUNIFIED_\d+\b")


def _is_rewritable_detail_id(oid: str) -> bool:
    if not oid or not isinstance(oid, str):
        return False
    if oid in history.manual_operations:
        return True
    if oid.startswith("UNIFIED_"):
        return True
    try:
        if history.op_id_in_fake_history_files(oid):
            return True
    except Exception:
        pass
    return False


def _resolve_detail_overlay(oid: str) -> dict | None:
    try:
        return history.resolve_overlay_record_by_id(oid)
    except Exception:
        return None

def _format_phone_ru(phone: str) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) == 11 and digits[0] in ("7", "8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    if len(digits) != 11 or not digits.startswith("7"):
        return str(phone or "").strip()
    return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"


def _extract_ids_from_url(url: str) -> list:
    out = []
    out.extend(m.group(0).lower() for m in _UUID_RE.finditer(url or ""))
    out.extend(m.group(0) for m in _MANUAL_RE.finditer(url or ""))
    out.extend(m.group(0) for m in _UNIFIED_RE.finditer(url or ""))
    try:
        q = parse_qs(urlparse(url).query)
        for key in ("operationId", "operation_id", "id", "operationID", "parentOperationId", "rootOperationId"):
            for val in q.get(key, []):
                if val and (val.startswith("m_") or val.startswith("UNIFIED_") or len(val) > 10):
                    out.append(val.strip())
    except Exception:
        pass
    return list(dict.fromkeys(out))


def _collect_ids_from_json(obj, out: set) -> None:
    if isinstance(obj, dict):
        for k in ("id", "operationId", "parentOperationId", "rootOperationId"):
            v = obj.get(k)
            if isinstance(v, str) and (
                v.startswith("m_") or v.startswith("UNIFIED_") or _UUID_RE.fullmatch(v)
            ):
                out.add(v)
        for v in obj.values():
            _collect_ids_from_json(v, out)
    elif isinstance(obj, list):
        for x in obj:
            _collect_ids_from_json(x, out)


def _extract_ids_from_flow(flow: http.HTTPFlow) -> set:
    s = set(_extract_ids_from_url(flow.request.pretty_url or ""))
    try:
        body = flow.request.text or ""
        if body.strip().startswith("{"):
            _collect_ids_from_json(json.loads(body), s)
    except Exception:
        pass
    return s


def _pick_reference_operation() -> tuple[str | None, int | None]:
    import time as _time

    cache = history.operations_cache or {}
    cache_len = len(cache)
    now = _time.monotonic()
    cached = getattr(_pick_reference_operation, "_cache", None)
    if (
        isinstance(cached, tuple)
        and len(cached) == 4
        and cached[0] == cache_len
        and (now - cached[1]) < 8.0
    ):
        return cached[2], cached[3]

    best_id = None
    best_ts = -1
    best_transfer_id = None
    best_transfer_ts = -1
    for op_id, op in cache.items():
        if not op_id or str(op_id).startswith("m_") or str(op_id).startswith("UNIFIED_"):
            continue
        if not isinstance(op, dict):
            continue
        ts = history.date_str_to_millis(op.get("date", ""))
        if isinstance(op.get("operationTime"), dict):
            try:
                ms = int(op["operationTime"].get("milliseconds") or 0)
                if ms > 0:
                    ts = ms
            except Exception:
                pass
        if ts > best_ts:
            best_ts = ts
            best_id = str(op_id)
        group = str(op.get("group") or "").upper()
        subgroup = op.get("subgroup") if isinstance(op.get("subgroup"), dict) else {}
        sc = op.get("spendingCategory") if isinstance(op.get("spendingCategory"), dict) else {}
        is_transfer = (
            group == "TRANSFER"
            or str(subgroup.get("name") or "").lower().find("перевод") >= 0
            or str(sc.get("name") or "").lower() == "переводы"
        )
        if is_transfer and ts > best_transfer_ts:
            best_transfer_ts = ts
            best_transfer_id = str(op_id)
    if best_transfer_id:
        result = (best_transfer_id, (best_transfer_ts if best_transfer_ts > 0 else None))
    else:
        result = (best_id, (best_ts if best_ts > 0 else None))
    _pick_reference_operation._cache = (cache_len, now, result[0], result[1])
    return result


def _replace_id_refs_in_json(obj, target_id: str, replacement_id: str):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ("id", "operationId", "parentOperationId", "rootOperationId") and isinstance(v, str) and v == target_id:
                out[k] = replacement_id
            else:
                out[k] = _replace_id_refs_in_json(v, target_id, replacement_id)
        return out
    if isinstance(obj, list):
        return [_replace_id_refs_in_json(x, target_id, replacement_id) for x in obj]
    return obj


def _replace_time_refs_in_json(obj, replacement_time: int):
    time_keys = {"operationTime", "time", "timestamp", "operationTimestamp"}
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "operationTime" and isinstance(v, dict):
                nv = dict(v)
                nv["milliseconds"] = replacement_time
                out[k] = nv
            elif k in time_keys and isinstance(v, (int, float)):
                out[k] = replacement_time
            else:
                out[k] = _replace_time_refs_in_json(v, replacement_time)
        return out
    if isinstance(obj, list):
        return [_replace_time_refs_in_json(x, replacement_time) for x in obj]
    return obj


def _url_suggests_detail_or_receipt(u: str) -> bool:
    u = (u or "").lower()
    if "/mybank/statements" in u or "mybank%2fstatements" in u:
        return False
    if any(b in u for b in ("histogram", "category_list", "graphql", "web-gateway", "log/collect")):
        return False
    hints = (
        "receipt",
        "fiscal",
        "ofd",
        "operationby",
        "operation/info",
        "/operation/",
        "operation_detail",
        "getoperation",
        "money-session",
        "slip",
        "cheque",
        "check/",
        "invoice",
        "sprav",
        "reference",
        "certificate",
        # не "statement" — совпадает с "statements" (Справки / API справок)
        "/statement/",
        "statement?",
        "=statement",
        "&statement",
        "movement",
        "registry",
    )
    return any(h in u for h in hints)


def request(flow: http.HTTPFlow) -> None:
    history.ensure_manual_operations_fresh()
    if not is_bank_flow(flow):
        return
    _url0 = flow.request.pretty_url or ""
    if url_prohibit_proxy_json_mutation(_url0):
        return
    if flow_statements_spravki_context(flow):
        return
    ids_in_flow = _extract_ids_from_flow(flow)
    target_ids = [mid for mid in ids_in_flow if _is_rewritable_detail_id(mid) and _resolve_detail_overlay(mid)]
    if not target_ids:
        return
    replacement_id, replacement_time = _pick_reference_operation()
    if not replacement_id:
        return

    target_id = target_ids[0]
    try:
        flow.metadata["manual_detail_id"] = target_id
        flow.metadata["replacement_operation_id"] = replacement_id
        flow.metadata["replacement_time_ms"] = replacement_time
    except Exception:
        pass

    try:
        parsed = urlparse(flow.request.url)
        q = parse_qs(parsed.query, keep_blank_values=True)
        changed = False
        for key in ("operationId", "operation_id", "id", "operationID", "parentOperationId", "rootOperationId"):
            vals = q.get(key)
            if not vals:
                continue
            q[key] = [replacement_id if v == target_id else v for v in vals]
            changed = True
        if replacement_time is not None:
            for key in ("operationTime", "time", "timestamp", "operationTimestamp"):
                if key in q:
                    q[key] = [str(int(replacement_time))]
                    changed = True
        if changed:
            flow.request.url = urlunparse(parsed._replace(query=urlencode(q, doseq=True)))
        elif target_id in flow.request.url:
            flow.request.url = flow.request.url.replace(target_id, replacement_id)
    except Exception:
        pass

    try:
        body = flow.request.get_text(strict=False) or ""
        stripped = body.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            patched = _replace_id_refs_in_json(json.loads(body), target_id, replacement_id)
            if replacement_time is not None:
                patched = _replace_time_refs_in_json(patched, int(replacement_time))
            flow.request.set_text(json.dumps(patched, ensure_ascii=False))
    except Exception:
        pass


def _patch_receipt_like_node(obj: dict, man: dict) -> bool:
    """Узел со ссылкой на операцию (operationId) без полного id — подставляем суммы/тексты."""
    changed = False
    amt = abs(float(man.get("amount") or 0))
    typ = man.get("type") or "Debit"
    primary = (man.get("title") or man.get("phone") or man.get("description") or "").strip() or (
        "Операция" if typ == "Debit" else "Поступление"
    )
    sender_name = (man.get("requisite_sender_name") or man.get("sender_name") or "").strip() or primary
    second = (man.get("subtitle") or "").strip()
    bank = (man.get("bank") or "").strip()
    phone = (man.get("requisite_phone") or man.get("phone") or "").strip()
    formatted_phone = _format_phone_ru(phone)

    if isinstance(obj.get("amount"), dict):
        try:
            from history import _normalize_money_dict
            obj["amount"] = _normalize_money_dict(obj["amount"], amt)
        except Exception:
            obj["amount"]["value"] = amt
            obj["amount"]["currency"] = {"code": 643, "name": "RUB", "strCode": "643"}
        changed = True
    elif "amount" in obj and not isinstance(obj.get("amount"), dict):
        obj["amount"] = {"value": amt, "currency": {"code": 643, "name": "RUB", "strCode": "643"}}
        changed = True

    if "operationAmount" in obj and isinstance(obj["operationAmount"], dict):
        try:
            from history import _normalize_money_dict
            obj["operationAmount"] = _normalize_money_dict(obj["operationAmount"], amt)
        except Exception:
            obj["operationAmount"]["value"] = amt
        changed = True
    for _ak in ("signedAmount", "accountAmount", "moneyAmount"):
        if _ak in obj and isinstance(obj.get(_ak), dict):
            try:
                from history import _normalize_money_dict
                _sv = -amt if typ == "Debit" and _ak == "signedAmount" else amt
                obj[_ak] = _normalize_money_dict(obj[_ak], _sv)
                changed = True
            except Exception:
                pass

    for key in ("description", "title", "name", "purpose", "merchantName", "comment", "subtitle"):
        if key in obj:
            obj[key] = primary if key not in ("comment", "subtitle") else (second or primary)
            changed = True

    if "formattedDescription" in obj:
        obj["formattedDescription"] = second or primary
        changed = True

    if bank and isinstance(obj.get("merchant"), dict):
        obj["merchant"]["name"] = bank
        changed = True
    elif bank and "merchant" in obj:
        obj["merchant"] = {"name": bank}
        changed = True

    # Пропагация brand.name и brand.logo (название банка в шапке)
    brand_logo = man.get("logo") or man.get("bank_preset_logo") or ""
    if bank and isinstance(obj.get("brand"), dict):
        obj["brand"]["name"] = bank
        if brand_logo:
            obj["brand"]["logo"] = brand_logo
            obj["brand"]["fileLink"] = brand_logo
        changed = True
    elif bank and "brand" in obj:
        obj["brand"] = {"name": bank}
        if brand_logo:
            obj["brand"]["logo"] = brand_logo
            obj["brand"]["fileLink"] = brand_logo
        changed = True

    # Пропагация логотипа в logo/logoUrl/image/icon поля
    if brand_logo:
        for logo_key in ("logo", "logoUrl", "image", "icon", "picture", "avatar", "favicon"):
            if logo_key in obj:
                obj[logo_key] = brand_logo
                changed = True
        # Также в counterparty.logo
        if isinstance(obj.get("counterparty"), dict):
            for logo_key in ("logo", "logoUrl", "image", "icon", "picture", "avatar", "favicon"):
                if logo_key in obj["counterparty"]:
                    obj["counterparty"][logo_key] = brand_logo
                    changed = True

    # Добавляем phone/pointer для detail-экрана
    phone = (man.get("requisite_phone") or man.get("phone") or "").strip()
    card_number = (man.get("card_number") or "").strip()
    
    for key in ("phone", "phoneNumber", "recipientPhone", "pointer"):
        if key in obj and phone:
            obj[key] = formatted_phone or phone
            changed = True

    # Добавляем cardNumber/cardNumber поля
    if card_number:
        for key in ("cardNumber", "cardNumber", "pan", "card_number"):
            if key in obj:
                obj[key] = card_number
                changed = True

    # Добавляем recipient/counterpartyName
    for key in ("recipient", "recipientName", "counterpartyName", "fullName"):
        if key in obj and primary:
            obj[key] = primary
            changed = True

    sender_value = (formatted_phone or phone) if typ == "Debit" else sender_name
    for key in ("sender", "senderName", "senderDetails", "payerName", "sourceName", "displayName"):
        if key in obj and sender_value:
            obj[key] = sender_value
            changed = True

    # Патчим counterparty объект целиком
    if isinstance(obj.get("counterparty"), dict):
        cp = obj["counterparty"]
        if bank and not cp.get("name"):
            cp["name"] = bank
            changed = True
        elif primary and not cp.get("name"):
            cp["name"] = primary
            changed = True
        if brand_logo:
            for logo_key in ("logo", "logoUrl", "image", "icon", "picture", "avatar", "favicon"):
                if logo_key in cp:
                    cp[logo_key] = brand_logo
                    changed = True

    if typ in ("Credit", "Debit"):
        if "type" in obj:
            obj["type"] = typ
            changed = True
        if "operationType" in obj:
            obj["operationType"] = typ
            changed = True

    ms = history.parse_bank_date_str_to_ms(man.get("date", ""))
    if ms is None:
        ms = history.date_str_to_millis(man.get("date", ""))
    history._sync_all_operation_times(obj, int(ms))

    history._apply_bank_brand_preset(obj, man)
    history._propagate_merchant_logo(obj)
    return changed


def _patch_tree(obj, overlay_ids: set) -> bool:
    changed = False

    def visit(node):
        nonlocal changed
        if isinstance(node, dict):
            oid = node.get("id")
            if isinstance(oid, str) and oid in overlay_ids:
                man = _resolve_detail_overlay(oid)
                if man:
                    merged = history.overlay_manual_on_template(
                        copy.deepcopy(node),
                        oid,
                        man,
                        min_time_ms=None,
                        clamp_to_wall_ms=False,
                    )
                    node.clear()
                    node.update(merged)
                    changed = True
                    return
            op_ref = node.get("operationId")
            if (
                isinstance(op_ref, str)
                and op_ref in overlay_ids
                and node.get("id") != op_ref
            ):
                man = _resolve_detail_overlay(op_ref)
                if man and _patch_receipt_like_node(node, man):
                    changed = True
            for v in node.values():
                visit(v)
        elif isinstance(node, list):
            for x in node:
                visit(x)

    visit(obj)
    return changed


def _patch_manual_detail_semantics(obj, man: dict) -> bool:
    changed = False
    typ = man.get("type") or "Debit"
    primary = (man.get("title") or man.get("phone") or man.get("description") or "").strip() or (
        "Операция" if typ == "Debit" else "Поступление"
    )
    sender_name = (man.get("requisite_sender_name") or man.get("sender_name") or "").strip() or primary
    phone = (man.get("requisite_phone") or man.get("phone") or "").strip() or str((controller.config.get("name") or {}).get("phone") or "").strip()
    formatted_phone = _format_phone_ru(phone)
    account_name = "Black"
    transfer_block_title = "Перевод" if typ == "Debit" else "Пополнение"
    balance_value = float(((controller.config.get("balance") or {}).get("new_balance")) or 0)
    # Используем card_number из ручной операции если есть, иначе из конфига
    account_mask = (man.get("card_number") or "").strip()
    if not account_mask:
        account_mask = str(((controller.config.get("balance") or {}).get("new_card_number")) or "").strip()
    if not account_mask:
        account_mask = "220070******0000"

    def _pick_reference_card_info():
        # Берем реальную карту из reference operation, чтобы `card_credentials`
        # вернул успех и UI показал все поля.
        try:
            replacement_id, _ = _pick_reference_operation()
            if not replacement_id:
                return {}
            ref = (history.operations_cache or {}).get(replacement_id) or {}
            if not isinstance(ref, dict):
                return {}
            return {
                "card_ucid": ref.get("ucid") or ref.get("cardUcid") or ref.get("card_ucid") or "",
                "account_id": ref.get("account") or ref.get("accountId") or ref.get("account_id") or "",
                "card_id": ref.get("card") or ref.get("cardId") or ref.get("card_id") or "",
            }
        except Exception:
            return {}

    ref_card = _pick_reference_card_info()
    card_ucid = ref_card.get("card_ucid") or "1386102627"
    account_id = ref_card.get("account_id") or "5860068322"
    card_id = ref_card.get("card_id") or "383947501"
    beneficiary = str(((controller.config.get("reki") or {}).get("beneficiary")) or "").strip()
    external_account = str(((controller.config.get("reki") or {}).get("account")) or "").strip()

    def set_money_dict(v):
        nonlocal changed
        if isinstance(v, dict) and "value" in v:
            v["value"] = balance_value
            changed = True

    def patch_label_value(node: dict, label_key: str, value_keys: tuple[str, ...]):
        nonlocal changed
        label = str(node.get(label_key) or "").strip().lower()
        if not label:
            return
        replacement = None
        replacement_label = None
        if "отправител" in label or "sender" in label:
            if typ == "Debit" and formatted_phone:
                replacement = formatted_phone
                replacement_label = "Номер телефона"
            else:
                replacement = sender_name
                replacement_label = "Отправитель"
        if "номер телефона" in label or label == "телефон" or "phone" in label:
            replacement = formatted_phone or phone
            replacement_label = "Номер телефона"
        elif "получател" in label or "фио" in label or "recipient" in label:
            replacement = primary
        elif "назначение" in label or "beneficiary" in label:
            replacement = beneficiary
        elif "счет" in label or "счёт" in label or "account" in label:
            replacement = external_account or account_mask or account_name
        elif "карт" in label or "pan" in label:
            replacement = account_mask or account_name
        if replacement is None:
            return
        for value_key in value_keys:
            if value_key in node:
                node[value_key] = replacement
                changed = True
        if replacement_label is not None and label_key in node:
            node[label_key] = replacement_label
            changed = True

    def visit(node):
        nonlocal changed
        if isinstance(node, dict):
            patch_label_value(node, "fieldName", ("fieldValue", "value", "text", "description", "subtitle", "content", "body", "primaryText", "secondaryText"))
            patch_label_value(node, "label", ("value", "text", "description", "subtitle", "content", "body", "primaryText", "secondaryText"))
            patch_label_value(node, "title", ("value", "text", "description", "subtitle", "content", "body", "primaryText", "secondaryText"))
            patch_label_value(node, "name", ("value", "text", "description", "subtitle", "content", "body", "primaryText", "secondaryText"))

            for key in ("phone", "phoneNumber", "recipientPhone", "pointer"):
                if key in node and phone:
                    node[key] = formatted_phone or phone
                    changed = True

            for key in ("recipient", "recipientName", "counterpartyName", "fullName"):
                if key in node and primary:
                    node[key] = primary
                    changed = True

            sender_value = (formatted_phone or phone) if typ == "Debit" else sender_name
            for key in ("sender", "senderName", "senderDetails", "payerName", "sourceName", "displayName"):
                if key in node and sender_value:
                    node[key] = sender_value
                    changed = True

            if "beneficiaryInfo" in node and beneficiary:
                node["beneficiaryInfo"] = beneficiary
                changed = True
            if "recipientExternalAccount" in node and external_account:
                node["recipientExternalAccount"] = external_account
                changed = True

            titleish = " ".join(
                str(node.get(k) or "").strip().lower()
                for k in ("title", "name", "description", "subtitle", "productName", "accountName", "cardName")
            )
            productish = any(
                key in node for key in (
                    "ucid", "account", "card", "cardNumber", "pan",
                    "productName", "accountName", "cardName",
                    "availableBalance", "moneyAmount", "balance", "accountBalance"
                )
            )
            # Не считаем вложенный card-credential словарь полноценным продуктовым блоком,
            # иначе ниже можно создать card внутри card и уйти в рекурсию.
            card_credentials_only = (
                any(key in node for key in ("ucid", "cardNumber", "pan"))
                and not any(
                    key in node for key in (
                        "productName", "accountName", "cardName",
                        "availableBalance", "moneyAmount", "balance", "accountBalance",
                        "description", "subtitle"
                    )
                )
            )
            if any(x in titleish for x in ("black", "дебетовая карта", "счет", "счёт", "карта", "перевод", "пополнение")) or productish:
                for key in ("title", "name"):
                    current = str(node.get(key) or "").strip().lower()
                    if key in node and current in ("", "перевод", "пополнение", "поступление", "операция"):
                        node[key] = transfer_block_title
                        changed = True
                for key in ("productName", "accountName", "cardName"):
                    if key in node:
                        node[key] = account_name
                        changed = True
                if "description" in node:
                    current_desc = str(node.get("description") or "").strip().lower()
                    if current_desc in ("", "дебетовая карта", "black", "карта", "счет", "счёт"):
                        node["description"] = account_name
                        changed = True
                if "subtitle" in node:
                    current_subtitle = str(node.get("subtitle") or "").strip().lower()
                    if current_subtitle in ("", "дебетовая карта", "black", "карта", "счет", "счёт"):
                        node["subtitle"] = account_name
                        changed = True
                for key in ("availableBalance", "moneyAmount", "balance", "accountBalance"):
                    if key in node:
                        set_money_dict(node[key])

                # Card/account/ucid — критично для блока requisites.
                for key, val in (
                    ("ucid", card_ucid),
                    ("account", account_id),
                    ("card", card_id),
                    ("cardNumber", account_mask),
                ):
                    if key in node and not node.get(key):
                        node[key] = val
                        changed = True

                # Иногда структура бывает вложенной: "card": {"ucid": ...}
                if isinstance(node.get("card"), dict):
                    if not node["card"].get("ucid"):
                        node["card"]["ucid"] = card_ucid
                    if not node["card"].get("id"):
                        node["card"]["id"] = card_id
                    if "cardNumber" in node["card"] and not node["card"].get("cardNumber"):
                        node["card"]["cardNumber"] = account_mask
                    changed = True
                elif productish and not card_credentials_only and ("card" in node or "cardNumber" in node or "cardName" in node):
                    node["card"] = {"id": card_id, "ucid": card_ucid, "cardNumber": account_mask}
                    changed = True

                if isinstance(node.get("account"), dict):
                    if not node["account"].get("id"):
                        node["account"]["id"] = account_id
                        changed = True
                elif productish and not card_credentials_only and ("account" in node or "accountName" in node or "balance" in node):
                    node["account"] = {"id": account_id}
                    changed = True

            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(obj)
    return changed


def response(flow: http.HTTPFlow) -> None:
    history.ensure_manual_operations_fresh()
    if not is_bank_flow(flow):
        return
    if not flow.response:
        return
    ensure_response_decoded(flow)
    txt = flow.response.text or ""
    if not txt.strip():
        return
    if not is_jsonish_response(flow):
        return

    url = flow.request.pretty_url or ""
    if url_prohibit_proxy_json_mutation(url):
        return
    if flow_statements_spravki_context(flow):
        return

    try:
        metadata_manual_id = flow.metadata.get("manual_detail_id")
    except Exception:
        metadata_manual_id = None

    ids_in_flow = _extract_ids_from_flow(flow)
    overlay_candidates = set()
    if isinstance(metadata_manual_id, str) and _resolve_detail_overlay(metadata_manual_id):
        overlay_candidates.add(metadata_manual_id)
    for mid in ids_in_flow:
        if _is_rewritable_detail_id(mid) and _resolve_detail_overlay(mid):
            overlay_candidates.add(mid)

    if not overlay_candidates:
        # Без известного overlay id — только если URL похож на detail/receipt и есть metadata
        if not (isinstance(metadata_manual_id, str) and metadata_manual_id):
            if not _url_suggests_detail_or_receipt(url):
                return
            return
        # metadata есть, но запись пока не резолвится — всё равно выходим
        return

    try:
        data = json.loads(txt)
    except Exception:
        return

    # Подмена id в запросе на reference → в ответе вернуть fake/manual id.
    try:
        manual_id = flow.metadata.get("manual_detail_id")
        replacement_id = flow.metadata.get("replacement_operation_id")
        if (
            isinstance(manual_id, str)
            and manual_id in overlay_candidates
            and isinstance(replacement_id, str)
            and replacement_id
        ):
            data = _replace_id_refs_in_json(data, replacement_id, manual_id)
    except Exception:
        pass

    target_manual = None
    if isinstance(metadata_manual_id, str):
        target_manual = _resolve_detail_overlay(metadata_manual_id)
    if not target_manual:
        for mid in overlay_candidates:
            target_manual = _resolve_detail_overlay(mid)
            if target_manual:
                break
    changed = _patch_tree(data, overlay_candidates)
    if target_manual:
        changed = _patch_manual_detail_semantics(data, target_manual) or changed
    if changed:
        flow.response.text = json.dumps(data, ensure_ascii=False)
        if bank_debug_enabled():
            print(f"[operation_detail] подмена ответа: {url[:160]}")
