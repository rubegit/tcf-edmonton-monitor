import unittest
from datetime import date
from monitor import extract_date_from_text, is_slot_available, parse_html_table

class TestTcfMonitor(unittest.TestCase):

    def test_extract_date_english(self):
        self.assertEqual(extract_date_from_text("Monday 23 Nov 2026 - 9:20am▸12:20pm"), date(2026, 11, 23))
        self.assertEqual(extract_date_from_text("TCF Canada - November 23 2026"), date(2026, 11, 23))
        self.assertEqual(extract_date_from_text("Wednesday 02 Dec 2026"), date(2026, 12, 2))
        self.assertEqual(extract_date_from_text("15 December 2026"), date(2026, 12, 15))

    def test_extract_date_french(self):
        self.assertEqual(extract_date_from_text("Lundi 23 novembre 2026"), date(2026, 11, 23))
        self.assertEqual(extract_date_from_text("Mercredi 02 déc 2026"), date(2026, 12, 2))
        self.assertEqual(extract_date_from_text("15 décembre 2026"), date(2026, 12, 15))

    def test_extract_date_numeric(self):
        self.assertEqual(extract_date_from_text("Session: 2026-11-23"), date(2026, 11, 23))
        self.assertEqual(extract_date_from_text("Date: 23/11/2026"), date(2026, 11, 23))

    def test_availability_logic_fixes_original_spec_bug(self):
        # BUG trong code mẫu ban đầu: Nếu Spots = SOLD OUT nhưng Bookings != CLOSED, nó vẫn báo True.
        # Với hàm mới, trường hợp này BẮT BUỘC phải là False.
        avail, reason = is_slot_available("SOLD OUT!", "Register", None)
        self.assertFalse(avail, "SOLD OUT không bao giờ được coi là khả dụng!")

        avail, reason = is_slot_available("SOLD OUT!", "Closed", None)
        self.assertFalse(avail)

        avail, reason = is_slot_available("Available", "CLOSED", None)
        self.assertFalse(avail, "CLOSED không bao giờ được coi là khả dụng!")

    def test_availability_detection_success(self):
        avail, reason = is_slot_available("2 spots left", "Register", "https://edmonton.afedmonton.ca/cart")
        self.assertTrue(avail)
        self.assertIn("CÒN CHỖ", reason)

        avail, reason = is_slot_available("Open", "Available", None)
        self.assertTrue(avail)

    def test_html_table_parsing(self):
        sample_html = """
        <html>
        <body>
            <table class="exam-list">
                <thead>
                    <tr>
                        <th>Exam</th><th>Schedules</th><th>Registration Dates</th><th>Spots left</th><th>Bookings</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Hàng 1: Ngoài phạm vi ngày (10/10/2026) -->
                    <tr>
                        <td>TCF Canada - October 10</td>
                        <td>Saturday 10 Oct 2026</td>
                        <td>Until 01 Oct 2026</td>
                        <td>SOLD OUT!</td>
                        <td>Closed</td>
                    </tr>
                    <!-- Hàng 2: Trong phạm vi (23/11/2026) nhưng SOLD OUT -->
                    <tr>
                        <td>TCF Canada - November 23</td>
                        <td>Monday 23 Nov 2026 - 9:20am</td>
                        <td>Until 10 Nov 2026</td>
                        <td>SOLD OUT!</td>
                        <td>Closed</td>
                    </tr>
                    <!-- Hàng 3: Trong phạm vi (02/12/2026) và CÒN CHỖ! -->
                    <tr>
                        <td>TCF Canada - December 02</td>
                        <td>Wednesday 02 Dec 2026 - 9:20am</td>
                        <td>Until 20 Nov 2026</td>
                        <td>2 spots left</td>
                        <td><a href="https://edmonton.afedmonton.ca/community/event-rsvp/?event_id=999">Register</a></td>
                    </tr>
                </tbody>
            </table>
        </body>
        </html>
        """
        slots = parse_html_table(sample_html)
        self.assertEqual(len(slots), 3)

        # Slot 1: Out of range
        self.assertEqual(slots[0]["exam_date"], date(2026, 10, 10))
        self.assertFalse(slots[0]["available"])

        # Slot 2: In range but SOLD OUT
        self.assertEqual(slots[1]["exam_date"], date(2026, 11, 23))
        self.assertFalse(slots[1]["available"])

        # Slot 3: In range and AVAILABLE!
        self.assertEqual(slots[2]["exam_date"], date(2026, 12, 2))
        self.assertTrue(slots[2]["available"])
        self.assertEqual(slots[2]["action_url"], "https://edmonton.afedmonton.ca/community/event-rsvp/?event_id=999")

if __name__ == "__main__":
    unittest.main()
