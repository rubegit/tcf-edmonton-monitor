#!/usr/bin/env python3
"""
TCF Canada Edmonton Slot Monitor & Alert Bot
Automated monitoring of Alliance Française of Edmonton exam registrations.
Detects available slots between START_DATE and END_DATE, sending instant Telegram alerts.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup, Tag

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==============================================================================
# CẤU HÌNH HỆ THỐNG (CONFIGURATION)
# ==============================================================================

DEFAULT_TARGET_URL = "https://edmonton.afedmonton.ca/community/event-rsvp/?event_id=123"
TARGET_URL = os.getenv("TARGET_URL", DEFAULT_TARGET_URL).strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Khoảng thời gian quét (Mặc định: 23/11/2026 đến 15/12/2026)
START_DATE_STR = os.getenv("START_DATE", "2026-11-23").strip()
END_DATE_STR = os.getenv("END_DATE", "2026-12-15").strip()

try:
    START_DATE = datetime.strptime(START_DATE_STR, "%Y-%m-%d").date()
    END_DATE = datetime.strptime(END_DATE_STR, "%Y-%m-%d").date()
except ValueError:
    START_DATE = date(2026, 11, 23)
    END_DATE = date(2026, 12, 15)

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".last_alert.json")
DEDUPLICATION_COOLDOWN_HOURS = 2

# Bảng tra cứu tháng (Tiếng Anh + Tiếng Pháp)
MONTH_MAPPING = {
    # 1. Tháng 1
    "jan": 1, "january": 1, "janv": 1, "janvier": 1,
    # 2. Tháng 2
    "feb": 2, "february": 2, "fev": 2, "fév": 2, "fevr": 2, "févr": 2, "fevrier": 2, "février": 2,
    # 3. Tháng 3
    "mar": 3, "march": 3, "mars": 3,
    # 4. Tháng 4
    "apr": 4, "april": 4, "avr": 4, "avril": 4,
    # 5. Tháng 5
    "may": 5, "mai": 5,
    # 6. Tháng 6
    "jun": 6, "june": 6, "juin": 6,
    # 7. Tháng 7
    "jul": 7, "july": 7, "juil": 7, "juillet": 7,
    # 8. Tháng 8
    "aug": 8, "august": 8, "aout": 8, "août": 8,
    # 9. Tháng 9
    "sep": 9, "sept": 9, "september": 9, "septembre": 9,
    # 10. Tháng 10
    "oct": 10, "october": 10, "octobre": 10,
    # 11. Tháng 11
    "nov": 11, "november": 11, "novembre": 11,
    # 12. Tháng 12
    "dec": 12, "december": 12, "déc": 12, "decembre": 12, "décembre": 12,
}

# ==============================================================================
# HÀM XỬ LÝ NGÀY THÁNG (DATE PARSING)
# ==============================================================================

def extract_date_from_text(text: str) -> Optional[date]:
    """
    Trích xuất ngày tháng năm từ chuỗi văn bản (hỗ trợ cả tiếng Anh và tiếng Pháp).
    Ví dụ:
      - '23 Nov 2026', '23 November 2026', '23 nov. 2026', '23 novembre 2026'
      - 'Nov 23, 2026', 'November 23 2026'
      - '2026-11-23', '23/11/2026'
    """
    if not text:
        return None

    cleaned = text.replace(".", " ").replace(",", " ")

    # Mẫu 1: 23 Nov 2026 hoặc 23 November 2026
    m1 = re.search(r"\b(\d{1,2})\s+([a-zA-ZÀ-ÿ]+)\s+(202\d)\b", cleaned, re.IGNORECASE)
    if m1:
        day_str, month_str, year_str = m1.group(1), m1.group(2).lower(), m1.group(3)
        month = MONTH_MAPPING.get(month_str)
        if month:
            try:
                return date(int(year_str), month, int(day_str))
            except ValueError:
                pass

    # Mẫu 2: Nov 23 2026 hoặc November 23, 2026
    m2 = re.search(r"\b([a-zA-ZÀ-ÿ]+)\s+(\d{1,2})\s+(202\d)\b", cleaned, re.IGNORECASE)
    if m2:
        month_str, day_str, year_str = m2.group(1).lower(), m2.group(2), m2.group(3)
        month = MONTH_MAPPING.get(month_str)
        if month:
            try:
                return date(int(year_str), month, int(day_str))
            except ValueError:
                pass

    # Mẫu 3: 2026-11-23 (ISO)
    m3 = re.search(r"\b(202\d)-(\d{1,2})-(\d{1,2})\b", cleaned)
    if m3:
        try:
            return date(int(m3.group(1)), int(m3.group(2)), int(m3.group(3)))
        except ValueError:
            pass

    # Mẫu 4: 23/11/2026 (DD/MM/YYYY)
    m4 = re.search(r"\b(\d{1,2})/(\d{1,2})/(202\d)\b", cleaned)
    if m4:
        try:
            return date(int(m4.group(3)), int(m4.group(2)), int(m4.group(1)))
        except ValueError:
            pass

    # Mẫu 5: Nếu năm bị lược bỏ (mặc định lấy 2026)
    m5 = re.search(r"\b(\d{1,2})\s+([a-zA-ZÀ-ÿ]+)\b", cleaned, re.IGNORECASE)
    if m5:
        day_str, month_str = m5.group(1), m5.group(2).lower()
        month = MONTH_MAPPING.get(month_str)
        if month:
            try:
                return date(2026, month, int(day_str))
            except ValueError:
                pass

    return None

# ==============================================================================
# HÀM PHÂN TÍCH DOM & BÓC TÁCH SLOT THI
# ==============================================================================

def is_slot_available(spots_text: str, bookings_text: str, action_url: Optional[str]) -> Tuple[bool, str]:
    """
    Đánh giá suất thi có thực sự khả dụng hay không.
    Điều kiện:
      - KHÔNG bị SOLD OUT / COMPLET
      - KHÔNG bị CLOSED / FERMÉ
      - Và CÓ dấu hiệu mở đăng ký: nút/link Register, số chỗ > 0, hoặc chữ Available/Open.
    """
    spots_upper = spots_text.upper()
    bookings_upper = bookings_text.upper()

    # Dấu hiệu hết chỗ
    sold_out_keywords = ["SOLD OUT", "COMPLET", "NO SPOTS", "FULL", "0 SPOTS"]
    is_sold_out = any(kw in spots_upper or kw in bookings_upper for kw in sold_out_keywords)

    # Dấu hiệu đã đóng đăng ký
    closed_keywords = ["CLOSED", "FERMÉ", "FERME", "EXPIRED", "UNAVAILABLE"]
    is_closed = any(kw in bookings_upper for kw in closed_keywords)

    if is_sold_out:
        return False, "SOLD OUT"

    if is_closed:
        return False, "CLOSED"

    # Dấu hiệu còn chỗ / mở đăng ký
    has_action_link = bool(action_url and ("register" in action_url.lower() or "event" in action_url.lower() or "cart" in action_url.lower()))
    has_register_keyword = any(kw in bookings_upper or kw in spots_upper for kw in ["REGISTER", "BOOK", "AVAILABLE", "OPEN", "DISPONIBLE", "S'INSCRIRE"])

    # Kiểm tra số lượng chỗ còn lại (ví dụ "1", "2", "3 spots left")
    spots_num_match = re.search(r"\b(\d+)\s*(spot|seat|chỗ|place)?\b", spots_text, re.IGNORECASE)
    has_spots_count = False
    if spots_num_match:
        try:
            has_spots_count = int(spots_num_match.group(1)) > 0
        except ValueError:
            pass

    if has_action_link or has_register_keyword or has_spots_count:
        return True, f"CÒN CHỖ ({spots_text.strip() or 'Open'})"

    # Nếu không bị sold out và không bị closed nhưng trạng thái mơ hồ, gắn cờ cảnh giác
    if not is_sold_out and not is_closed and (spots_text.strip() or bookings_text.strip()):
        return True, f"KHẢ DỤNG ({spots_text.strip() or bookings_text.strip()})"

    return False, "UNKNOWN / KHÔNG RÕ"

def parse_html_table(html_content: str) -> List[Dict[str, Any]]:
    """
    Bóc tách bảng danh sách kỳ thi từ mã nguồn HTML.
    Hỗ trợ cả cấu trúc <table> chuẩn và các thẻ div/card nếu có.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    found_slots = []

    # 1. Tìm trong tất cả các thẻ <tr> của <table>
    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        row_text = row.get_text(" ", strip=True)

        # Lọc kỳ thi TCF (TCF Canada, TCF IRN, v.v.)
        if "TCF" not in row_text.upper():
            continue

        exam_name = ""
        schedules = ""
        reg_dates = ""
        location = ""
        spots_left = ""
        bookings = ""
        action_url = None

        # Trích xuất link đăng ký nếu có trong thẻ <a>
        link_tag = row.find("a", href=True)
        if link_tag:
            action_url = link_tag["href"]

        if len(cells) >= 4:
            # Cấu trúc bảng tiêu chuẩn:
            # Col 0: Exam, Col 1: Schedules, Col 2: Reg Dates, Col 3: Location (hoặc Spots), Col 4: Bookings
            exam_name = cells[0].get_text(" ", strip=True)
            schedules = cells[1].get_text(" ", strip=True)
            if len(cells) >= 5:
                reg_dates = cells[2].get_text(" ", strip=True)
                spots_left = cells[3].get_text(" ", strip=True)
                bookings = cells[4].get_text(" ", strip=True)
            elif len(cells) == 4:
                spots_left = cells[2].get_text(" ", strip=True)
                bookings = cells[3].get_text(" ", strip=True)
        else:
            # Fallback nếu bảng không chuẩn
            exam_name = row_text[:50]
            schedules = row_text
            spots_left = row_text
            bookings = row_text

        # Trích xuất ngày thi
        exam_date = extract_date_from_text(schedules) or extract_date_from_text(exam_name) or extract_date_from_text(row_text)

        available, status_desc = is_slot_available(spots_left, bookings, action_url)

        found_slots.append({
            "exam_name": exam_name or "TCF Canada",
            "exam_date": exam_date,
            "schedules": schedules or exam_name,
            "location": location or "Alliance Française of Edmonton",
            "spots_left": spots_left,
            "bookings": bookings,
            "action_url": action_url,
            "available": available,
            "status_desc": status_desc,
            "raw_text": row_text
        })

    return found_slots

# ==============================================================================
# HÀM GỬI CẢNH BÁO TELEGRAM (TELEGRAM BOT API)
# ==============================================================================

def send_telegram_alert(message: str, action_url: Optional[str] = None) -> bool:
    """
    Gửi thông báo định dạng HTML qua Telegram Bot API.
    Có đính kèm nút bấm Inline Keyboard mở link đăng ký trực tiếp.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[⚠️ WARNING] Chưa cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID. Bỏ qua gửi tin nhắn.")
        return False

    endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    final_url = action_url or TARGET_URL
    payload: Dict[str, Any] = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "disable_notification": False  # Kích hoạt chuông thông báo trên điện thoại
    }

    # Thêm nút bấm Inline Keyboard để bấm đăng ký ngay
    if final_url and final_url.startswith("http"):
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": "⚡ MỞ LINK ĐĂNG KÝ NGAY", "url": final_url}
                ]
            ]
        }

    try:
        response = requests.post(endpoint, json=payload, timeout=15)
        if response.status_code == 200:
            print("✅ [TELEGRAM] Đã gửi thông báo thành công!")
            return True
        else:
            print(f"❌ [TELEGRAM FAIL] Lỗi từ Telegram API ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ [TELEGRAM ERROR] Ngoại lệ kết nối Telegram: {e}")
        return False

# ==============================================================================
# QUẢN LÝ DEDUPLICATION / TRÁNH SPAM
# ==============================================================================

def should_alert_slot(slot: Dict[str, Any]) -> bool:
    """
    Kiểm tra xem suất thi này đã được gửi cảnh báo gần đây chưa để tránh spam liên tục mỗi 10 phút.
    """
    slot_id = hashlib.md5(f"{slot.get('exam_date')}_{slot.get('schedules')}".encode("utf-8")).hexdigest()
    now_ts = datetime.now().timestamp()

    state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}

    last_ts = state.get(slot_id, 0)
    # Nếu chưa từng gửi hoặc đã quá thời gian cooldown
    if (now_ts - last_ts) > (DEDUPLICATION_COOLDOWN_HOURS * 3600):
        state[slot_id] = now_ts
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except Exception:
            pass
        return True

    return False

# ==============================================================================
# HÀM ĐIỀU PHỐI CHÍNH (MAIN WORKFLOW)
# ==============================================================================

def run_monitor(html_override: Optional[str] = None, dry_run: bool = False, force_alert: bool = False) -> int:
    """
    Hàm thực thi chính:
      1. Tải HTML từ TARGET_URL (hoặc đọc file nếu có override)
      2. Bóc tách dữ liệu bảng
      3. Lọc suất thi nằm trong khoảng START_DATE -> END_DATE
      4. Phát hiện slot còn chỗ và gửi Telegram
    """
    print("=" * 60)
    print("🚀 TCF Canada Edmonton Slot Monitor & Alert Bot")
    print(f"⏰ Thời gian quét: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Mục tiêu: {START_DATE.strftime('%d/%m/%Y')} -> {END_DATE.strftime('%d/%m/%Y')}")
    print("=" * 60)

    # 1. Lấy dữ liệu HTML
    if html_override:
        print(f"📄 [INPUT] Đang đọc HTML từ dữ liệu đầu vào nội bộ...")
        html_content = html_override
    else:
        print(f"🌐 [HTTP] Đang gửi yêu cầu tới: {TARGET_URL}")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
        }
        try:
            response = requests.get(TARGET_URL, headers=headers, timeout=25)
            response.raise_for_status()
            html_content = response.text
            print(f"✅ [HTTP 200] Tải trang thành công ({len(html_content)} bytes)")
        except requests.exceptions.RequestException as e:
            print(f"⚠️ [NETWORK WARNING] Không tải được trang web: {e}")
            print("Ghi nhận cảnh báo, không làm crash CI/CD runner.")
            return 0

    # 2. Bóc tách dữ liệu bảng
    slots = parse_html_table(html_content)
    print(f"📊 Tìm thấy tổng cộng {len(slots)} kỳ thi trong bảng dữ liệu.")

    matching_scope_slots = []
    available_target_slots = []

    for slot in slots:
        ex_date = slot["exam_date"]
        date_str = ex_date.strftime("%d/%m/%Y") if ex_date else "Chưa rõ ngày"

        # Kiểm tra phạm vi ngày
        in_scope = False
        if ex_date:
            in_scope = (START_DATE <= ex_date <= END_DATE)

        if in_scope:
            matching_scope_slots.append(slot)
            print(f"  👉 [PHÙ HỢP NGÀY] {date_str} | Trạng thái: {slot['status_desc']} | Khung giờ: {slot['schedules'][:40]}")
            if slot["available"]:
                available_target_slots.append(slot)
        else:
            status_tag = "MỞ" if slot["available"] else "HẾT"
            # print(f"     [Khác ngày] {date_str} ({status_tag})")

    print("-" * 60)
    print(f"📌 Số kỳ thi trong khung 23/11 - 15/12: {len(matching_scope_slots)}")
    print(f"🔥 Số suất thi CÒN CHỖ khả dụng: {len(available_target_slots)}")

    # 3. Gửi cảnh báo Telegram nếu có suất khả dụng
    if available_target_slots:
        for slot in available_target_slots:
            if not force_alert and not should_alert_slot(slot):
                print(f"ℹ️ Suất thi ngày {slot['exam_date']} đã gửi cảnh báo gần đây, bỏ qua chống spam.")
                continue

            date_str = slot["exam_date"].strftime("%d/%m/%Y") if slot["exam_date"] else "Xem chi tiết"
            message = (
                f"🚨 <b>[TCF CANADA EDMONTON] CÓ SUẤT THI CÒN CHỖ!</b> 🚨\n\n"
                f"📅 <b>Ngày thi:</b> <code>{date_str}</code>\n"
                f"⏰ <b>Lịch trình:</b> {slot['schedules']}\n"
                f"🎟 <b>Số chỗ / Trạng thái:</b> <b>{slot['status_desc']}</b>\n"
                f"📍 <b>Địa điểm:</b> Alliance Française of Edmonton\n"
                f"🕒 <b>Phát hiện lúc:</b> {datetime.now().strftime('%H:%M:%S (%d/%m/%Y)')}\n\n"
                f"⚠️ <i>Lưu ý: Suất thi TCF tại Edmonton thường hết rất nhanh. Hãy nhấp vào liên kết bên dưới để đăng ký ngay!</i>"
            )

            if dry_run:
                print("\n[DRY RUN - NỘI DUNG SẼ GỬI QUA TELEGRAM]:")
                print(message)
                print(f"[Link nút bấm]: {slot['action_url'] or TARGET_URL}\n")
            else:
                send_telegram_alert(message, slot.get("action_url"))

        return 1
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Chưa phát hiện suất thi nào còn chỗ từ {START_DATE.strftime('%d/%m')} đến {END_DATE.strftime('%d/%m')}.")
        return 0

# ==============================================================================
# LỆNH THỰC THI (ENTRY POINT)
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCF Canada Edmonton Slot Monitor")
    parser.add_argument("--dry-run", action="store_true", help="Chạy thử nghiệm không gửi tin nhắn Telegram")
    parser.add_argument("--test-telegram", action="store_true", help="Gửi một tin nhắn kiểm tra tới Telegram để xác nhận cấu hình")
    parser.add_argument("--file", type=str, help="Đọc file HTML local để kiểm thử parser offline")
    parser.add_argument("--force", action="store_true", help="Bỏ qua cơ chế chống spam, gửi cảnh báo ngay nếu còn chỗ")

    args = parser.parse_args()

    if args.test_telegram:
        print("📨 Đang gửi tin nhắn thử nghiệm tới Telegram...")
        test_msg = (
            "🤖 <b>[TEST] TCF Edmonton Monitor Bot đã kết nối thành công!</b>\n\n"
            f"⏰ <b>Thời gian:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🎯 <b>Mục tiêu giám sát:</b> TCF Canada ({START_DATE_STR} đến {END_DATE_STR})\n"
            "✅ <i>Hệ thống thông báo Telegram sẵn sàng hoạt động.</i>"
        )
        success = send_telegram_alert(test_msg)
        sys.exit(0 if success else 1)

    html_data = None
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            html_data = f.read()

    run_monitor(html_override=html_data, dry_run=args.dry_run, force_alert=args.force)
