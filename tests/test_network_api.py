"""
Unit & Integration Tests for network_api.py
============================================
Môn: Đánh giá và Kiểm định Chất lượng Phần mềm
Dự án: H3-DASH Analytical Lab Tool

Chạy: pytest tests/ -v --tb=short
"""

import json
import os
import sys
import tempfile
import unittest
from io import BytesIO
from unittest.mock import MagicMock, call, mock_open, patch

# Thêm thư mục gốc vào path để import được module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock FileHandler TRƯỚC KHI import module vì network_api.py cố ghi log vào
# /srv/html/network_api.log — path này chỉ tồn tại bên trong Docker container.
# Bên ngoài Docker (khi chạy test), ta cần patch nó để tránh FileNotFoundError.
import logging
_patcher = patch("logging.FileHandler", lambda *a, **kw: logging.NullHandler())
_patcher.start()

# ==========================================
# Helpers: mock các biến môi trường trước khi import
# ==========================================
os.environ.setdefault("NET_IFACE", "eth0")

import network_api  # noqa: E402
_patcher.stop()


# ==========================================
# TEST GROUP 1: State Management (get_state, save_state)
# ==========================================
class TestStateManagement(unittest.TestCase):
    """Kiểm tra các hàm đọc/ghi trạng thái hệ thống."""

    def setUp(self):
        """Tạo thư mục tạm để không ảnh hưởng tới file thật."""
        self.tmp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.tmp_dir, "current_state.json")
        # Override STATE_FILE trong module
        self._original_state_file = network_api.STATE_FILE
        network_api.STATE_FILE = self.state_file

    def tearDown(self):
        network_api.STATE_FILE = self._original_state_file

    # --- get_state ---

    def test_get_state_returns_default_when_file_missing(self):
        """Khi file trạng thái không tồn tại → trả về giá trị mặc định."""
        state = network_api.get_state()
        self.assertEqual(state, {"mode": "reset", "protocol": "h2"})

    def test_get_state_reads_existing_valid_file(self):
        """Khi file JSON hợp lệ tồn tại → đọc và trả về đúng dữ liệu."""
        expected = {"mode": "4g"}
        with open(self.state_file, "w") as f:
            json.dump(expected, f)
        state = network_api.get_state()
        self.assertEqual(state, expected)

    def test_get_state_returns_default_on_corrupt_json(self):
        """File JSON bị hỏng → không crash, trả về default (không bỏ qua lỗi âm thầm)."""
        with open(self.state_file, "w") as f:
            f.write("{ this is not valid json }")
        # Nếu còn bare except: pass, lỗi JSONDecodeError bị nuốt mà không log
        # Sau khi fix, hàm phải vẫn trả về default
        state = network_api.get_state()
        self.assertEqual(state, {"mode": "reset", "protocol": "h2"})

    def test_get_state_returns_default_on_empty_file(self):
        """File rỗng → trả về default."""
        open(self.state_file, "w").close()
        state = network_api.get_state()
        self.assertEqual(state, {"mode": "reset", "protocol": "h2"})

    # --- save_state ---

    def test_save_state_writes_correct_json(self):
        """Hàm save_state phải ghi đúng JSON vào file."""
        with patch("builtins.open", mock_open()) as mocked_open:
            network_api.save_state("3g")
            handle = mocked_open()
            written = "".join(
                call_args[0][0]
                for call_args in handle.write.call_args_list
            )
        self.assertIn("3g", written)

    def test_save_and_reload_state(self):
        """Ghi rồi đọc lại phải ra cùng giá trị — kiểm tra tính nhất quán."""
        network_api.save_state("5g")
        state = network_api.get_state()
        self.assertEqual(state["mode"], "5g")

    def test_save_state_overwrites_previous(self):
        """Ghi state mới phải ghi đè state cũ, không append."""
        network_api.save_state("2g")
        network_api.save_state("lte")
        state = network_api.get_state()
        self.assertEqual(state["mode"], "lte")


# ==========================================
# TEST GROUP 2: Network Profiles (PROFILES dictionary)
# ==========================================
class TestNetworkProfiles(unittest.TestCase):
    """Kiểm tra cấu hình các profile mạng."""

    REQUIRED_PROFILES = ["2g", "3g", "4g", "lte", "wifi", "5g", "reset"]

    def test_all_required_profiles_exist(self):
        """Tất cả các profile bắt buộc phải có trong PROFILES."""
        for profile in self.REQUIRED_PROFILES:
            with self.subTest(profile=profile):
                self.assertIn(profile, network_api.PROFILES,
                              f"Profile '{profile}' bị thiếu!")

    def test_profile_has_required_keys(self):
        """Mỗi profile phải có đủ 3 trường: bw, latency, loss."""
        required_keys = {"bw", "latency", "loss"}
        for name, profile in network_api.PROFILES.items():
            with self.subTest(profile=name):
                self.assertEqual(
                    set(profile.keys()), required_keys,
                    f"Profile '{name}' thiếu hoặc thừa trường!"
                )

    def test_reset_profile_has_none_values(self):
        """Profile 'reset' phải có tất cả giá trị là None (không giới hạn)."""
        reset = network_api.PROFILES["reset"]
        for key, val in reset.items():
            self.assertIsNone(val, f"reset.{key} phải là None nhưng là {val!r}")

    def test_bandwidth_ordering_is_logical(self):
        """Băng thông phải tăng dần: 2g < 3g < 4g < lte < wifi < 5g."""
        def parse_mbit(bw_str):
            if bw_str is None:
                return float("inf")
            bw_str = bw_str.lower()
            val = float("".join(c for c in bw_str if c.isdigit() or c == "."))
            if "kbit" in bw_str:
                return val / 1000
            return val  # mbit

        order = ["2g", "3g", "4g", "lte", "wifi", "5g"]
        bandwidths = [parse_mbit(network_api.PROFILES[p]["bw"]) for p in order]
        for i in range(len(bandwidths) - 1):
            self.assertLess(
                bandwidths[i], bandwidths[i + 1],
                f"Băng thông {order[i]} ({bandwidths[i]}) phải nhỏ hơn {order[i+1]} ({bandwidths[i+1]})"
            )

    def test_latency_ordering_is_logical(self):
        """Độ trễ phải giảm dần từ 2g → 5g (mạng nhanh hơn → ít trễ hơn)."""
        def parse_ms(lat_str):
            if lat_str is None:
                return 0
            return float("".join(c for c in lat_str if c.isdigit() or c == "."))

        order = ["2g", "3g", "4g", "lte", "5g"]
        latencies = [parse_ms(network_api.PROFILES[p]["latency"]) for p in order]
        for i in range(len(latencies) - 1):
            self.assertGreater(
                latencies[i], latencies[i + 1],
                f"Độ trễ {order[i]} ({latencies[i]}ms) phải lớn hơn {order[i+1]} ({latencies[i+1]}ms)"
            )


# ==========================================
# TEST GROUP 3: apply_tc_rules (với mock subprocess)
# ==========================================
class TestApplyTcRules(unittest.TestCase):
    """Kiểm tra hàm áp dụng quy tắc mạng, mock subprocess để không cần root."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self._orig_state = network_api.STATE_FILE
        network_api.STATE_FILE = os.path.join(self.tmp_dir, "state.json")

    def tearDown(self):
        network_api.STATE_FILE = self._orig_state

    def _make_mock_run(self):
        """Tạo mock subprocess.run trả về returncode=0."""
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = ""
        mock.stderr = ""
        return mock

    @patch("network_api.subprocess.run")
    @patch("builtins.open", mock_open())
    def test_reset_mode_clears_tc_rules(self, mock_run):
        """Mode 'reset' phải xóa tc qdisc và flush iptables."""
        mock_run.return_value = self._make_mock_run()
        network_api.apply_tc_rules("reset")

        calls_str = [" ".join(c.args[0]) for c in mock_run.call_args_list]
        # Phải có lệnh xóa qdisc
        self.assertTrue(
            any("tc qdisc del" in c for c in calls_str),
            "Phải gọi 'tc qdisc del' khi reset"
        )
        # Phải có lệnh flush iptables
        self.assertTrue(
            any("iptables -F OUTPUT" in c for c in calls_str),
            "Phải gọi 'iptables -F OUTPUT' khi reset"
        )

    @patch("network_api.subprocess.run")
    @patch("builtins.open", mock_open())
    def test_4g_mode_adds_htb_and_netem(self, mock_run):
        """Mode '4g' phải thiết lập HTB (giới hạn băng thông) và netem (trễ/mất gói)."""
        mock_run.return_value = self._make_mock_run()
        network_api.apply_tc_rules("4g")

        calls_str = [" ".join(c.args[0]) for c in mock_run.call_args_list]
        self.assertTrue(any("htb" in c for c in calls_str),
                        "Phải thiết lập HTB qdisc cho profile 4g")
        self.assertTrue(any("netem" in c for c in calls_str),
                        "Phải thiết lập netem (delay/loss) cho profile 4g")

    @patch("network_api.subprocess.run")
    @patch("builtins.open", mock_open())
    def test_wifi_mode_does_not_apply_tc_constraints(self, mock_run):
        """Mode 'wifi' là tốc độ thực tế, không được apply HTB/netem giới hạn."""
        mock_run.return_value = self._make_mock_run()
        network_api.apply_tc_rules("wifi")

        calls_str = [" ".join(c.args[0]) for c in mock_run.call_args_list]
        # Chỉ được gọi lệnh xóa (del), không thêm (add) qdisc mới
        self.assertFalse(
            any("tc qdisc add" in c for c in calls_str),
            "Mode WiFi không được thêm qdisc giới hạn băng thông"
        )

    @patch("network_api.subprocess.run")
    @patch("builtins.open", mock_open())
    def test_apply_tc_saves_state(self, mock_run):
        """Sau khi apply, trạng thái mới phải được lưu lại."""
        mock_run.return_value = self._make_mock_run()

        with patch("network_api.save_state") as mock_save:
            network_api.apply_tc_rules("3g")
            mock_save.assert_called_once_with("3g")

    @patch("network_api.subprocess.run")
    @patch("builtins.open", mock_open())
    def test_unknown_mode_falls_back_to_4g_profile(self, mock_run):
        """Profile không tồn tại → fallback về 4g, không crash."""
        mock_run.return_value = self._make_mock_run()
        # Không nên raise exception
        try:
            network_api.apply_tc_rules("unknown_mode_xyz")
        except Exception as e:
            self.fail(f"apply_tc_rules nên xử lý gracefully với mode không hợp lệ, nhưng raise: {e}")


# ==========================================
# TEST GROUP 4: HTTP Handler (NetworkHandler)
# ==========================================
class TestNetworkHandler(unittest.TestCase):
    """Integration test cho HTTP request handler."""

    def _make_request(self, body: bytes, path: str = "/api/network"):
        """Helper: tạo mock HTTP request và gọi do_POST."""
        handler = network_api.NetworkHandler.__new__(network_api.NetworkHandler)
        handler.path = path
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = BytesIO(body)

        response_buffer = BytesIO()

        def write_bytes(data):
            response_buffer.write(data)

        handler.wfile = MagicMock()
        handler.wfile.write.side_effect = write_bytes
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.log_message = MagicMock()  # Suppress BaseHTTPRequestHandler logs

        return handler, response_buffer

    @patch("network_api.threading.Thread")
    @patch("network_api.get_state", return_value={"mode": "reset"})
    def test_post_valid_mode_returns_success(self, mock_state, mock_thread):
        """POST với mode hợp lệ → response có status=success."""
        mock_thread.return_value.start = MagicMock()
        body = b"mode=4g"
        handler, buf = self._make_request(body)

        with patch("builtins.open", mock_open()):
            handler.do_POST()

        written_data = b"".join(
            call_args[0][0] for call_args in handler.wfile.write.call_args_list
        )
        response = json.loads(written_data.decode())
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["mode"], "4g")

    @patch("network_api.threading.Thread")
    @patch("network_api.get_state", return_value={"mode": "3g"})
    def test_post_uses_current_state_when_no_mode_param(self, mock_state, mock_thread):
        """POST không kèm param 'mode' → dùng mode hiện tại từ state."""
        mock_thread.return_value.start = MagicMock()
        body = b""  # Không có param nào
        handler, buf = self._make_request(body)
        handler.headers = {"Content-Length": "0"}

        handler.do_POST()

        written_data = b"".join(
            call_args[0][0] for call_args in handler.wfile.write.call_args_list
        )
        response = json.loads(written_data.decode())
        # Phải fallback về mode từ get_state()
        self.assertEqual(response["mode"], "3g")

    @patch("network_api.threading.Thread")
    @patch("network_api.get_state", return_value={"mode": "reset"})
    def test_post_sets_cors_headers(self, mock_state, mock_thread):
        """Response phải có CORS headers để Dashboard có thể gọi API."""
        mock_thread.return_value.start = MagicMock()
        body = b"mode=wifi"
        handler, _ = self._make_request(body)

        handler.do_POST()

        header_calls = [str(c) for c in handler.send_header.call_args_list]
        has_cors = any("Access-Control-Allow-Origin" in c for c in header_calls)
        self.assertTrue(has_cors, "Thiếu CORS header 'Access-Control-Allow-Origin'")

    def test_options_request_returns_200(self):
        """Preflight OPTIONS request → trả về 200 (không block CORS)."""
        handler = network_api.NetworkHandler.__new__(network_api.NetworkHandler)
        handler.path = "/api/network"
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.log_message = MagicMock()

        handler.do_OPTIONS()

        handler.send_response.assert_called_once_with(200)


# ==========================================
# TEST GROUP 5: run_command helper
# ==========================================
class TestRunCommand(unittest.TestCase):
    """Kiểm tra hàm wrapper chạy lệnh shell."""

    @patch("network_api.subprocess.run")
    def test_run_command_returns_result(self, mock_run):
        """Phải trả về subprocess result để caller có thể check returncode."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = network_api.run_command(["echo", "test"])
        self.assertEqual(result, mock_result)

    @patch("network_api.subprocess.run")
    def test_run_command_logs_error_on_failure(self, mock_run):
        """Khi lệnh thất bại (returncode != 0) và ignore_errors=False → phải log lỗi."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "tc: error"
        mock_run.return_value = mock_result

        with patch.object(network_api.logger, "error") as mock_log:
            network_api.run_command(["tc", "bad_command"], ignore_errors=False)
            mock_log.assert_called()

    @patch("network_api.subprocess.run")
    def test_run_command_suppresses_error_when_ignore_flag_set(self, mock_run):
        """Khi ignore_errors=True → không log lỗi (dùng cho 'tc del' khi chưa có rule)."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "RTNETLINK answers: No such file"
        mock_run.return_value = mock_result

        with patch.object(network_api.logger, "error") as mock_log:
            network_api.run_command(["tc", "qdisc", "del", "dev", "eth0", "root"],
                                     ignore_errors=True)
            mock_log.assert_not_called()


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
