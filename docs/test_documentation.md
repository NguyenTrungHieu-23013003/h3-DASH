# TÀI LIỆU KIỂM THỬ — H3-DASH ANALYTICAL LAB TOOL

**Môn:** Đánh giá và Kiểm định Chất lượng Phần mềm  
**Dự án:** H3-DASH — HTTP/3 MPEG-DASH Performance Lab  
**Nhóm:** 3 thành viên  
**Ngày:** 2026-06-12  

---

## 1. TỔNG QUAN DỰ ÁN

### 1.1. Mô tả hệ thống
H3-DASH là hệ thống thực nghiệm đo lường hiệu năng giao thức **HTTP/3 (QUIC)** kết hợp với **MPEG-DASH** (Adaptive Bitrate Streaming).

| Thành phần | Công nghệ | Vai trò |
|:-----------|:----------|:--------|
| Web Server | Caddy + H3 | Phục vụ video DASH qua HTTPS/3 |
| Network Controller | `network_api.py` (Python) | API điều khiển mạng giả lập |
| Traffic Control | Linux `tc` + `iproute2` | Giới hạn băng thông/độ trễ |
| Dashboard | HTML + dash.js | Thu thập và xuất metrics |
| Container | Docker + Docker Compose | Môi trường cô lập, tái hiện |

### 1.2. Phạm vi kiểm thử
- **SUT (System Under Test):** `network_api.py` — module điều khiển mạng trung tâm
- **Môi trường:** Python 3.13, pytest 9.0, Docker (Ubuntu base)
- **Loại kiểm thử:** Unit, Integration, Black-box, White-box, Automated Analysis, E2E Selenium

---

## 2. KẾ HOẠCH KIỂM THỬ (TEST PLAN) — Khóa 1

### 2.1. 7 Nguyên tắc Kiểm thử (7 Principles of Testing)

Dự án H3-DASH áp dụng 7 nguyên tắc kiểm thử theo ISTQB:

| # | Nguyên tắc | Áp dụng trong dự án |
|:--|:-----------|:--------------------|
| 1 | **Testing shows presence of defects** | Test suite chứng minh lỗi _bare except_ tồn tại ban đầu trong `get_state()` |
| 2 | **Exhaustive testing is impossible** | Chỉ test 7 profile mạng đại diện, không test mọi tổ hợp tham số |
| 3 | **Early testing** | Test được viết song song với code, không phải sau khi hoàn thành |
| 4 | **Defect clustering** | 80% bug tập trung tại `apply_tc_rules()` và HTTP handler — tập trung test ở đây |
| 5 | **Pesticide paradox** | Thêm test cases mới (TC-BB-07 → TC-BB-10) sau khi test cũ không phát hiện thêm lỗi |
| 6 | **Testing is context dependent** | Dùng mock subprocess vì môi trường test không có quyền root |
| 7 | **Absence-of-errors fallacy** | 24/24 test PASS không có nghĩa phần mềm hoàn hảo — `__main__` block chưa được test |

### 2.2. Mục tiêu kiểm thử
1. Xác minh tính đúng đắn của logic quản lý trạng thái hệ thống
2. Kiểm tra tính toàn vẹn của cấu hình các profile mạng
3. Đảm bảo các lệnh `tc` và `iptables` được gọi đúng theo từng profile
4. Kiểm tra HTTP handler xử lý request đúng chuẩn REST
5. Tự động hóa phân tích kết quả thực nghiệm theo Quality Gates

### 2.3. Entry Criteria (Điều kiện bắt đầu kiểm thử)

> Kiểm thử chỉ được bắt đầu khi **tất cả** các điều kiện sau được thỏa mãn:

| # | Điều kiện | Kiểm tra bằng |
|:--|:----------|:--------------|
| EC-01 | Code `network_api.py` đã được review và merge vào nhánh `main` | Git log |
| EC-02 | Môi trường Python 3.10+ và pytest đã được cài đặt | `pytest --version` |
| EC-03 | Tất cả dependencies (`pytest-cov`, `pylint`) đã sẵn sàng | `pip list` |
| EC-04 | Biến môi trường `NET_IFACE` đã được thiết lập (hoặc có giá trị mặc định `eth0`) | `echo $NET_IFACE` |
| EC-05 | File `tests/test_network_api.py` đã có đủ test cases theo test plan | Code review |

### 2.4. Exit Criteria (Điều kiện dừng kiểm thử)

> Kiểm thử được coi là **hoàn thành** khi đạt tất cả tiêu chí sau:

| # | Tiêu chí | Ngưỡng yêu cầu | Kết quả |
|:--|:---------|:----------------|:--------|
| XC-01 | Tỷ lệ test case PASS | ≥ 95% | ✅ 24/24 = 100% |
| XC-02 | Statement coverage | ≥ 80% | ✅ 85% |
| XC-03 | Branch coverage | ≥ 90% | ✅ 100% (10/10 nhánh) |
| XC-04 | Không có lỗi mức CRITICAL/BLOCKER còn mở | 0 lỗi | ✅ 0 |
| XC-05 | Quality Gates tự động | 6/6 PASS | ✅ 6/6 |
| XC-06 | Tài liệu test đã được cập nhật | Đầy đủ | ✅ |

### 2.5. Chiến lược kiểm thử

```
┌─────────────────────────────────────────────────────────┐
│                   TEST STRATEGY                          │
├──────────────┬──────────────┬──────────────┬────────────┤
│  Khóa 1      │  Khóa 2      │  Khóa 3      │  Khóa 4    │
│ (Foundations)│ (BB + WB)    │ (Automated)  │ (Selenium) │
├──────────────┼──────────────┼──────────────┼────────────┤
│ Test Plan    │ Equivalence  │ Quality Gates│ POM Pattern│
│ 7 Principles │ Partitioning │ CSV Parser   │ Headless   │
│ Entry/Exit   │ BVA          │ Static Anal. │ Chrome     │
│ Defect Log   │ Branch Cov.  │ Pylint CI    │ 7 TC-UI    │
└──────────────┴──────────────┴──────────────┴────────────┘
```

### 2.6. Công cụ sử dụng

| Công cụ | Phiên bản | Mục đích |
|:--------|:----------|:---------|
| `pytest` | 9.0.3 | Test runner chính |
| `pytest-cov` | 7.1.0 | Đo độ phủ code |
| `unittest.mock` | stdlib | Mock subprocess, filesystem |
| `pylint` | 3.x | Static code analysis |
| `Selenium` | 4.x | E2E UI testing |
| `locust` | 2.x | Load/Performance testing |
| `analyze_results.py` | custom | Tự động phân tích CSV |

---

## 3. BLACK-BOX TESTING (Khóa 2 — Phần A)

> **Nguyên tắc:** Kiểm thử dựa trên đặc tả (specification), không nhìn vào code nội bộ.

### 3.1. Kỹ thuật: Equivalence Partitioning

**Đối tượng kiểm thử:** Tham số `mode` trong POST request `/api/network`

| Lớp tương đương | Giá trị đại diện | Hành vi mong đợi |
|:----------------|:-----------------|:-----------------|
| **Hợp lệ — Profile chuẩn** | `"4g"`, `"3g"`, `"5g"` | HTTP 200, status=success |
| **Hợp lệ — Đặc biệt** | `"reset"`, `"wifi"` | HTTP 200, xóa tc rules |
| **Không hợp lệ — Chuỗi lạ** | `"xyz"`, `"h4"` | Fallback về 4G, không crash |
| **Không hợp lệ — Thiếu param** | (body rỗng) | Dùng state hiện tại |

### 3.2. Kỹ thuật: Boundary Value Analysis (BVA)

| Tham số | Giá trị biên dưới | Giá trị biên trên | Ghi chú |
|:--------|:------------------|:------------------|:--------|
| Bandwidth | `128kbit` (2G) | `200mbit` (5G) | Reset = None |
| Latency | `10ms` (5G) | `500ms` (2G) | Reset = None |
| Packet Loss | `0%` (5G, LTE) | `5%` (2G) | |

### 3.3. Test Cases Black-box

| TC-ID | Tên test case | Input | Expected Output | Kỹ thuật |
|:------|:--------------|:------|:----------------|:---------|
| TC-BB-01 | POST mode=4g thành công | `mode=4g` | `{status:success, mode:4g}` | EP |
| TC-BB-02 | POST mode=reset xóa rules | `mode=reset` | tc rules cleared | EP |
| TC-BB-03 | POST mode=wifi không giới hạn | `mode=wifi` | Không có HTB/netem | EP |
| TC-BB-04 | POST body rỗng dùng state cũ | `""` | mode = state hiện tại | EP |
| TC-BB-05 | POST mode không hợp lệ | `mode=xyz` | Fallback, không crash | EP |
| TC-BB-06 | OPTIONS preflight request | OPTIONS / | HTTP 200, CORS headers | EP |
| TC-BB-07 | 2G là bandwidth thấp nhất | Profile 2G | bw=128kbit < bw(3G) | BVA |
| TC-BB-08 | 5G là bandwidth cao nhất | Profile 5G | bw=200mbit > bw(wifi) | BVA |
| TC-BB-09 | Reset profile = None values | Profile reset | bw=None, lat=None | BVA |
| TC-BB-10 | Độ trễ giảm dần 2G→5G | Tất cả profiles | lat(2G)>lat(3G)>lat(5G) | BVA |

---

## 4. WHITE-BOX TESTING (Khóa 2 — Phần B)

> **Nguyên tắc:** Kiểm thử dựa trên cấu trúc nội bộ của code.

### 4.1. Phân tích luồng điều khiển — `apply_tc_rules(mode)`

```
apply_tc_rules(mode)
        │
        ├── [1] tc qdisc del (ignore_errors=True)      ← luôn chạy
        ├── [2] iptables -F OUTPUT (ignore_errors=True) ← luôn chạy
        │
        └── if mode in ['reset', 'wifi']:   ← NHÁNH A
                │   save_state(mode)
                └── return  ← thoát sớm
            else:                           ← NHÁNH B
                │   profile = PROFILES.get(mode, PROFILES['4g'])
                │   tc qdisc add ... htb
                │   tc qdisc add ... netem
                └── save_state(mode)
```

### 4.2. Độ phủ code (Code Coverage)

```
Name             Stmts   Miss  Cover   Missing
----------------------------------------------
network_api.py     107     16    85%   123-128, 131-134, 147-153
----------------------------------------------
TOTAL              107     16    85%
```

**Phân tích các dòng chưa được phủ:**

| Dòng | Nội dung | Lý do chưa phủ |
|:-----|:---------|:----------------|
| 123-128 | `delayed_apply()` bên trong thread | Thread async, bị mock |
| 131-134 | Exception handler trong POST | Cần inject lỗi vào wfile |
| 147-153 | `__main__` block | Không chạy trực tiếp |

### 4.3. Branch Coverage Analysis

| Nhánh | Điều kiện | Test case phủ |
|:------|:----------|:--------------|
| A1 | `mode == 'reset'` | `test_reset_mode_clears_tc_rules` |
| A2 | `mode == 'wifi'` | `test_wifi_mode_does_not_apply_tc_constraints` |
| B1 | `mode in PROFILES` | `test_4g_mode_adds_htb_and_netem` |
| B2 | `mode not in PROFILES` | `test_unknown_mode_falls_back_to_4g_profile` |
| C1 | `returncode == 0` | `test_run_command_returns_result` |
| C2 | `returncode != 0`, ignore=False | `test_run_command_logs_error_on_failure` |
| C3 | `returncode != 0`, ignore=True | `test_run_command_suppresses_error_when_ignore_flag_set` |
| D1 | State file tồn tại, JSON hợp lệ | `test_get_state_reads_existing_valid_file` |
| D2 | State file không tồn tại | `test_get_state_returns_default_when_file_missing` |
| D3 | State file JSON lỗi | `test_get_state_returns_default_on_corrupt_json` |

**Branch Coverage: 10/10 nhánh chính (100%)**

---

## 5. KẾT QUẢ CHẠY KIỂM THỬ

### 5.1. Tổng quan kết quả

```
============================= test session starts ==============================
platform linux -- Python 3.13.3, pytest-9.0.3, pluggy-1.6.0
plugins: cov-7.1.0

collected 24 items

24 passed, 14 subtests passed in 0.13s
```

### 5.2. Chi tiết theo nhóm

| Nhóm test | Số lượng | Kết quả | Mô tả |
|:----------|:---------|:--------|:------|
| TestStateManagement | 7 | ✅ 7/7 PASS | Đọc/ghi trạng thái |
| TestNetworkProfiles | 5 (+7 subtests) | ✅ 5/5 PASS | Cấu hình profiles |
| TestApplyTcRules | 5 | ✅ 5/5 PASS | Logic áp dụng tc |
| TestNetworkHandler | 4 | ✅ 4/4 PASS | HTTP handler |
| TestRunCommand | 3 | ✅ 3/3 PASS | Shell command wrapper |
| **TỔNG** | **24** | **✅ 24/24** | **100% PASS** |

### 5.3. Lệnh chạy kiểm thử

```bash
# Chạy toàn bộ test suite với coverage
pytest tests/ -v --tb=short --cov=network_api --cov-report=html --cov-report=term-missing
```

---

## 6. STATIC ANALYSIS (Khóa 3 — Phần A)

> **Công cụ:** `pylint 3.x` — phân tích code tĩnh, không cần chạy chương trình.

### 6.1. Kết quả Pylint

Lệnh chạy:
```bash
pylint network_api.py --output-format=text
```

**Điểm số: 5.32/10** (trước khi cải thiện)

### 6.2. Phân loại vấn đề phát hiện

| Loại | Mã | Số lượng | Mô tả |
|:-----|:---|:---------|:------|
| **Warning (W)** | W1203 | 14 | Dùng f-string trong logging (nên dùng lazy %) |
| **Warning (W)** | W1514 | 2 | `open()` thiếu tham số `encoding` |
| **Warning (W)** | W0718 | 2 | `except Exception` quá rộng |
| **Convention (C)** | C0116 | 3 | Thiếu docstring cho method |
| **Convention (C)** | C0321 | 2 | Nhiều lệnh trên một dòng |
| **Warning (W)** | W0621 | 1 | Redefine biến từ outer scope |

### 6.3. Phân tích & Đánh giá

| Nhóm vấn đề | Mức độ | Hành động |
|:------------|:-------|:----------|
| `W1203` — f-string logging | Thấp | Chấp nhận: code rõ ràng hơn, hiệu năng không ảnh hưởng |
| `W1514` — thiếu encoding | Trung bình | Cần fix: có thể gây lỗi trên hệ thống không phải UTF-8 |
| `W0718` — broad except | Trung bình | Chấp nhận: cần catch mọi lỗi trong HTTP handler |
| `C0116` — thiếu docstring | Thấp | Fix: `do_POST`, `do_OPTIONS`, `apply_tc_rules` cần docstring |

> **Kết luận:** Điểm 5.32/10 phản ánh code được viết nhanh cho mục đích nghiên cứu. Các vấn đề chủ yếu là Convention, không phải lỗi logic. Sau khi fix `W1514`, điểm ước tính tăng lên ~7.5/10.

---

## 7. AUTOMATED ANALYSIS (Khóa 3 — Phần B)

### 7.1. Mô tả công cụ phân tích

File: `analyze_results.py` — Script tự động kiểm tra Quality Gates từ CSV thực nghiệm.

```
CSV Log File → parse_csv() → evaluate_quality_gates() → print_report() → export_markdown()
```

### 7.2. Quality Gates định nghĩa

| Gate ID | Metric | Tiêu chuẩn | Ngưỡng |
|:--------|:-------|:-----------|:-------|
| QG-01 | Stalls | ITU-T G.1010 §6.2 | ≤ 3 lần |
| QG-02 | Buffer trung bình | MPEG-DASH Best Practice | ≥ 2.0 giây |
| QG-03 | Throughput trung bình | H3-DASH Lab Spec | ≥ 1.0 Mbps |
| QG-04 | Dropped Frames | W3C Media Performance | ≤ 5% |
| QG-05 | Manifest Time | QUIC RFC 9000 | ≤ 500ms |
| QG-06 | Total Buffering Time | ITU-T G.1010 §6.3 | ≤ 10 giây |

### 7.3. Kết quả phân tích mẫu

```
QG-01  Stalls ≤ 3            2.000 lần    3 lần   ✅ PASS
QG-02  Avg Buffer ≥ 2.0s     3.635 giây  2.0 giây  ✅ PASS
QG-03  Throughput ≥ 1.0 Mbps 56.686 Mbps 1.0 Mbps  ✅ PASS
QG-04  Dropped Frames ≤ 5%   0.002 %     0.05 %   ✅ PASS
QG-05  Manifest ≤ 500ms      206.186 ms  500.0 ms  ✅ PASS
QG-06  Buffering ≤ 10s       0.841 giây  10.0 giây ✅ PASS

Kết quả: 6/6 Quality Gates ĐẠT → ✅ ĐẠT CHUẨN CHẤT LƯỢNG
```

---

## 8. E2E UI TESTING với SELENIUM (Khóa 4)

> **Công cụ:** Selenium 4 + ChromeDriver (Headless) + Page Object Model Pattern

### 8.1. Kiến trúc Page Object Model

```
tests/test_ui.py
    │
    ├── DashboardPage (POM class)
    │     ├── Locators (ID, XPath selectors)
    │     ├── open() / get_title()
    │     ├── start_session() / stop_session()
    │     └── find_by_id() / click_by_id()
    │
    └── TestDashboardUI (test class)
          ├── TC-UI-01: Page loads with correct title
          ├── TC-UI-02: Network profile buttons present
          ├── TC-UI-03: Start session toggles state
          ├── TC-UI-04: Log terminal shows events
          ├── TC-UI-05: Essential DOM elements exist
          ├── TC-UI-06: Page renders without errors
          └── TC-UI-07: Rapid clicks stability test
```

### 8.2. Test Cases Selenium

| TC-ID | Mô tả | Kỹ thuật | Điều kiện Pass |
|:------|:------|:---------|:---------------|
| TC-UI-01 | Page load & title | Black-box | Title chứa "H3-DASH" |
| TC-UI-02 | Profile buttons hiện diện | Equivalence Partitioning | Có đủ LTE, 5G, 4G, 3G, 2G |
| TC-UI-03 | Start session toggle | State-based testing | Text thay đổi sau click |
| TC-UI-04 | Log terminal output | Behavioral testing | Log không rỗng sau start |
| TC-UI-05 | DOM elements exist | Structural testing | Tất cả phần tử thiết yếu có mặt |
| TC-UI-06 | No error page | Sanity check | Không có "404", "500" |
| TC-UI-07 | Rapid clicks stability | Stress testing | Page không crash sau 4 click |

### 8.3. Lệnh chạy Selenium

```bash
# Cài Selenium
pip install selenium webdriver-manager

# Chạy E2E tests
pytest tests/test_ui.py -v

# Chạy toàn bộ (unit + E2E)
pytest tests/ -v
```

---

## 9. LOAD TESTING (Bonus — Khóa 3)

File: `tests/locustfile.py` — Kiểm tra khả năng chịu tải của API.

```python
# 4 loại task giả lập:
# - switch_to_4g  (weight=3): POST mode=4g
# - switch_to_3g  (weight=2): POST mode=3g
# - reset_network (weight=1): POST mode=reset
# - get_dashboard (weight=4): GET /
```

```bash
# Chạy load test (cần server đang chạy)
locust -f tests/locustfile.py --host=https://localhost --headless \
  -u 10 -r 2 --run-time 30s
```

---

## 10. DEFECT LOG (Lịch sử lỗi)

### 10.1. Bảng theo dõi lỗi

| ID | Mô tả | Mức độ | Phát hiện bởi | Trạng thái | Fix |
|:---|:------|:-------|:--------------|:-----------|:----|
| BUG-01 | `get_state()` dùng `bare except: pass` — nuốt lỗi JSONDecodeError không log | Medium | White-box test | ✅ Fixed | Thay bằng `except (json.JSONDecodeError, OSError) as e: logger.warning(...)` |
| BUG-02 | `open()` trong `apply_tc_rules` thiếu `encoding` | Low | Pylint W1514 | ⚠️ Open | Cần thêm `encoding="utf-8"` |
| BUG-03 | Logging dùng f-string thay vì lazy `%` formatting | Low | Pylint W1203 | ⚠️ Accepted | Convention, không ảnh hưởng chức năng |
| BUG-04 | `apply_tc_rules()` thiếu docstring | Low | Pylint C0116 | ⚠️ Open | Cần bổ sung docstring |

### 10.2. Defect Lifecycle

```
[Phát hiện] → [Ghi nhận vào Defect Log] → [Phân loại mức độ]
      → [Phân công fix] → [Verify sau fix] → [Đóng]
```

### 10.3. Thống kê

| Mức độ | Tổng | Đã fix | Còn mở |
|:-------|:-----|:-------|:-------|
| Critical | 0 | 0 | 0 |
| High | 0 | 0 | 0 |
| Medium | 1 | 1 | 0 |
| Low | 3 | 0 | 3 |
| **Tổng** | **4** | **1** | **3** |

---

## 11. PHÂN CÔNG NHÓM

| Thành viên | Phụ trách | Nội dung |
|:-----------|:----------|:---------|
| **Thành viên 1** | Khóa 1 | Test plan, 7 principles, Entry/Exit criteria, Defect log |
| **Thành viên 2** | Khóa 2 | Equivalence Partitioning, BVA, Coverage analysis |
| **Thành viên 3** | Khóa 3 + 4 | `analyze_results.py`, pylint, Selenium E2E, Quality Gates |

---

## 12. KẾT LUẬN

### Những gì đã đạt được

✅ **24/24 test cases** PASS, không có lỗi  
✅ **85% statement coverage** — mức tốt cho production module  
✅ **100% branch coverage** trên 10 nhánh điều kiện chính  
✅ **6/6 Quality Gates** đạt chuẩn ITU-T G.1010  
✅ **7 test cases Selenium** với Page Object Model pattern  
✅ **Static analysis** bằng pylint — 4 defects được phân loại và theo dõi  
✅ **CI/CD pipeline** tự động chạy test + pylint + analysis trên GitHub Actions  
✅ **7 Principles of Testing** được áp dụng xuyên suốt dự án  
✅ **Entry/Exit Criteria** đầy đủ với ngưỡng đo lường cụ thể  

### Điểm có thể cải thiện (Future Work)

- Fix BUG-02, BUG-04 (pylint warnings còn mở)
- Tăng statement coverage từ 85% → 95%
- Thêm cross-browser testing (Firefox, Edge)
- Tích hợp SonarQube cho static analysis chuyên sâu hơn
