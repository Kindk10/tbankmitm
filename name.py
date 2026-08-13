from mitmproxy import http
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bank_filter import (
    is_bank_flow,
    ensure_response_decoded,
    bank_debug_enabled,
    flow_statements_spravki_context,
    url_prohibit_proxy_json_mutation,
)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def _digits_phone_number(phone: str, phone_number: str = "") -> str:
    """10 цифр для mobilePhoneNumber / msisdn; приоритет у нормализованного phone."""
    try:
        from controller import phone_to_phone_number
    except Exception:
        def phone_to_phone_number(p):  # type: ignore
            d = "".join(c for c in str(p or "") if c.isdigit())
            if len(d) >= 11 and d[0] in ("7", "8"):
                d = d[1:]
            return d[-10:] if len(d) > 10 else d

    derived = phone_to_phone_number(phone)
    if derived and len(derived) == 10:
        return derived
    fallback = phone_to_phone_number(phone_number)
    return fallback if fallback else (phone_number or "")


def get_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["name"]

def response(flow: http.HTTPFlow) -> None:
    url = flow.request.pretty_url

    if not is_bank_flow(flow):
        return
    if not flow.response:
        return
    if url_prohibit_proxy_json_mutation(url):
        return
    if flow_statements_spravki_context(flow):
        return
    ensure_response_decoded(flow)
    if not flow.response.text:
        if bank_debug_enabled():
            print(f"[name] пустой ответ: {url[:120]}")
        return
    
    # Получаем свежий конфиг при каждом запросе
    try:
        name_cfg = get_config()
        phone = name_cfg.get("phone") or ""
        phone_number = _digits_phone_number(phone, name_cfg.get("phone_number") or "")
        TEST_DATA = {
            "first_name": name_cfg["first_name"],
            "last_name": name_cfg["last_name"],
            "middle_name": name_cfg["middle_name"],
            "full_name": name_cfg["full_name"],
            "phone": phone,
            "phone_number": phone_number,
            "first_name_en": name_cfg["first_name_en"],
            "last_name_en": name_cfg["last_name_en"],
            "middle_name_en": name_cfg["middle_name_en"],
            "gender": name_cfg["gender"],
            "sex_code": name_cfg["sex_code"],
            "passport_series": name_cfg["passport_series"],
            "passport_number": name_cfg["passport_number"],
            "passport_issued_by": name_cfg["passport_issued_by"],
            "passport_issue_date": name_cfg["passport_issue_date"],
            "inn": name_cfg["inn"]
        }
    except:
        return  # если файла нет — ничего не делаем
    
    # ===== ВЕБ =====
    if "auth/short_personal_info" in url:
        try:
            data = json.loads(flow.response.text)
            if "payload" in data and "personalInfo" in data["payload"]:
                pi = data["payload"]["personalInfo"]
                
                if "fullName" in pi:
                    if "firstName" in pi["fullName"]:
                        pi["fullName"]["firstName"] = TEST_DATA["first_name"]
                    if "patronymic" in pi["fullName"]:
                        pi["fullName"]["patronymic"] = TEST_DATA["middle_name"]
                    if "lastName" in pi["fullName"]:
                        pi["fullName"]["lastName"] = TEST_DATA["last_name"]
                
                if "mobilePhoneNumber" in pi and TEST_DATA["phone_number"]:
                    pn = TEST_DATA["phone_number"]
                    # innerCode = код оператора (3 цифры), number = остальные 7
                    pi["mobilePhoneNumber"]["innerCode"] = pn[0:3] if len(pn) >= 3 else pn
                    pi["mobilePhoneNumber"]["number"] = pn[-7:] if len(pn) >= 7 else pn
                    # #region agent log
                    try:
                        from _agent_debug_log import dbg
                        dbg("H1", "name.short_personal_info", "patched mobilePhoneNumber", {
                            "pn_len": len(pn),
                            "inner_len": len(str(pi["mobilePhoneNumber"].get("innerCode") or "")),
                            "number_len": len(str(pi["mobilePhoneNumber"].get("number") or "")),
                        })
                    except Exception:
                        pass
                    # #endregion
            
            flow.response.text = json.dumps(data, ensure_ascii=False)
        except:
            pass
    
    # ===== ДОКУМЕНТЫ =====
    if "document/all" in url:
        try:
            data = json.loads(flow.response.text)
            if "payload" in data and "documents" in data["payload"]:
                docs = data["payload"]["documents"]
                
                if "RusNationalID" in docs and len(docs["RusNationalID"]) > 0:
                    for doc in docs["RusNationalID"]:
                        if "value" in doc:
                            val = doc["value"]
                            
                            if "serial" in val and "value" in val["serial"]:
                                val["serial"]["value"] = TEST_DATA["passport_series"]
                            if "number" in val and "value" in val["number"]:
                                val["number"]["value"] = TEST_DATA["passport_number"]
                            if "deliveredBy" in val and "value" in val["deliveredBy"]:
                                val["deliveredBy"]["value"] = TEST_DATA["passport_issued_by"]
                            if "dates" in val and "delivery" in val["dates"]:
                                if "value" in val["dates"]["delivery"]:
                                    val["dates"]["delivery"]["value"] = TEST_DATA["passport_issue_date"]
                            
                            if "person" in val:
                                person = val["person"]
                                if "firstName" in person and "value" in person["firstName"]:
                                    person["firstName"]["value"] = TEST_DATA["first_name"]
                                if "lastName" in person and "value" in person["lastName"]:
                                    person["lastName"]["value"] = TEST_DATA["last_name"]
                                if "middleName" in person and "value" in person["middleName"]:
                                    person["middleName"]["value"] = TEST_DATA["middle_name"]
                                if "sexCode" in person and "value" in person["sexCode"]:
                                    person["sexCode"]["value"] = TEST_DATA["sex_code"]
                                if "firstNameEn" in person and "value" in person["firstNameEn"]:
                                    person["firstNameEn"]["value"] = TEST_DATA["first_name_en"]
                                if "lastNameEn" in person and "value" in person["lastNameEn"]:
                                    person["lastNameEn"]["value"] = TEST_DATA["last_name_en"]
                                if "middleNameEn" in person and "value" in person["middleNameEn"]:
                                    person["middleNameEn"]["value"] = TEST_DATA["middle_name_en"]
                
                if "RusINN" in docs and len(docs["RusINN"]) > 0:
                    for doc in docs["RusINN"]:
                        if "value" in doc:
                            val = doc["value"]
                            if "inn" in val and "value" in val["inn"]:
                                val["inn"]["value"] = TEST_DATA["inn"]
                            
                            if "person" in val:
                                person = val["person"]
                                if "firstName" in person and "value" in person["firstName"]:
                                    person["firstName"]["value"] = TEST_DATA["first_name"]
                                if "lastName" in person and "value" in person["lastName"]:
                                    person["lastName"]["value"] = TEST_DATA["last_name"]
                                if "middleName" in person and "value" in person["middleName"]:
                                    person["middleName"]["value"] = TEST_DATA["middle_name"]
            
            flow.response.text = json.dumps(data, ensure_ascii=False)
        except:
            pass
    
    # ===== ЛК =====
    if any(x in url for x in ["userinfo", "personal_info", "profile", "messenger/userInfo", "contracts"]):
        try:
            data = json.loads(flow.response.text)
            if isinstance(data, dict):
                if "name" in data:
                    data["name"] = TEST_DATA["full_name"]
                if "given_name" in data:
                    data["given_name"] = TEST_DATA["first_name"]
                if "family_name" in data:
                    data["family_name"] = TEST_DATA["last_name"]
                if "middle_name" in data:
                    data["middle_name"] = TEST_DATA["middle_name"]
                
                if "phone_number" in data:
                    data["phone_number"] = TEST_DATA["phone"]
                if "phone" in data:
                    data["phone"] = TEST_DATA["phone"]
                if "msisdn" in data:
                    data["msisdn"] = TEST_DATA["phone_number"]
                
                if "payload" in data and isinstance(data["payload"], dict):
                    if "notMobileNumbers" in data["payload"]:
                        for item in data["payload"]["notMobileNumbers"]:
                            if "msisdn" in item:
                                item["msisdn"] = TEST_DATA["phone_number"]
            
            flow.response.text = json.dumps(data, ensure_ascii=False)
        except:
            pass

print("[+] name.py загружен (динамический конфиг)")