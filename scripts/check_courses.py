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

import requests
from bs4 import BeautifulSoup

from common import load_config, save_config, load_state, save_state, telegram_send_message

BASE_URL = "https://courses.duytan.edu.vn/Modules/academicprogram/CourseClassResult.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

VN_TZ = timezone(timedelta(hours=7))


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

    Cấu trúc thật (đã xác nhận với mẫu môn EVR 205):
      <table class="tb-calendar">
        <tbody>
          <tr><td colspan="12" class="nhom-lop"><div>EVR 205 A</div></td></tr>
          <tr class="lop">
            <td class="hit"><a>EVR 205 A</a></td>          <!-- 0: tên lớp -->
            <td><a>EVR205202601001</a></td>                  <!-- 1: mã đăng ký -->
            <td>LEC</td>                                     <!-- 2: loại hình -->
            <td><div>1</div></td>  hoặc <div>Hết chỗ</div>    <!-- 3: số chỗ còn lại -->
            <td>...</td>                                      <!-- 4: hạn đăng ký -->
            <td>11--18</td>                                   <!-- 5: tuần học -->
            <td>...giờ học...</td>                             <!-- 6: giờ học -->
            <td>...phòng...</td>                               <!-- 7: phòng -->
            <td>...địa điểm...</td>                            <!-- 8: địa điểm -->
            <td>GIẢNG VIÊN</td>                                <!-- 9: giảng viên -->
            <td>Còn Hạn Đăng Ký</td>                           <!-- 10: tình trạng đăng ký -->
            <td>Lớp Học Chưa Bắt Đầu</td>                      <!-- 11: tình trạng triển khai -->
          </tr>
          ...
        </tbody>
      </table>

    Trả về list các dict:
      {
        "code": "A",                        # mã lớp ngắn, dùng cho /select
        "reg_code": "EVR205202601001",       # mã đăng ký đầy đủ, duy nhất
        "full_name": "EVR 205 A",
        "teacher": "NGUYỄN PHAN TRÚC XUYÊN",
        "schedule": "...",                   # text giờ học thô
        "status": "Hết chỗ" | "Còn 2 chỗ",
        "slots": 0,
      }
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


def now_str():
    return datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")


def handle_pending_class_lists(cfg):
    """Với các môn vừa được /classes yêu cầu, fetch và gửi danh sách lớp."""
    changed = False
    for course in cfg["courses"]:
        if not course.get("pending_class_list"):
            continue
        changed = True
        try:
            html = fetch_class_list_html(
                course["course_id"], course["semester_id"], course["timespan_id"]
            )
            classes = parse_class_list(html)
        except Exception as e:
            telegram_send_message(
                f"❌ Lỗi khi lấy danh sách lớp cho {course['course_name']}: {e}"
            )
            course["pending_class_list"] = False
            continue

        if not classes:
            telegram_send_message(
                f"⚠️ Không parse được danh sách lớp cho {course['course_name']}.\n"
                f"Có thể cấu trúc HTML khác dự đoán — cần gửi mẫu HTML thật để chỉnh lại."
            )
        else:
            lines = [f"📚 Danh sách lớp — {course['course_name']} (id {course['course_id']}):\n"]
            for c in classes:
                lines.append(
                    f"• {c['code']} — {c['status']} — {c['teacher']}\n"
                    f"  {c['schedule']}"
                )
            lines.append(f"\nDùng /select {course['course_id']} <mã_lớp...> để chọn lớp theo dõi.")
            lines.append("Ví dụ: /select " + str(course["course_id"]) + " "
                         + " ".join(c["code"] for c in classes[:2]))
            telegram_send_message("\n".join(lines))

        course["pending_class_list"] = False

    return changed


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

    config_changed = handle_pending_class_lists(cfg)

    changes = check_watched_classes(cfg, state)
    send_change_summary(changes)

    state["_last_check_time"] = now_str()

    save_state(state)
    if config_changed:
        save_config(cfg)


if __name__ == "__main__":
    main()
