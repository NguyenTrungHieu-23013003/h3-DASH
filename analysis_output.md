# H3-DASH — Báo Cáo Phân Tích Tự Động

**Môn:** Đánh giá và Kiểm định Chất lượng Phần mềm  
**Khóa 3:** Introduction to Automated Analysis  
**Session:** `SES-20260617-122643`  
**Ngày:** 2026-06-17 12:26:43  
**File dữ liệu:** `sample_h3_log.csv`  

## 1. Kiểm Tra Quality Gates

| ID | Mô tả | Tiêu chuẩn | Thực tế | Ngưỡng | Kết quả |
|:---|:------|:-----------|--------:|-------:|:-------:|
| QG-01 | Tổng số lần dừng hình (Stalls) ≤ 3 | ITU-T G.1010 §6.2 | 5.000 lần | 3 lần | ❌ FAIL |
| QG-02 | Buffer trung bình (Avg Buffer) ≥ 2.0 giây | MPEG-DASH Best Practice | 3.740 giây | 2.0 giây | ✅ PASS |
| QG-03 | Throughput trung bình ≥ 1.0 Mbps | H3-DASH Lab Spec | 51.369 Mbps | 1.0 Mbps | ✅ PASS |
| QG-04 | Tỷ lệ Dropped/Decoded Frames ≤ 5% | W3C Media Performance | 0.002 % | 0.05 % | ✅ PASS |
| QG-05 | Thời gian tải Manifest ≤ 500ms (0-RTT benefit) | QUIC RFC 9000 | 191.312 ms | 500.0 ms | ✅ PASS |
| QG-06 | Tổng Buffering Time ≤ 10 giây | ITU-T G.1010 §6.3 | 0.699 giây | 10.0 giây | ✅ PASS |

**Kết quả tổng thể:** 5/6 gates đạt → ❌ **CHƯA ĐẠT**

## 2. Thống Kê Theo Profile Mạng

| Profile | Mẫu | Throughput TB (Mbps) | Buffer TB (s) | Bitrate TB (kbps) | Stalls | Buffering (s) |
|:--------|----:|--------------------:|--------------:|------------------:|-------:|-------------:|
| 2G | 13 | 0.107 | 0.00 | 96.2 | 5 | 0.70 |
| 3G | 12 | 1.629 | 3.12 | 1465.9 | 0 | 0.00 |
| 4G | 15 | 16.227 | 4.35 | 14604.1 | 0 | 0.00 |
| 5G | 15 | 158.221 | 5.40 | 142398.7 | 0 | 0.00 |
| LTE | 15 | 39.683 | 4.53 | 35714.8 | 0 | 0.00 |
| WIFI | 14 | 77.293 | 4.47 | 69563.8 | 0 | 0.00 |

## 3. Kết Luận Tự Động

> Script này chạy hoàn toàn tự động — không cần can thiệp thủ công.
> Các Quality Gates được xây dựng theo tiêu chuẩn ITU-T G.1010 và QUIC RFC 9000.
