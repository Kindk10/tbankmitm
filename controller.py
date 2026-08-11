from mitmproxy import http
import json
from datetime import datetime
from urllib.parse import parse_qs
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

# Начальный конфиг
config = {
    "name": {
        "first_name": "ИВАН",
        "last_name": "ИВАНОВ",
        "middle_name": "ИВАНОВИЧ",
        "full_name": "ИВАНОВ ИВАН ИВАНОВИЧ",
        "phone": "+79991112233",
        "phone_number": "9991112233",
        "first_name_en": "IVAN",
        "last_name_en": "IVANOV",
        "middle_name_en": "IVANOVICH",
        "gender": "male",
        "sex_code": "male",
        "passport_series": "1212",
        "passport_number": "345678",
        "passport_issued_by": "TESTOVOE UVD",
        "passport_issue_date": "2020-02-02",
        "inn": "123456789012",
        "email": ""
    },
    "reki": {
        "contract": "7777777777",
        "account": "40817810799999999999",
        "recipient": "ИВАНОВ ИВАН ИВАНОВИЧ",
        "beneficiary": "Перевод средств по договору № 7777777777 ИВАНОВ ИВАН ИВАНОВИЧ НДС не облагается"
    },
    "balance": {
        "new_balance": 9999999.99,
        "new_card_number": "9999******9999",
        "new_collect_sum": 999999
    },
    "transfers": {
        "total_out_rub": 0
    },
    "history": {
        "show_categories": True,
        "sort_direction": "desc",
        "filter_month": datetime.now().month,
        "panel_show_all_operations": True,
    }
}

# Загружаем сохранённый конфиг, если есть
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            saved = json.load(f)
            # Рекурсивно обновляем, чтобы сохранить структуру
            for key in saved:
                if key in config and isinstance(config[key], dict) and isinstance(saved[key], dict):
                    config[key].update(saved[key])
                else:
                    config[key] = saved[key]
            print("✅ Конфиг загружен из файла")
        except Exception as e:
            print(f"❌ Ошибка загрузки конфига: {e}")


def _sync_panel_fetch_origin_from_env():
    """С телефона WebView fetch идёт на публичный IP VPS, не на 127.0.0.1."""
    origin = (os.environ.get("TBANK_PANEL_FETCH_ORIGIN") or "").strip().rstrip("/")
    if not origin:
        ip = (os.environ.get("TBANKMITM_PUBLIC_IP") or "").strip()
        port = (os.environ.get("TBANKMITM_PROXY_PORT") or "8082").strip() or "8082"
        if ip:
            origin = f"http://{ip}:{port}"
    if origin:
        config["panel_fetch_origin"] = origin


def phone_to_phone_number(phone):
    """Из '+79101234567' / '89101234567' / '9101234567' → 10 цифр для msisdn / mobilePhoneNumber."""
    digits = "".join(c for c in str(phone or "") if c.isdigit())
    if len(digits) >= 11 and digits[0] in ("7", "8"):
        digits = digits[1:]
    if len(digits) > 10:
        digits = digits[-10:]
    return digits


def sync_name_phone_number(name_cfg=None):
    """Держит name.phone_number в синхроне с name.phone после сохранения из панели."""
    nm = name_cfg if name_cfg is not None else config.get("name")
    if not isinstance(nm, dict):
        return
    phone = (nm.get("phone") or "").strip()
    if not phone:
        return
    derived = phone_to_phone_number(phone)
    if not derived:
        return
    current = "".join(c for c in str(nm.get("phone_number") or "") if c.isdigit())
    if len(current) >= 11 and current[0] in ("7", "8"):
        current = current[1:]
    if len(current) > 10:
        current = current[-10:]
    changed = current != derived
    if changed:
        nm["phone_number"] = derived


def save_config():
    """Сохраняет конфиг в файл"""
    try:
        sync_name_phone_number()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"✅ Конфиг сохранён в {CONFIG_FILE}")
    except Exception as e:
        print(f"❌ Ошибка сохранения конфига: {e}")

# Сохраняем начальный конфиг
_sync_panel_fetch_origin_from_env()
sync_name_phone_number()
save_config()

HTML_PATH = os.path.join(os.path.dirname(__file__), "panel.html")

def load_html():
    try:
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<html><body><h1>panel.html не найден</h1><p>Путь: {HTML_PATH}</p><p>Ошибка: {e}</p></body></html>"

def request(flow: http.HTTPFlow) -> None:
    global config
    url = flow.request.pretty_url

    if flow.request.host == "localhost" and flow.request.port == 8084:
        if flow.request.path == "/admin":
            flow.response = http.Response.make(200, load_html(), {"Content-Type": "text/html"})
            print("✅ Панель управления открыта")
            return

        if flow.request.path == "/api/config":
            # Возвращаем текущий конфиг
            flow.response = http.Response.make(
                200,
                json.dumps(config, ensure_ascii=False),
                {"Content-Type": "application/json"}
            )
            return

        if flow.request.method == "POST" and flow.request.path == "/api/config/save":
            body = flow.request.text
            try:
                new_config = json.loads(body)
                print(f"📦 Получены новые настройки: {list(new_config.keys())}")
                
                # Обновляем конфиг
                for key, value in new_config.items():
                    if key in config and isinstance(config[key], dict) and isinstance(value, dict):
                        config[key].update(value)
                        print(f"  🔄 Обновлён раздел {key}: {value}")
                    else:
                        config[key] = value
                        print(f"  ➕ Добавлен раздел {key}: {value}")

                if "name" in new_config and isinstance(config.get("name"), dict):
                    sync_name_phone_number(config["name"])
                
                # Сохраняем в файл
                save_config()
                
                flow.response = http.Response.make(200, json.dumps({"status": "ok"}))
            except Exception as e:
                print(f"❌ Ошибка сохранения: {e}")
                flow.response = http.Response.make(400, json.dumps({"error": str(e)}))
            return

        if flow.request.path == "/favicon.ico":
            flow.response = http.Response.make(204)
            return

