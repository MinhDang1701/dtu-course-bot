"""
check_courses.py
JOB 2 — đọc config đã được job 1 cập nhật, gọi website Duy Tân,
so sánh trạng thái chỗ trống, gửi Telegram nếu có thay đổi.

parse_class_list() đã được viết lại dựa trên HTML thật của
CourseClassResult.aspx (bảng class="tb-calendar", mỗi lớp là 1 <tr class="lop">
đi sau 1 <tr class="nhom-lop"> phân nhóm). Đã test với mẫu môn EVR 205.
"""

import re
import sys
from datetime import datetime, timezone, timedelta

from common import (
    load_config,
    load_state,
    save_state,
    telegram_send_message,
    fetch_class_list_html,
    parse_class_list,
)

VN_TZ = timezone(timedelta(hours=7))


def now_str():
    return datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")


def check_watched_classes(cfg, state):
    """So sánh trạng thái lớp đang theo dõi với lần trước, trả về list thay đổi."""
    changes = []

    for course in cfg["courses"]:
        watch = course.get("watch_classes") or []
        if not watch:
            continue

        try:
            html = fetch_class_list_html(
                course["course_id"], course["semester_id"], course["timespan_id"]
            )
            classes = parse_class_list(html)
        except Exception as e:
            print(f"[check_courses] Lỗi fetch môn {course['course_name']}: {e}")
            continue

        # Cho phép tra theo mã lớp ngắn ("A") hoặc mã đăng ký đầy đủ ("EVR205202601001")
        classes_by_code = {}
        for c in classes:
            classes_by_code[c["code"]] = c
            classes_by_code[c["reg_code"]] = c

        for code in watch:
            key = f"{course['course_id']}:{code}"
            current = classes_by_code.get(code)
            if not current:
                continue  # không tìm thấy lớp này trong lần fetch — bỏ qua, không báo lỗi giả

            prev = state.get(key)
            prev_slots = prev["slots"] if prev else None

            if prev_slots is None:
                # lần đầu tiên thấy lớp này — chỉ lưu, không báo (tránh báo giả lúc mới track)
                pass
            elif current["slots"] > prev_slots:
                changes.append({
                    "course_name": course["course_name"],
                    "class_code": code,
                    "prev_slots": prev_slots,
                    "new_slots": current["slots"],
                    "status": current["status"],
                })

            state[key] = {"slots": current["slots"], "status": current["status"]}

    return changes


def send_change_summary(changes):
    if not changes:
        return
    lines = ["📢 DTU Course Alert\n", f"{now_str()}\n", f"Có {len(changes)} thay đổi:\n"]
    for ch in changes:
        lines.append(
            f"✅ {ch['course_name']} {ch['class_code']}\n"
            f"{ch['prev_slots']} → {ch['new_slots']} chỗ"
        )
    telegram_send_message("\n\n".join(lines))


def main():
    cfg = load_config()
    state = load_state()

    changes = check_watched_classes(cfg, state)
    send_change_summary(changes)

    state["_last_check_time"] = now_str()

    save_state(state)


if __name__ == "__main__":
    main()
