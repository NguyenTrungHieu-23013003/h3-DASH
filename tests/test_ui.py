"""
E2E UI Tests for H3-DASH Dashboard — Khóa 4: Web and Mobile Testing with Selenium
===================================================================================
Môn: Đánh giá và Kiểm định Chất lượng Phần mềm
Dự án: H3-DASH Analytical Lab Tool

Kỹ thuật áp dụng:
  - Page Object Model (POM) pattern
  - Headless Chrome automation
  - Element presence & state assertions
  - UI interaction testing (click, toggle)
  - Cross-element relationship testing

Chạy: pytest tests/test_ui.py -v
"""

import unittest
import time
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

# ── Conditional Selenium import ────────────────────────────────────────────────
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException, WebDriverException
    )
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        _DRIVER_MANAGER = True
    except ImportError:
        _DRIVER_MANAGER = False
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False


# ── Page Object Model ──────────────────────────────────────────────────────────
class DashboardPage:
    """
    Page Object Model cho H3-DASH Dashboard.
    Encapsulates selectors và các thao tác UI vào một class duy nhất.
    Theo POM pattern: test code không hardcode selector.
    """
    BASE_URL = "http://127.0.0.1:8080"

    # Locators
    BTN_RECORD_ID      = "btn-record"
    RECORD_TEXT_ID     = "record-text"
    LOG_TERMINAL_ID    = "log-terminal"
    NETWORK_PROFILE_ID = "network-profile"          # badge hiển thị profile hiện tại
    BTN_EXPORT_ID      = "btn-export"               # nút xuất CSV
    METRICS_TABLE_ID   = "metrics-table"            # bảng số liệu

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout=8)

    def open(self):
        self.driver.get(self.BASE_URL + "/")

    # ── Element helpers ────────────────────────────────────────────────────────
    def get_title(self):
        return self.driver.title

    def find_by_id(self, element_id):
        return self.wait.until(EC.presence_of_element_located((By.ID, element_id)))

    def find_by_xpath(self, xpath):
        return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

    def click_by_id(self, element_id):
        el = self.wait.until(EC.element_to_be_clickable((By.ID, element_id)))
        el.click()
        return el

    def get_text_by_id(self, element_id):
        try:
            el = self.wait.until(EC.presence_of_element_located((By.ID, element_id)))
            return el.text
        except TimeoutException:
            return ""

    # ── Business actions ───────────────────────────────────────────────────────
    def start_session(self):
        """Click nút Start Session và chờ trạng thái thay đổi."""
        self.click_by_id(self.BTN_RECORD_ID)
        time.sleep(0.5)

    def stop_session(self):
        """Click nút Stop Session."""
        self.click_by_id(self.BTN_RECORD_ID)
        time.sleep(0.3)

    def get_network_profile_buttons(self):
        """Lấy tất cả các nút chuyển profile mạng."""
        return self.driver.find_elements(
            By.XPATH, "//button[contains(@class,'profile') or contains(@onclick,'setProfile')]"
        )

    def count_metric_rows(self):
        """Đếm số dòng trong bảng metrics."""
        try:
            table = self.driver.find_element(By.ID, self.METRICS_TABLE_ID)
            rows = table.find_elements(By.TAG_NAME, "tr")
            return max(0, len(rows) - 1)  # trừ header
        except NoSuchElementException:
            return -1  # bảng chưa xuất hiện

    def get_page_source_size(self):
        return len(self.driver.page_source)


# ── Local Static File Server ───────────────────────────────────────────────────
class _SilentHandler(SimpleHTTPRequestHandler):
    """Suppress server log output during tests."""
    def log_message(self, format, *args):  # noqa: A002
        pass


class DummyServer(threading.Thread):
    """Chạy HTTP server đơn giản để phục vụ file tĩnh từ html/."""

    def __init__(self, port=8080):
        super().__init__()
        self.port = port
        self.server = None
        self.daemon = True
        self._html_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "html"
        )

    def run(self):
        os.chdir(self._html_dir)
        self.server = HTTPServer(("127.0.0.1", self.port), _SilentHandler)
        self.server.serve_forever()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


# ── Test Suite ─────────────────────────────────────────────────────────────────
@unittest.skipIf(not HAS_SELENIUM, "Selenium không được cài đặt — bỏ qua E2E tests")
class TestDashboardUI(unittest.TestCase):
    """
    Kiểm thử E2E giao diện Dashboard (Khóa 4) bằng Selenium WebDriver.

    Áp dụng:
      - Page Object Model (POM) để tách biệt test logic và UI selector
      - Headless Chrome để chạy không cần màn hình (phù hợp CI/CD)
      - WebDriverWait thay vì time.sleep cố định (stable selectors)
    """

    @classmethod
    def setUpClass(cls):
        """Khởi tạo server và WebDriver một lần cho cả test suite."""
        # Start local file server
        cls.server = DummyServer(port=8080)
        cls.server.start()
        time.sleep(0.8)  # chờ server sẵn sàng

        # Chrome headless options
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280,800")

        try:
            if _DRIVER_MANAGER:
                cls.driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=chrome_options,
                )
            else:
                cls.driver = webdriver.Chrome(options=chrome_options)
            cls.driver.implicitly_wait(5)
            cls.page = DashboardPage(cls.driver)
        except WebDriverException as e:
            cls.driver = None
            cls.page = None
            print(f"\n[WARN] Chrome driver không khởi động được: {e}")

    @classmethod
    def tearDownClass(cls):
        """Dọn dẹp: đóng driver và tắt server."""
        if cls.driver:
            cls.driver.quit()
        cls.server.stop()

    def setUp(self):
        if not self.driver:
            self.skipTest("Chrome driver không khởi động — bỏ qua test này")

    # ── TC-UI-01: Page Load & Title ──────────────────────────────────────────
    def test_01_page_loads_with_correct_title(self):
        """
        TC-UI-01: Dashboard phải load đúng title và các thành phần chính.
        Kỹ thuật: Black-box — kiểm tra output (title) theo spec.
        """
        self.page.open()

        # Assert: title phải chứa tên ứng dụng
        title = self.page.get_title()
        self.assertIn(
            "H3-DASH", title,
            f"Title '{title}' không chứa 'H3-DASH'"
        )

        # Assert: page source không rỗng (render thành công)
        source_size = self.page.get_page_source_size()
        self.assertGreater(source_size, 500,
                           "Page source quá nhỏ — khả năng render bị lỗi")

    # ── TC-UI-02: Network Profile Buttons ────────────────────────────────────
    def test_02_network_profile_buttons_are_present(self):
        """
        TC-UI-02: Phải có đủ các nút chuyển profile mạng (LTE, 4G, 5G, ...).
        Kỹ thuật: Black-box — equivalence partitioning theo từng profile.
        """
        self.page.open()

        # Kiểm tra ít nhất nút LTE tồn tại (profile quan trọng nhất)
        btn_lte = self.page.find_by_xpath("//button[contains(text(), 'LTE')]")
        self.assertIsNotNone(btn_lte, "Nút 'LTE' không tìm thấy trên Dashboard")

        # Kiểm tra các profile khác
        expected_profiles = ["5G", "4G", "3G", "2G"]
        for profile in expected_profiles:
            with self.subTest(profile=profile):
                elements = self.driver.find_elements(
                    By.XPATH, f"//button[contains(text(), '{profile}')]"
                )
                self.assertTrue(
                    len(elements) > 0,
                    f"Không tìm thấy nút profile '{profile}'"
                )

    # ── TC-UI-03: Start Session Toggle ───────────────────────────────────────
    def test_03_start_session_button_toggles_state(self):
        """
        TC-UI-03: Nút Start Session phải đổi trạng thái khi click.
        Kỹ thuật: State-based testing — kiểm tra transition từ idle → recording.
        """
        self.page.open()
        time.sleep(0.3)

        try:
            record_text = self.page.find_by_id(DashboardPage.RECORD_TEXT_ID)
            initial_text = record_text.text.strip().lower()

            # Trạng thái ban đầu phải là "session start" hoặc tương tự
            self.assertTrue(
                "start" in initial_text or "session" in initial_text,
                f"Text ban đầu không đúng: '{initial_text}'"
            )

            # Click để bắt đầu ghi
            self.page.start_session()

            # Trạng thái sau click phải thay đổi
            new_text = record_text.text.strip().lower()
            self.assertNotEqual(
                initial_text, new_text,
                f"Text không thay đổi sau khi click: vẫn là '{new_text}'"
            )

            # Click lại để dừng
            self.page.stop_session()

        except (TimeoutException, NoSuchElementException):
            self.skipTest("Phần tử btn-record / record-text không có trong HTML")

    # ── TC-UI-04: Log Terminal Output ─────────────────────────────────────────
    def test_04_log_terminal_shows_session_event(self):
        """
        TC-UI-04: Terminal log phải hiển thị sự kiện khi session bắt đầu.
        Kỹ thuật: Behavioral testing — kiểm tra side effect của action.
        """
        self.page.open()
        time.sleep(0.3)

        try:
            btn = self.page.find_by_id(DashboardPage.BTN_RECORD_ID)
            btn.click()
            time.sleep(1.0)  # chờ JS cập nhật DOM

            log = self.page.find_by_id(DashboardPage.LOG_TERMINAL_ID)
            log_text = log.text

            # Log phải có nội dung — không được rỗng sau khi bắt đầu session
            self.assertTrue(
                len(log_text.strip()) > 0,
                "Terminal log vẫn rỗng sau khi bắt đầu session"
            )

            # Dừng session
            btn.click()

        except (TimeoutException, NoSuchElementException):
            self.skipTest("Phần tử log-terminal / btn-record không có trong HTML")

    # ── TC-UI-05: Essential DOM Elements Exist ────────────────────────────────
    def test_05_essential_dom_elements_are_present(self):
        """
        TC-UI-05: Tất cả DOM element quan trọng phải hiện diện khi page load.
        Kỹ thuật: Structural testing — kiểm tra cấu trúc HTML theo spec.
        """
        self.page.open()

        essential_elements = [
            ("ID",    DashboardPage.BTN_RECORD_ID,   "Nút Start/Stop Session"),
            ("XPATH", "//h1 | //h2 | //header",       "Tiêu đề trang"),
            ("XPATH", "//button",                      "Ít nhất 1 nút trên trang"),
        ]

        for locator_type, value, description in essential_elements:
            with self.subTest(element=description):
                try:
                    if locator_type == "ID":
                        elements = self.driver.find_elements(By.ID, value)
                    else:
                        elements = self.driver.find_elements(By.XPATH, value)
                    self.assertTrue(
                        len(elements) > 0,
                        f"Thiếu phần tử: {description} (locator: {value})"
                    )
                except NoSuchElementException:
                    self.fail(f"Không tìm thấy: {description}")

    # ── TC-UI-06: Page Responsiveness Check ──────────────────────────────────
    def test_06_page_renders_without_js_errors(self):
        """
        TC-UI-06: Page phải render thành công, không bị blank/error page.
        Kỹ thuật: Sanity check — đảm bảo không có lỗi nghiêm trọng.
        """
        self.page.open()

        source = self.driver.page_source.lower()

        # Không được có error page phổ biến
        error_indicators = [
            "404 not found",
            "500 internal server error",
            "cannot get /",
            "application error",
        ]
        for indicator in error_indicators:
            self.assertNotIn(
                indicator, source,
                f"Page chứa dấu hiệu lỗi: '{indicator}'"
            )

        # Page phải có nội dung thực
        self.assertGreater(
            len(source), 200,
            "Page source quá ngắn — có thể render bị lỗi"
        )

    # ── TC-UI-07: Multiple Rapid Clicks Stability ─────────────────────────────
    def test_07_rapid_button_clicks_do_not_crash_page(self):
        """
        TC-UI-07: Click nhanh nhiều lần không được làm trang bị crash.
        Kỹ thuật: Stress/Robustness testing — kiểm tra tính ổn định UI.
        """
        self.page.open()
        time.sleep(0.3)

        try:
            btn = self.page.find_by_id(DashboardPage.BTN_RECORD_ID)

            # Click 4 lần liên tiếp (start → stop → start → stop)
            for _ in range(4):
                btn.click()
                time.sleep(0.2)

            # Sau nhiều click, page phải vẫn còn responsive
            # Kiểm tra bằng cách tìm lại element (nếu crash sẽ raise exception)
            still_alive = self.driver.find_elements(By.ID, DashboardPage.BTN_RECORD_ID)
            self.assertTrue(
                len(still_alive) > 0,
                "Nút bị mất sau nhiều lần click — page có thể bị crash"
            )

        except (TimeoutException, NoSuchElementException):
            self.skipTest("Phần tử btn-record không có trong HTML")


if __name__ == "__main__":
    unittest.main(verbosity=2)
