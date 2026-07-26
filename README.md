# DTU Course Watcher Bot

Bot theo dõi chỗ trống lớp tín chỉ Đại học Duy Tân, chạy hoàn toàn miễn phí
trên GitHub Actions (không cần bật máy tính, không cần VPS).

## 1. Setup ban đầu

1. Tạo bot Telegram qua **@BotFather** trên Telegram → lấy `TELEGRAM_BOT_TOKEN`.
2. Lấy `TELEGRAM_CHAT_ID` của bạn: nhắn vài tin cho bot vừa tạo, sau đó mở
   trình duyệt vào:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   → tìm trường `"chat":{"id": ...}` — đó là chat id của bạn.
3. Tạo 1 repo GitHub mới (public để không tốn phút chạy, hoặc private nếu
   muốn giấu code — private thì nên tăng chu kỳ cron lên 20-30 phút để
   không vượt 2.000 phút/tháng free).
4. Upload toàn bộ nội dung thư mục này lên repo đó.
5. Vào repo → **Settings → Secrets and variables → Actions → New repository
   secret**, thêm 2 secret:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
6. Vào tab **Actions** của repo, bấm **Enable workflows** nếu bị tắt mặc định.
7. Có thể bấm **Run workflow** (workflow_dispatch) để test thử ngay, không
   cần đợi tới chu kỳ cron.

## 2. Cách dùng qua Telegram

```
/track <course_id> <semester_id> <timespan_id> <ten_mon>
```
Ví dụ: `/track 1860 95 95 HIS362`
→ Thêm môn theo dõi. Trong lần chạy tiếp theo (~15 phút), bot sẽ tự gửi
danh sách toàn bộ lớp của môn này.

```
/classes <course_id>
```
Yêu cầu bot gửi lại danh sách lớp hiện tại của 1 môn đã track.

```
/select <course_id> <ma_lop_1> <ma_lop_2> ...
```
Ví dụ: `/select 1860 A AE`
→ Chỉ theo dõi 2 lớp A và AE của môn 1860, các lớp khác bị bỏ qua.

```
/list
```
Xem tất cả môn + lớp đang theo dõi.

```
/untrack <course_id>
```
Ngừng theo dõi 1 môn (dùng khi sang học kỳ mới, đổi mã môn).

```
/status
```
Kiểm tra bot còn hoạt động, xem lần check gần nhất.

**Lưu ý về độ trễ lệnh:** vì bot chỉ chạy theo lịch (không lắng nghe real-time),
lệnh Telegram sẽ được xử lý trong lần chạy tiếp theo — nghĩa là có thể mất tới
15 phút để bot phản hồi.

## 3. Cách lấy `course_id`, `semester_id`, `timespan_id`

Mở trang môn học trên `courses.duytan.edu.vn`, mở DevTools (F12) → tab
Network → tìm request tới `CourseClassResult.aspx` → xem các tham số
`courseid`, `semesterid`, `timespan` trong URL.

## 4. Điểm cần kiểm tra lại (parser chưa được xác nhận với HTML thật)

File `scripts/check_courses.py`, hàm `parse_class_list()`, hiện đang **dự
đoán** cấu trúc HTML trả về từ `CourseClassResult.aspx` (thử tìm `<table>`
trước, fallback quét text thô). Nếu sau khi chạy thử mà:
- Không parse ra lớp nào, hoặc
- Trạng thái/chỗ trống hiển thị sai

→ Hãy lấy đoạn HTML thật (DevTools → Network → request
`CourseClassResult.aspx` → tab Response → copy toàn bộ) và gửi lại để chỉnh
hàm `parse_class_list()` cho chính xác.

## 5. Cấu trúc project

```
.
├── .github/workflows/check.yml   # 2 job: xử lý lệnh Telegram, check lớp học
├── scripts/
│   ├── common.py                 # hàm dùng chung (đọc/ghi config, gọi Telegram API)
│   ├── telegram_commands.py      # JOB 1
│   └── check_courses.py          # JOB 2
├── config/courses.json           # danh sách môn/lớp đang theo dõi (tự cập nhật)
├── state/state.json              # trạng thái lớp lần check trước (tự cập nhật)
├── state/telegram_offset.json    # offset getUpdates (tự cập nhật)
└── requirements.txt
```
