"""
common.py
Các hàm dùng chung cho cả 2 job: telegram_commands.py và check_courses.py
"""

import json
import os
import re
import requests

CONFIG_PATH = "config/courses.json"
STATE_PATH = "state/state.json"
OFFSET_PATH = "state/telegram_offset.json"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return default
        return json.loads(content)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_config():
    cfg = load_json(CONFIG_PATH, {"courses": []})
    cfg.setdefault("semester_id", None)
    cfg.setdefault("timespan_id", None)
    return cfg


def save_config(cfg):
    save_json(CONFIG_PATH, cfg)


def load_state():
    return load_json(STATE_PATH, {})


def save_state(state):
    save_json(STATE_PATH, state)


def load_offset():
    return load_json(OFFSET_PATH, {"offset": 0}).get("offset", 0)


def save_offset(offset):
    save_json(OFFSET_PATH, {"offset": offset})


def telegram_get_updates(offset):
    """Lấy tin nhắn mới kể từ update_id = offset (offset đã +1 để không lấy lại tin cũ)."""
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN trong biến môi trường/secrets.")
    resp = requests.get(
        f"{TELEGRAM_API}/getUpdates",
        params={"offset": offset, "timeout": 0},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram getUpdates lỗi: {data}")
    return data.get("result", [])


def telegram_send_message(text, parse_mode="HTML"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID.")
    resp = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram sendMessage lỗi: {data}")
    return data


def find_course(cfg, course_id):
    for c in cfg["courses"]:
        if str(c["course_id"]) == str(course_id):
            return c
    return None


def extract_course_id(text):
    if not text:
        return None
    text = text.strip()
    if text.isdigit():
        return text
    match = re.search(r"[?&]courseid=(\d+)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None
