"""
telegram_commands.py
JOB 1 — chỉ xử lý tin nhắn Telegram, KHÔNG gọi website Duy Tân.
Nếu phần này lỗi (Telegram API sập, sai cú pháp lệnh...) sẽ không ảnh hưởng
tới job check lớp học ở job 2.

Lệnh hỗ trợ:
  /hocky <semester_id> <timespan_id>
  /track <course_id hoặc URL môn học> <ten_mon>
  /untrack <course_id>
  /list
  /classes <course_id>      -> gửi ngay danh sách lớp qua Telegram
  /select <course_id> <ma_lop_1> <ma_lop_2> ...
  /status
"""

import sys
import time
from common import (
    load_config,
    save_config,
    load_offset,
    save_offset,
    load_state,
    telegram_get_updates,
    telegram_send_message,
    find_course,
    extract_course_id,
    fetch_class_list_html,
    parse_class_list,
)


def cmd_hocky(cfg, args):
    if len(args) < 2:
        return "❌ Cú pháp: /hocky (semester_id) (timespan_id)"
    cfg["semester_id"] = args[0]
    cfg["timespan_id"] = args[1]
    return (f"✅ Đã lưu semester_id = {args[0]} và timespan_id = {args[1]}.\n"
            f"Từ giờ lệnh /track chỉ cần course_id hoặc URL môn học và tên môn.")


def cmd_track(cfg, args):
    semester_id = cfg.get("semester_id")
    timespan_id = cfg.get("timespan_id")
    if semester_id is None or timespan_id is None:
        return "❌ Vui lòng cài đặt học kỳ bằng lệnh /hocky (semester_id) (timespan_id) trước."

    if len(args) < 2:
        return "❌ Cú pháp: /track (course_id hoặc URL môn học) (ten_mon)"

    course_id = extract_course_id(args[0])
    if course_id is None:
        return "❌ Không nhận diện được course_id từ tham số đã nhập."

    course_name = " ".join(args[1:])

    if find_course(cfg, course_id):
        return f"⚠️ Môn {course_id} đã có trong danh sách theo dõi rồi."

    cfg["courses"].append({
        "course_id": course_id,
        "semester_id": semester_id,
        "timespan_id": timespan_id,
        "course_name": course_name,
        "watch_classes": [],
    })

    msg_added = f"✅ Đã thêm môn {course_name} (id {course_id}).\n\n"
    
    try:
        html = fetch_class_list_html(course_id, semester_id, timespan_id)
        classes = parse_class_list(html)
    except Exception as e:
        return msg_added + f"❌ Lỗi khi lấy danh sách lớp: {e}"

    if not classes:
        return msg_added + (
            f"⚠️ Không parse được danh sách lớp cho {course_name}.\n"
            f"Có thể cấu trúc HTML khác dự đoán — cần gửi mẫu HTML thật để chỉnh lại."
        )

    lines = [msg_added + f"📚 Danh sách lớp — {course_name} (id {course_id}):\n"]
    for c in classes:
        lines.append(
            f"• {c['code']} — {c['status']} — {c['teacher']}\n"
            f"  {c['schedule']}"
        )
    lines.append(f"\nDùng /select {course_id} (mã lớp...) để chọn lớp theo dõi.")
    lines.append("Ví dụ: /select " + str(course_id) + " "
                 + " ".join(c["code"] for c in classes[:2]))
    return "\n".join(lines)


def cmd_untrack(cfg, args):
    if len(args) < 1:
        return "❌ Cú pháp: /untrack (course_id)"
    course_id = args[0]
    before = len(cfg["courses"])
    cfg["courses"] = [c for c in cfg["courses"] if str(c["course_id"]) != str(course_id)]
    if len(cfg["courses"]) == before:
        return f"⚠️ Không tìm thấy môn {course_id} trong danh sách theo dõi."
    return f"✅ Đã xóa môn {course_id} khỏi danh sách theo dõi."


def cmd_list(cfg, args):
    if not cfg["courses"]:
        return "📭 Chưa theo dõi môn nào. Dùng /track để thêm."
    lines = ["📋 Danh sách môn đang theo dõi:\n"]
    for c in cfg["courses"]:
        watch = c.get("watch_classes") or []
        watch_str = ", ".join(watch) if watch else "(chưa chọn lớp — dùng /classes rồi /select)"
        lines.append(f"• {c['course_name']} (id {c['course_id']}) — lớp: {watch_str}")
    return "\n".join(lines)


def cmd_classes(cfg, args):
    if len(args) < 1:
        return "❌ Cú pháp: /classes (course_id)"
    course_id = args[0]
    course = find_course(cfg, course_id)
    if not course:
        return f"⚠️ Chưa theo dõi môn {course_id}. Dùng /track trước."
    
    try:
        html = fetch_class_list_html(
            course["course_id"], course["semester_id"], course["timespan_id"]
        )
        classes = parse_class_list(html)
    except Exception as e:
        return f"❌ Lỗi khi lấy danh sách lớp cho {course['course_name']}: {e}"

    if not classes:
        return (
            f"⚠️ Không parse được danh sách lớp cho {course['course_name']}.\n"
            f"Có thể cấu trúc HTML khác dự đoán — cần gửi mẫu HTML thật để chỉnh lại."
        )

    lines = [f"📚 Danh sách lớp — {course['course_name']} (id {course['course_id']}):\n"]
    for c in classes:
        lines.append(
            f"• {c['code']} — {c['status']} — {c['teacher']}\n"
            f"  {c['schedule']}"
        )
    lines.append(f"\nDùng /select {course['course_id']} (mã lớp...) để chọn lớp theo dõi.")
    lines.append("Ví dụ: /select " + str(course["course_id"]) + " "
                 + " ".join(c["code"] for c in classes[:2]))
    return "\n".join(lines)


def cmd_select(cfg, args):
    if len(args) < 2:
        return "❌ Cú pháp: /select (course_id) (ma_lop_1) (ma_lop_2) ..."
    course_id = args[0]
    class_codes = args[1:]
    course = find_course(cfg, course_id)
    if not course:
        return f"⚠️ Chưa theo dõi môn {course_id}. Dùng /track trước."
    course["watch_classes"] = class_codes
    return f"✅ {course['course_name']}: chỉ theo dõi lớp {', '.join(class_codes)}."


def cmd_status(cfg, args):
    state = load_state()
    total_courses = len(cfg["courses"])
    total_classes = sum(len(c.get("watch_classes") or []) for c in cfg["courses"])
    last_check = state.get("_last_check_time", "chưa có lần check nào")
    
    sem_str = cfg.get("semester_id") if cfg.get("semester_id") is not None else "(chưa khai báo)"
    time_str = cfg.get("timespan_id") if cfg.get("timespan_id") is not None else "(chưa khai báo)"

    return (f"🤖 Bot đang hoạt động.\n"
            f"Semester ID: {sem_str}\n"
            f"Timespan ID: {time_str}\n"
            f"Số môn theo dõi: {total_courses}\n"
            f"Số lớp đang theo dõi: {total_classes}\n"
            f"Lần check lớp gần nhất: {last_check}")


COMMANDS = {
    "/hocky": cmd_hocky,
    "/track": cmd_track,
    "/untrack": cmd_untrack,
    "/list": cmd_list,
    "/classes": cmd_classes,
    "/select": cmd_select,
    "/status": cmd_status,
}


def process_message(cfg, text):
    parts = text.strip().split()
    if not parts:
        return None
    cmd = parts[0].lower()
    args = parts[1:]
    handler = COMMANDS.get(cmd)
    if not handler:
        return None  # bỏ qua tin nhắn không phải lệnh hợp lệ
    return handler(cfg, args)


def main():
    cfg = load_config()
    offset = load_offset()

    try:
        updates = telegram_get_updates(offset)
    except Exception as e:
        print(f"[telegram_commands] Lỗi khi lấy tin nhắn: {e}")
        sys.exit(0)  # không làm fail cả job, để job 2 vẫn chạy bình thường

    if not updates:
        print("[telegram_commands] Không có tin nhắn mới.")
        return

    replies = []
    max_update_id = offset - 1

    for update in updates:
        max_update_id = max(max_update_id, update["update_id"])
        message = update.get("message") or update.get("edited_message")
        if not message:
            continue
        text = message.get("text", "")
        if not text.startswith("/"):
            continue
        reply = process_message(cfg, text)
        if reply:
            replies.append(reply)

    save_offset(max_update_id + 1)
    save_config(cfg)

    for reply in replies:
        try:
            telegram_send_message(reply)
            time.sleep(0.5)  # tránh gửi quá nhanh bị Telegram giới hạn
        except Exception as e:
            print(f"[telegram_commands] Lỗi khi gửi tin nhắn: {e}")


if __name__ == "__main__":
    main()
