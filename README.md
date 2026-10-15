# 🚨 TCF Canada Edmonton Slot Monitor & Alert Bot

Hệ thống tự động giám sát cổng đăng ký thi **TCF Canada** của trung tâm **Alliance Française of Edmonton** để phát hiện ngay lập tức khi có suất thi còn chỗ (không bị `SOLD OUT` / `Closed`) và gửi thông báo tức thời về điện thoại qua **Telegram Bot**.

Hệ thống vận hành **hoàn toàn tự động trên nền tảng GitHub Actions**, chạy 24/7 trên máy chủ đám mây của GitHub, **không phụ thuộc vào máy tính cá nhân**, không tốn pin hay băng thông mạng nhà bạn.

---

## 📋 Tính năng nổi bật

* ⏱ **Quét định kỳ tự động:** Chạy đều đặn mỗi 10 phút suốt 24/7 qua GitHub Actions.
* 🎯 **Lọc chính xác theo khung ngày:** Mặc định quét các suất thi từ **23/11/2026** đến **15/12/2026** (có thể tùy chỉnh linh hoạt).
* 🌐 **Hỗ trợ đa ngôn ngữ (Anh / Pháp):** Tự động nhận diện định dạng ngày thi tiếng Anh (`Nov 23`, `23 November 2026`) và tiếng Pháp (`23 novembre`, `décembre`).
* 🛡 **Loại bỏ 100% báo động giả:** Sửa triệt để lỗi logic phủ định; kiểm tra đa tầng trạng thái `SOLD OUT`, `CLOSED` và số lượng chỗ khả dụng (`Spots left > 0` hoặc có nút `Register`).
* 📱 **Thông báo tức thời qua Telegram:** Kèm nút bấm **⚡ MỞ LINK ĐĂNG KÝ NGAY** để bạn chạm vào là mở thẳng trang đặt chỗ giữ slot ngay trên điện thoại.
* 🔕 **Chống spam thông minh:** Ghi nhớ trạng thái để không làm phiền bạn liên tục nếu cùng một suất thi vẫn đang mở.

---

## 🛠 Hướng dẫn thiết lập từ A đến Z (Dành cho người mới)

Chỉ mất khoảng **3 - 5 phút** để hoàn tất toàn bộ cài đặt theo các bước dưới đây:

### Bước 1: Tạo Bot Telegram & Lấy Token (1 phút)

1. Mở ứng dụng **Telegram** trên điện thoại hoặc máy tính.
2. Tìm kiếm người dùng: **`@BotFather`** (có tích xanh chính thức).
3. Bấm **Start** (hoặc gửi `/start`), sau đó gửi lệnh:
   ```text
   /newbot
   ```
4. Đặt tên hiển thị cho bot (ví dụ: `TCF Edmonton Alert Bot`).
5. Đặt username cho bot (phải kết thúc bằng chữ `bot`, ví dụ: `tcf_edmonton_alert_bot`).
6. Sau khi tạo xong, BotFather sẽ gửi cho bạn đoạn mã **HTTP API Token**, có dạng:
   ```text
   7123456789:AAFlkjhsdf89234jhklsd-sdf89234jkl
   ```
   👉 *Hãy lưu lại mã này (đây là `TELEGRAM_BOT_TOKEN`).*

---

### Bước 2: Lấy Chat ID của bạn (30 giây)

1. Mở ô tìm kiếm trên Telegram, tìm bot: **`@userinfobot`**.
2. Bấm **Start** (hoặc gửi tin nhắn bất kỳ cho nó).
3. Bot sẽ trả về thông tin tài khoản của bạn, bao gồm dòng:
   ```text
   Id: 123456789
   ```
   👉 *Dãy số này chính là `TELEGRAM_CHAT_ID` của bạn.*
4. **Lưu ý cực kỳ quan trọng:** Mở lại con bot bạn vừa tạo ở Bước 1 và bấm **Start** (gửi `/start`) với nó một lần. (Telegram quy định bot chỉ có thể gửi tin nhắn cho người dùng sau khi bạn đã bấm Start với nó).

---

### Bước 3: Tạo Repository trên GitHub & Đưa Secrets vào

1. Đăng nhập vào [GitHub](https://github.com/) và tạo một Repository mới (ví dụ đặt tên là `tcf-edmonton-monitor`).
   > 💡 **Khuyên dùng:** Đặt Repository ở chế độ **Public** để được **miễn phí 100% không giới hạn số phút chạy GitHub Actions**. Các thông tin nhạy cảm (Token, Chat ID, Link) được lưu an toàn trong phần **Secrets**, người khác hoàn toàn không thể xem được.
2. Tải toàn bộ mã nguồn trong thư mục `tcf_monitor` này lên repository của bạn.
3. Trên trang repository tại GitHub:
   * Vào mục **Settings** (bánh răng) ở thanh menu trên cùng.
   * Ở cột bên trái, chọn **Secrets and variables** ➔ chọn **Actions**.
   * Nhấn nút màu xanh **New repository secret** để thêm lần lượt 3 biến sau:

| Tên Secret | Ý nghĩa | Giá trị mẫu |
| :--- | :--- | :--- |
| `TARGET_URL` | Đường link trang thi của Alliance Française Edmonton | `https://edmonton.afedmonton.ca/community/event-rsvp/?event_id=...` |
| `TELEGRAM_BOT_TOKEN` | Token bot lấy từ `@BotFather` ở Bước 1 | `7123456789:AAFlkjhsdf89234jhklsd-sdf89234jkl` |
| `TELEGRAM_CHAT_ID` | Số ID lấy từ `@userinfobot` ở Bước 2 | `123456789` |

---

### Bước 4: Chạy thử nghiệm ngay trên GitHub (Test Manual)

1. Trên repository GitHub của bạn, nhấn vào tab **Actions**.
2. Ở cột bên trái, bạn sẽ thấy workflow mang tên: **`TCF Edmonton Slot Monitor`**.
3. Nhấn vào tên workflow, sau đó nhìn sang góc phải nhấn nút **Run workflow**.
4. (Tùy chọn) Bạn có thể tích chọn ô `test_telegram: true` rồi nhấn **Run workflow**:
   * Sau 15-30 giây, bot sẽ gửi ngay một tin nhắn chào mừng kiểm tra kết nối về điện thoại của bạn!
5. Kể từ thời điểm này, GitHub Actions sẽ tự động kích hoạt mỗi 10 phút để rà soát cổng thi. Khi có suất thi còn chỗ, điện thoại bạn sẽ rung chuông báo ngay lập tức!

---

## 💻 Chạy thử nghiệm cục bộ trên máy tính (Local Testing)

Nếu muốn chạy thử nghiệm trực tiếp trên máy Mac/PC của bạn:

```bash
# 1. Đi tới thư mục tcf_monitor
cd tcf_monitor

# 2. Tạo môi trường ảo và cài đặt thư viện
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Tạo file cấu hình .env từ file mẫu
cp .env.example .env
# Mở file .env và điền Token, Chat ID, URL của bạn vào

# 4. Kiểm tra gửi tin nhắn thử tới Telegram
python3 monitor.py --test-telegram

# 5. Chạy quét thực tế không gửi tin nhắn (Dry-run)
python3 monitor.py --dry-run

# 6. Chạy quét trực tiếp (sẽ gửi tin nhắn nếu có slot mở)
python3 monitor.py
```

---

## 🧪 Chạy bộ kiểm thử tự động (Unit Tests)

Bộ kiểm thử được viết sẵn để xác thực độ chính xác của bộ bóc tách DOM và bộ phân tích ngày tháng:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Kết quả:
```text
......
----------------------------------------------------------------------
Ran 6 tests in 0.001s

OK
```

---

## ⚙️ Tùy chỉnh nâng cao

### Đổi phạm vi ngày thi
Mặc định hệ thống lọc từ ngày `2026-11-23` đến `2026-12-15`. Nếu muốn đổi sang kỳ thi khác:
* **Khi chạy trên máy tính:** Chỉnh sửa biến `START_DATE` và `END_DATE` trong file `.env`.
* **Khi chạy trên GitHub Actions:** Vào **Settings ➔ Secrets and variables ➔ Actions ➔ tab Variables ➔ New repository variable** và thêm:
  * `START_DATE`: ví dụ `2026-12-01`
  * `END_DATE`: ví dụ `2026-12-31`

### Đổi chu kỳ quét
Trong file [monitor.yml](file:///.github/workflows/monitor.yml):
```yaml
schedule:
  - cron: '*/10 * * * *'   # Quét mỗi 10 phút (mặc định)
  # - cron: '*/5 * * * *'  # Quét mỗi 5 phút
```
