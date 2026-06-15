# BÁO CÁO GIỮA KỲ — H3-DASH ANALYTICAL LAB TOOL

**Môn học:** Đánh giá và Kiểm định Chất lượng Phần mềm  
**Dự án:** H3-DASH — HTTP/3 & MPEG-DASH Performance Testing Lab  
**Nhóm:** 3 thành viên  
**Ngày:** 2026-06-08  

---

## MỤC LỤC

1. [Giới thiệu dự án](#1-giới-thiệu-dự-án)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Cài đặt môi trường từ đầu](#3-cài-đặt-môi-trường-từ-đầu)
4. [Vận hành hệ thống Lab](#4-vận-hành-hệ-thống-lab)
5. [Chạy kiểm thử (Unit & Integration Tests)](#5-chạy-kiểm-thử)
6. [Chạy phân tích tự động (Automated Analysis)](#6-chạy-phân-tích-tự-động)
7. [Cẩm nang 17 thông số log CSV](#7-cẩm-nang-17-thông-số-log-csv)
8. [Kết quả và luận giải](#8-kết-quả-và-luận-giải)
9. [Cấu trúc thư mục dự án](#9-cấu-trúc-thư-mục-dự-án)

---

## 1. Giới thiệu dự án

H3-DASH là hệ thống thực nghiệm đo lường và phân tích hiệu năng giao thức **HTTP/3 (QUIC)** trong việc truyền tải video thích nghi **MPEG-DASH** (Adaptive Bitrate Streaming).

**Mục tiêu nghiên cứu:**
- Chứng minh lợi thế của QUIC (0-RTT handshake, chống Head-of-Line Blocking) so với TCP/HTTP2
- Đo lường QoE (Quality of Experience) người dùng qua các điều kiện mạng khác nhau (2G → 5G)
- Tự động kiểm tra kết quả thực nghiệm theo chuẩn Quality Gates (ITU-T G.1010, QUIC RFC 9000)

**Phạm vi kiểm thử:**
- **SUT (System Under Test):** `network_api.py` — module Python điều khiển mạng trung tâm
- **Loại test:** Unit Testing, Integration Testing, Black-box, White-box, Automated Analysis

---

## 2. Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────┐
│                     DOCKER CONTAINER                         │
│                                                              │
│  ┌──────────────┐    HTTP/3     ┌──────────────────────┐    │
│  │   Chrome     │◄─────────────►│  Caddy Server (H3)   │    │
│  │  (Client)    │   port 443    │  + html/index.html   │    │
│  └──────┬───────┘               └──────────────────────┘    │
│         │                                                     │
│         │ POST /api/network                                   │
│         ▼                                                     │
│  ┌──────────────┐    tc/iptables  ┌──────────────────────┐  │
│  │ network_api  │────────────────►│   Linux Kernel       │  │
│  │  (port 5000) │                 │  Traffic Control     │  │
│  └──────────────┘                 └──────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

Ngoài Docker (môi trường test):
┌──────────────────────────────────────┐
│  pytest + pytest-cov                 │
│  ├── tests/test_network_api.py       │
│  └── analyze_results.py (CSV → QG)  │
└──────────────────────────────────────┘
```

| File | Vai trò |
|:-----|:--------|
| `network_api.py` | API Python điều khiển mạng, nhận lệnh từ Dashboard |
| `Caddyfile` | Cấu hình Caddy Server hỗ trợ H3 native |
| `Dockerfile` | Build image: Caddy + Python + iproute2 |
| `docker-compose.yml` | Orchestrate container, mở cổng 443 (TCP/UDP) |
| `html/index.html` | Dashboard + Metrics Engine, xuất CSV |
| `generate_certs.sh` | Tạo chứng chỉ TLS self-signed cho localhost |
| `simulate_network.sh` | Công cụ CLI để nạp nhanh profile mạng |
| `tests/test_network_api.py` | Bộ test (24 test cases) cho network_api.py |
| `analyze_results.py` | Script phân tích tự động file CSV theo Quality Gates |
| `docs/test_documentation.md` | Tài liệu kiểm thử đầy đủ (test plan, test cases) |

---

## 3. Cài đặt môi trường từ đầu

### 3.1. Yêu cầu hệ thống

| Phần mềm | Phiên bản tối thiểu | Kiểm tra |
|:---------|:--------------------|:---------|
| OS | Ubuntu 22.04 / Debian 12 | `uname -a` |
| Docker | 24.0+ | `docker --version` |
| Docker Compose | v2.0+ | `docker compose version` |
| Python | 3.10+ | `python3 --version` |
| pip | 23.0+ | `pip3 --version` |
| Google Chrome | 115+ | `google-chrome --version` |

---

### 3.2. Bước 1 — Clone dự án

```bash
git clone <repository-url>
cd h3-dash
```

---

### 3.3. Bước 2 — Cài đặt Python dependencies (để chạy test)

> ⚠️ Bước này chỉ cần cho môi trường kiểm thử. Không cần cho server Docker.

```bash
# Cài pytest và pytest-cov
pip install pytest pytest-cov --break-system-packages

# Kiểm tra cài đặt thành công
pytest --version
# → pytest 9.x.x

python3 -c "import coverage; print('coverage OK')"
# → coverage OK
```

---

### 3.4. Bước 3 — Tạo chứng chỉ TLS (bắt buộc cho H3)

> ⚠️ HTTP/3 yêu cầu HTTPS. Cần tạo chứng chỉ self-signed cho localhost.

```bash
chmod +x generate_certs.sh
./generate_certs.sh
```

Sau khi chạy xong, kiểm tra thư mục `certs/` có đủ:
```
certs/
├── rootCA.pem      ← Root CA (để Chrome tin tưởng)
├── rootCA.key
├── localhost.crt   ← Server certificate
├── localhost.key   ← Private key
└── ...
```

> 📌 **Lấy SPKI fingerprint** (cần cho lệnh Chrome ở bước sau):
> ```bash
> openssl x509 -in certs/localhost.crt -pubkey -noout \
>   | openssl pkey -pubin -outform der \
>   | openssl dgst -sha256 -binary \
>   | base64
> ```
> Copy chuỗi hash này để dùng trong flag `--ignore-certificate-errors-spki-list`.

---

### 3.5. Bước 4 — Khởi động Docker Server

```bash
# Build và start container (lần đầu mất ~2-3 phút)
docker compose up --build -d

# Kiểm tra container đang chạy
docker compose ps
# → Status: running

# Xem log server (tùy chọn)
docker compose logs -f
```

---

### 3.6. Bước 5 — Mở Chrome với chế độ H3

> ⚠️ **Bắt buộc** dùng lệnh này. Chrome bình thường sẽ ưu tiên H2, không kết nối H3.

```bash
google-chrome \
  --user-data-dir=/tmp/h3-test \
  --ignore-certificate-errors-spki-list=<SPKI_HASH_Ở_BƯỚC_3.4> \
  --origin-to-force-quic-on=localhost:443 \
  --disable-gpu \
  --ozone-platform=x11 \
  https://localhost
```

**Thay `<SPKI_HASH_Ở_BƯỚC_3.4>` bằng chuỗi hash lấy được ở bước 3.4.**

> ✅ Xác nhận H3 đang hoạt động: Mở DevTools (`F12`) → Network tab → cột Protocol phải hiện **`h3`**.

---

## 4. Vận hành hệ thống Lab

### 4.1. Thực hiện thực nghiệm

1. Mở Dashboard tại `https://localhost`
2. Nhấn **▶ Start Session** để bắt đầu ghi log
3. Chọn **SIM Profile** để giả lập điều kiện mạng:

| Profile | Băng thông | Độ trễ | Mất gói | Mô tả |
|:--------|:-----------|:-------|:--------|:------|
| 2G | 128 kbps | 500ms | 5% | Mạng yếu, nông thôn |
| 3G | 2 Mbps | 100ms | 0.5% | Mạng di động cơ bản |
| 4G | 20 Mbps | 40ms | 0.2% | Mạng di động phổ thông |
| LTE | 50 Mbps | 20ms | 0% | 4G+ tốc độ cao |
| WiFi | 100 Mbps | 15ms | 0.1% | Mạng gia đình |
| 5G | 200 Mbps | 10ms | 0% | Mạng thế hệ mới |
| Reset | Không giới hạn | — | — | Xóa toàn bộ giới hạn |

4. Theo dõi metrics nhảy realtime trên **Metrics Engine**
5. Nhấn **⬇ Export** để tải file CSV log về máy

### 4.2. Dừng server

```bash
docker compose down
```

---

## 5. Chạy kiểm thử

> 📌 Bộ test **không cần Docker** và **không cần quyền root**. Chạy hoàn toàn trên máy local bằng mock.

### 5.1. Chạy toàn bộ test suite

```bash
cd /path/to/h3-dash

# Chạy đơn giản
pytest tests/ -v

# Chạy với coverage report (khuyên dùng)
pytest tests/ -v --tb=short \
  --cov=network_api \
  --cov-report=term-missing \
  --cov-report=html
```

### 5.2. Kết quả mong đợi

```
============================= test session starts ==============================
platform linux -- Python 3.13.3, pytest-9.0.3
plugins: cov-7.1.0

collected 24 items

tests/test_network_api.py::TestStateManagement::test_get_state_reads_existing_valid_file       PASSED
tests/test_network_api.py::TestStateManagement::test_get_state_returns_default_on_corrupt_json PASSED
tests/test_network_api.py::TestStateManagement::test_get_state_returns_default_on_empty_file   PASSED
tests/test_network_api.py::TestStateManagement::test_get_state_returns_default_when_file_missing PASSED
tests/test_network_api.py::TestStateManagement::test_save_and_reload_state                     PASSED
tests/test_network_api.py::TestStateManagement::test_save_state_overwrites_previous            PASSED
tests/test_network_api.py::TestStateManagement::test_save_state_writes_correct_json            PASSED
tests/test_network_api.py::TestNetworkProfiles::test_all_required_profiles_exist               PASSED
tests/test_network_api.py::TestNetworkProfiles::test_bandwidth_ordering_is_logical             PASSED
tests/test_network_api.py::TestNetworkProfiles::test_latency_ordering_is_logical               PASSED
tests/test_network_api.py::TestNetworkProfiles::test_profile_has_required_keys                 PASSED
tests/test_network_api.py::TestNetworkProfiles::test_reset_profile_has_none_values             PASSED
tests/test_network_api.py::TestApplyTcRules::test_4g_mode_adds_htb_and_netem                  PASSED
tests/test_network_api.py::TestApplyTcRules::test_apply_tc_saves_state                        PASSED
tests/test_network_api.py::TestApplyTcRules::test_reset_mode_clears_tc_rules                  PASSED
tests/test_network_api.py::TestApplyTcRules::test_unknown_mode_falls_back_to_4g_profile       PASSED
tests/test_network_api.py::TestApplyTcRules::test_wifi_mode_does_not_apply_tc_constraints     PASSED
tests/test_network_api.py::TestNetworkHandler::test_options_request_returns_200               PASSED
tests/test_network_api.py::TestNetworkHandler::test_post_sets_cors_headers                    PASSED
tests/test_network_api.py::TestNetworkHandler::test_post_uses_current_state_when_no_mode_param PASSED
tests/test_network_api.py::TestNetworkHandler::test_post_valid_mode_returns_success           PASSED
tests/test_network_api.py::TestRunCommand::test_run_command_logs_error_on_failure             PASSED
tests/test_network_api.py::TestRunCommand::test_run_command_returns_result                    PASSED
tests/test_network_api.py::TestRunCommand::test_run_command_suppresses_error_when_ignore_flag_set PASSED

================================ coverage: ================================
Name             Stmts   Miss  Cover   Missing
----------------------------------------------
network_api.py     107     16    85%   123-128, 131-134, 147-153
----------------------------------------------
TOTAL              107     16    85%

==================== 24 passed, 14 subtests passed in 0.13s ====================
```

### 5.3. Xem HTML Coverage Report

```bash
# Sau khi chạy với --cov-report=html, mở báo cáo:
xdg-open htmlcov/index.html
```

### 5.4. Chạy từng nhóm test riêng lẻ

```bash
# Chỉ test State Management
pytest tests/ -v -k "TestStateManagement"

# Chỉ test Network Profiles
pytest tests/ -v -k "TestNetworkProfiles"

# Chỉ test HTTP Handler
pytest tests/ -v -k "TestNetworkHandler"

# Chỉ test Apply TC Rules
pytest tests/ -v -k "TestApplyTcRules"

# Chỉ test Run Command
pytest tests/ -v -k "TestRunCommand"
```

### 5.5. Tổng quan bộ test

| Nhóm | Số test | Kỹ thuật | Nội dung kiểm tra |
|:-----|:-------:|:---------|:------------------|
| TestStateManagement | 7 | Unit / White-box | Đọc/ghi file JSON trạng thái, xử lý lỗi |
| TestNetworkProfiles | 5 (+7 sub) | Black-box / BVA | Cấu hình đầy đủ, thứ tự BW/Latency |
| TestApplyTcRules | 5 | Unit / White-box | Lệnh `tc` đúng theo profile, save state |
| TestNetworkHandler | 4 | Integration | HTTP POST/OPTIONS, CORS headers |
| TestRunCommand | 3 | Unit | Xử lý lỗi shell command, ignore_errors |
| **Tổng** | **24** | | **100% PASS** |

---

## 6. Chạy phân tích tự động

Script `analyze_results.py` đọc file CSV log từ Dashboard và **tự động** kiểm tra 6 Quality Gates theo chuẩn ITU-T G.1010 & QUIC RFC 9000.

### 6.1. Chạy với dữ liệu mẫu (demo nhanh)

```bash
python3 analyze_results.py
```

Script sẽ tự sinh file CSV mẫu gồm 60+ dòng dữ liệu cho 6 profiles (2G/3G/4G/LTE/WiFi/5G) rồi phân tích luôn.

### 6.2. Chạy với dữ liệu thực từ thực nghiệm

```bash
# Sau khi export CSV từ Dashboard
python3 analyze_results.py path/to/your_exported_log.csv
```

### 6.3. Kết quả phân tích mẫu

```
======================================================================
  H3-DASH AUTOMATED ANALYSIS REPORT
======================================================================
  Session ID   : SES-20260608-112217
  Tổng mẫu    : 64 dòng dữ liệu
  Profiles     : 2G, 3G, 4G, 5G, LTE, WIFI

  KIỂM TRA QUALITY GATES
  -----------------------------------------------------------------------
  QG-01  Stalls ≤ 3 lần                  2.000 lần      3 lần  ✅ PASS
  QG-02  Avg Buffer ≥ 2.0 giây           3.635 giây   2.0 giây  ✅ PASS
  QG-03  Throughput TB ≥ 1.0 Mbps       56.686 Mbps   1.0 Mbps  ✅ PASS
  QG-04  Dropped Frames ≤ 5%             0.002 %      0.05 %  ✅ PASS
  QG-05  Manifest Time ≤ 500ms          206.186 ms   500.0 ms  ✅ PASS
  QG-06  Buffering Time ≤ 10 giây        0.841 giây  10.0 giây  ✅ PASS

  Kết quả: 6/6 Quality Gates ĐẠT → ✅ ĐẠT CHUẨN CHẤT LƯỢNG
```

### 6.4. Xuất báo cáo Markdown

Script tự động xuất file `analysis_output.md` — sẵn sàng dán vào báo cáo nhóm:

```bash
cat analysis_output.md
```

### 6.5. Quality Gates định nghĩa

| Gate ID | Metric theo dõi | Tiêu chuẩn | Ngưỡng |
|:--------|:----------------|:-----------|:-------|
| QG-01 | Tổng Stalls (lần dừng hình) | ITU-T G.1010 §6.2 | ≤ 3 lần |
| QG-02 | Buffer trung bình | MPEG-DASH Best Practice | ≥ 2.0 giây |
| QG-03 | Throughput trung bình | H3-DASH Lab Spec | ≥ 1.0 Mbps |
| QG-04 | Tỷ lệ Dropped/Decoded Frames | W3C Media Performance | ≤ 5% |
| QG-05 | Manifest Time (0-RTT proof) | QUIC RFC 9000 | ≤ 500ms |
| QG-06 | Tổng Buffering Time | ITU-T G.1010 §6.3 | ≤ 10 giây |

---

## 7. Cẩm nang 17 thông số log CSV

File CSV xuất từ Dashboard gồm 17 cột, chia thành 4 nhóm:

### Nhóm 1 — Môi trường & Kết nối

| Cột | Ý nghĩa | Giá trị nghiên cứu |
|:----|:--------|:------------------|
| `Timestamp` | Thời gian ghi mẫu | Trục thời gian thực |
| `Elapsed_Sec` | Giây trôi qua từ lúc start | Trục X cho biểu đồ |
| `SimProfile` | Profile mạng đang áp dụng | Môi trường test (3G/4G/5G...) |
| `Protocol` | Giao thức đang dùng | Xác nhận H3 (QUIC) |
| `Latency_ms` | Độ trễ (ping) mạng | Đo tốc độ phản hồi |
| `Estimated_BW_bps` | Băng thông dự đoán | "Não" của player nghĩ mạng mạnh cỡ nào |

### Nhóm 2 — Chất lượng hình ảnh

| Cột | Ý nghĩa | Giá trị nghiên cứu |
|:----|:--------|:------------------|
| `Bitrate_kbps` | Bitrate video đang phát | Cao → hình sắc nét hơn |
| `Resolution` | Độ phân giải (480p/720p/1080p) | Chỉ số chất lượng trực quan |

### Nhóm 3 — Trải nghiệm người dùng (QoE)

| Cột | Ý nghĩa | Giá trị nghiên cứu |
|:----|:--------|:------------------|
| `Throughput_Mbps` | Tốc độ tải thực tế | H3 kéo được bao nhiêu MB/s |
| `Buffer_Sec` | Bộ đệm dự trữ (giây) | Càng cao càng ít giật |
| `Stalls` | Số lần dừng hình (tích lũy) | **Quan trọng nhất:** H3 giảm đứng hình? |
| `Buffering_Time` | Tổng thời gian chờ đệm (giây) | Thời gian lãng phí |

### Nhóm 4 — Hiệu năng kỹ thuật

| Cột | Ý nghĩa | Giá trị nghiên cứu |
|:----|:--------|:------------------|
| `Dropped_Frames` | Khung hình bị bỏ | Video bị giật/khựng |
| `Decoded_Frames` | Khung hình đã giải mã | Tải phần cứng |
| `Corrupted_Frames` | Khung hình bị hỏng | Tính toàn vẹn dữ liệu QUIC |
| `Manifest_Time` | Thời gian tải manifest (ms) | 0-RTT benefit của QUIC |
| `License_Time` | Thời gian xử lý DRM (ms) | Overhead bảo mật |

---

## 8. Kết quả và luận giải

### 8.1. Chứng minh lợi thế 0-RTT Handshake

- **Metric:** So sánh `Manifest_Time` với `Latency_ms`
- **Luận giải:** Nếu `Manifest_Time` < 300ms dù `Latency` cao → QUIC 0-RTT/1-RTT đã bỏ qua bước bắt tay TCP+TLS rườm rà, video bắt đầu phát gần như tức thì.

### 8.2. Chứng minh chống Head-of-Line Blocking

- **Metric:** `Stalls` và `Buffer_Sec` khi đổi profile từ LTE → 3G
- **Luận giải:** Ở HTTP/2 (TCP), 1 gói mất → tất cả stream chờ. Ở H3/QUIC, nếu mạng yếu mà `Stalls` vẫn thấp và `Buffer_Sec` phục hồi nhanh → các stream QUIC độc lập nhau, không bị tắc dây chuyền.

### 8.3. Chứng minh ABR hoạt động tốt trên H3

- **Metric:** `Estimated_BW_bps` vs `Bitrate_kbps`
- **Luận giải:** Nếu băng thông dự đoán luôn bám sát và cao hơn bitrate thực tế → player luôn chọn được chất lượng cao nhất đường truyền cho phép.

### 8.4. Điểm yếu: CPU overhead

- **Metric:** `Throughput_Mbps` cao nhưng `Dropped_Frames` cũng tăng
- **Luận giải:** QUIC xử lý gói tin ở user-space thay vì kernel → tốn CPU hơn H2. Đây là trade-off cần nêu trong báo cáo.

### 8.5. Baseline: WiFi vs. mạng giả lập

- **Metric:** So sánh profile `WIFI` (tốc độ thực) với các profile giả lập
- **Luận giải:** WiFi cho `Throughput` cao và `Stalls = 0` → H3 sẵn sàng cho môi trường internet thực tế.

---

## 9. Cấu trúc thư mục dự án

```
h3-dash/
│
├── 📄 network_api.py          ← SUT: API điều khiển mạng (Python)
├── 📄 analyze_results.py      ← Script phân tích CSV tự động (Khóa 3)
├── 📄 report.md               ← Báo cáo này
│
├── 📁 tests/
│   ├── __init__.py
│   └── test_network_api.py    ← Bộ test 24 cases (pytest)
│
├── 📁 docs/
│   └── test_documentation.md  ← Tài liệu kiểm thử đầy đủ
│
├── 📁 html/
│   └── index.html             ← Dashboard + Metrics Engine
│
├── 📁 solutions/              ← Kết quả thực nghiệm mẫu
│   ├── analyze_lab_data.py
│   ├── sample_lab_data.csv
│   └── analysis_output/
│       ├── quality_report.md
│       ├── profile_comparison.png
│       ├── quality_gate.png
│       └── timeseries.png
│
├── 📁 certs/                  ← Chứng chỉ TLS self-signed
├── 📁 video/                  ← DASH video segments
│
├── 🐳 Dockerfile
├── 🐳 docker-compose.yml
├── ⚙️  Caddyfile
├── 🔒 generate_certs.sh
└── 🔧 simulate_network.sh
```

---

## Quick Reference — Lệnh hay dùng

```bash
# === CÀI ĐẶT ===
pip install pytest pytest-cov --break-system-packages

# === SERVER ===
docker compose up --build -d          # Khởi động
docker compose down                   # Dừng
docker compose logs -f                # Xem log

# === CHROME (bắt buộc dùng lệnh này) ===
google-chrome --user-data-dir=/tmp/h3-test \
  --ignore-certificate-errors-spki-list=<HASH> \
  --origin-to-force-quic-on=localhost:443 \
  --disable-gpu --ozone-platform=x11 \
  https://localhost

# === TEST ===
pytest tests/ -v --tb=short --cov=network_api --cov-report=term-missing

# === PHÂN TÍCH CSV ===
python3 analyze_results.py                    # Demo với dữ liệu mẫu
python3 analyze_results.py your_log.csv       # Dữ liệu thực nghiệm
```