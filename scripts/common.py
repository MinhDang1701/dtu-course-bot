"""
common.py
Các hàm dùng chung cho cả 2 job: telegram_commands.py và check_courses.py
"""

import json
import os
import re
import requests
from bs4 import BeautifulSoup

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


BASE_URL = "https://courses.duytan.edu.vn/Modules/academicprogram/CourseClassResult.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_class_list_html(course_id, semester_id, timespan_id):
    params = {
        "courseid": course_id,
        "semesterid": semester_id,
        "timespan": timespan_id,
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_class_list(html):
    """
    Parse bảng class="tb-calendar" trong response của CourseClassResult.aspx.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    table = soup.find("table", class_="tb-calendar")
    if not table:
        return results

    rows = table.find_all("tr", class_="lop")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 10:
            continue  # dòng không đủ cột như mong đợi, bỏ qua an toàn

        full_name = cells[0].get_text(strip=True)          # "EVR 205 A"
        reg_code = cells[1].get_text(strip=True)            # "EVR205202601001"
        slots_text = cells[3].get_text(strip=True)          # "1" hoặc "Hết chỗ"
        schedule = cells[6].get_text(" ", strip=True)
        teacher = cells[9].get_text(strip=True)

        # Mã lớp ngắn: từ cuối cùng của tên lớp, ví dụ "EVR 205 A" -> "A"
        name_parts = full_name.split()
        code = name_parts[-1] if name_parts else full_name

        if slots_text.isdigit():
            slots = int(slots_text)
            status = f"Còn {slots} chỗ"
        else:
            slots = 0
            status = "Hết chỗ" if "Hết" in slots_text else slots_text

        results.append({
            "code": code,
            "reg_code": reg_code,
            "full_name": full_name,
            "teacher": teacher,
            "schedule": schedule,
            "status": status,
            "slots": slots,
        })

    return results

