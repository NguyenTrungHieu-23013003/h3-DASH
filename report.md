# HƯỚNG DẪN VẬN HÀNH & PHÂN TÍCH DỮ LIỆU H3-DASH LAB

Dự án này được thiết kế để đo lường và phân tích hiệu năng của giao thức **HTTP/3 (QUIC)** trong việc truyền tải video thích nghi **MPEG-DASH**. Tài liệu này giúp bạn hiểu rõ cấu trúc hệ thống và cách khai thác dữ liệu log CSV cho mục đích nghiên cứu khoa học.

---

## 1. Danh mục và Công dụng của các File
Hệ thống được xây dựng trên nền tảng Docker để đảm bảo tính nhất quán và khả năng can thiệp sâu vào tầng mạng.

| Tên File | Vai trò | Công dụng chi tiết |
| :--- | :--- | :--- |
| **`docker-compose.yml`** | Điều phối hệ thống | Quản lý việc chạy container, ánh xạ cổng 443 (TCP/UDP) và phân quyền mạng (`NET_ADMIN`, `NET_RAW`) cho Docker. |
| **`Dockerfile`** | Xây dựng môi trường | Cài đặt Caddy Server (Hỗ trợ H3 native), Python 3 và các công cụ quản lý mạng (`iproute2`, `iptables`). |
| **`Caddyfile`** | Cấu hình Server H3 | Cho phép server hỗ trợ HTTP/1.1, H2, H3. Quan trọng nhất là gửi tiêu đề `Alt-Svc` để trình duyệt nhận diện cổng H3. |
| **`network_api.py`** | Trái tim điều khiển | Nhận lệnh từ Dashboard để thực thi giả lập mạng (băng thông, độ trễ, mất gói) thông qua công cụ `tc` (Traffic Control). |
| **`html/index.html`** | Dashboard & Metrics | Giao diện người dùng tích hợp bộ máy đo (Metrics Engine) từ thư viện `dash.js` và `shaka-player`. Xuất dữ liệu ra CSV. |
| **`generate_certs.sh`** | Bảo mật (SSL/TLS) | Tạo chứng chỉ tự ký (Self-signed) cho `localhost`. Đây là điều kiện bắt buộc để chạy được HTTPS/3. |
| **`simulate_network.sh`** | Công cụ tay | (Dùng trong terminal) Cho phép bạn nạp nhanh các profile mạng hoặc reset mạng mà không cần dùng giao diện web. |
| **`video/`** | Dữ liệu thực nghiệm | Chứa các phân đoạn video được mã hóa đa mức chất lượng (DASH Segments). |

---

## 2. Quy trình Vận hành Chuẩn (Step-by-Step)
Để tránh các lỗi như `ERR_QUIC_PROTOCOL_ERROR`, bạn cần thực hiện đúng trình tự:

### Bước 1: Khởi động Server
Mở terminal tại thư mục dự án và chạy:
```bash
docker compose up --build -d
```

### Bước 2: Khởi động Trình duyệt Chrome (Ép kiểu H3)
Bạn không thể dùng Chrome bình thường vì nó sẽ ưu tiên H2. Phải chạy lệnh terminal này để "ép" Chrome tin tưởng chứng chỉ Lab và ưu tiên H3:
```bash
google-chrome --user-data-dir=/tmp/h3-test \
  --ignore-certificate-errors-spki-list=+y/4p6HunOhDlI16sd0HHyEinjWpuxBKBf4VgHB11do= \
  --origin-to-force-quic-on=localhost:443 \
  --disable-gpu --ozone-platform=x11 \
  https://localhost
```

### Bước 3: Thực hiện Thí nghiệm
1. Truy cập Dashboard -> Nhấn **Start Session** (Bắt đầu ghi log).
2. Thay đổi **SIM Profile** (3G, 4G, 5G, **WiFi**) để quan sát sự thích nghi của H3.
   - *Lưu ý: Chế độ WiFi sẽ sử dụng tốc độ thực tế từ mạng của bạn (không giới hạn).*
3. Theo dõi các chỉ số nhảy trực tiếp trên **Metrics Engine**.
4. Nhấn **Export** để tải Log CSV về máy để phân tích.

---

## 3. Cẩm nang Tra cứu 17 Thông số Log (CSV)
Để người đọc dễ dàng nắm bắt, 17 thông số trong file log được chia thành 4 nhóm ý nghĩa thực tế sau:

### Nhóm 1: Môi trường & Kết nối (Network Environment)
*Giúp người đọc biết: "Thí nghiệm đang chạy trong điều kiện mạng nào?"*
| Tên Cột | Ý nghĩa thực tế | Giá trị nghiên cứu |
| :--- | :--- | :--- |
| **`SimProfile`** | Loại mạng giả lập | Xác định môi trường test (3G, 4G, 5G, **WIFI**...). |
| **`Protocol`** | Giao thức truyền tải | Khẳng định đang dùng **H3 (QUIC)**. |
| **`Latency_ms`** | Độ trễ (Ping) | Đo tốc độ phản hồi của mạng. |
| **`Timestamp`** | Thời gian hệ thống | Dùng để đối chiếu mốc thời gian thực tế. |
| **`Estimated_BW_bps`**| Băng thông dự đoán | "Não" của trình duyệt nghĩ mạng mạnh bao nhiêu. |

### Nhóm 2: Chất lượng Hình ảnh (Visual Quality)
*Giúp người đọc biết: "Video xem có nét và đẹp không?"*
| Tên Cột | Ý nghĩa thực tế | Giá trị nghiên cứu |
| :--- | :--- | :--- |
| **`Bitrate_kbps`** | Độ nặng của dữ liệu | Bitrate càng cao, ảnh càng sắc nét. |
| **`Resolution`** | Độ phân giải | Kích thước ảnh (720p, 1080p,... ). |

### Nhóm 3: Trải nghiệm & Độ mượt (User Experience - QoE)
*Giúp người đọc biết: "Xem video có bị ức chế vì lag hay chờ tải không?"*
| Tên Cột | Ý nghĩa thực tế | Giá trị nghiên cứu |
| :--- | :--- | :--- |
| **`Elapsed_Sec`** | Thời gian trôi qua | Dùng làm trục thời gian cho các biểu đồ. |
| **`Throughput_Mbps`** | Tốc độ tải thực tế | H3 đang kéo được bao nhiêu MB mỗi giây. |
| **`Buffer_Sec`** | Bộ nhớ dự trữ | Video đã tải sẵn được bao nhiêu giây (càng cao càng tốt). |
| **`Stalls`** | Số lần bị dừng | **Quan trọng nhất**: H3 có giúp giảm đứng hình không? |
| **`Buffering_Time`** | Thời gian chờ đệm | Tổng thời gian lãng phí vì phải chờ "xoay vòng". |

### Nhóm 4: Hiệu năng Chuyên sâu (Technical Health)
*Giúp người đọc biết: "Thiết bị có xử lý nổi H3 không và có lỗi gì ngầm không?"*
| Tên Cột | Ý nghĩa thực tế | Giá trị nghiên cứu |
| :--- | :--- | :--- |
| **`Dropped_Frames`** | Khung hình bị rơi | Video có bị giật (khựng) hình không? |
| **`Decoded_Frames`** | Khung hình đã xử lý | Đo mức độ làm việc của phần cứng thiết bị. |
| **`Corrupted_Frames`** | Khung hình bị hỏng | Kiểm tra tính chính xác của dữ liệu QUIC. |
| **`Manifest_Time`** | Trễ khởi tạo | H3 giúp bắt đầu xem video nhanh hơn bao nhiêu. |
| **`License_Time`** | Trễ bản quyền (DRM) | Thời gian xử lý các yêu cầu bảo mật. |

---

## 5. LUẬN GIẢI KẾT QUẢ (Dành cho người đọc báo cáo)
Đây là cách để bạn và người xem báo cáo hiểu được các con số trong log CSV đang "chứng minh" điều gì về công nghệ HTTP/3 (QUIC):

### 5.1. Chứng minh tốc độ khởi tạo (Handshake Benefit)
*   **Mối liên hệ**: So sánh giữa `Latency_ms` và `Manifest_Time`.
*   **Luận giải**: Nếu `Manifest_Time` (thời gian tải cấu hình) rất thấp trong khi `Latency` cao, điều đó chứng minh tính năng **0-RTT/1-RTT** của QUIC đang hoạt động. Nó bỏ qua các bước bắt tay rườm rà của TCP+TLS 1.2 cũ, giúp video bắt đầu phát ngay lập tức.

### 5.2. Chứng minh khả năng chống nghẽn (Anti-HoL Blocking)
*   **Mối liên hệ**: Xem cột `SimProfile` khi đổi từ LTE sang 3G/GPRS và quan sát `Stalls` cùng `Buffer_Sec`.
*   **Luận giải**: Ở HTTP/2 (cọc TCP), nếu 1 gói tin bị mất, toàn bộ các gói sau phải dừng lại. Ở HTTP/3, nếu bạn thấy mạng yếu nhưng `Stalls` (số lần dừng) vẫn thấp và `Buffer_Sec` phục hồi nhanh, đó là bằng chứng QUIC cho phép các luồng dữ liệu độc lập, **không bị tắc nghẽn dây chuyền**.

### 5.3. Chứng minh hiệu quả của ABR (Adaptive Bitrate) trên H3
*   **Mối liên hệ**: Quan sát `Estimated_BW_bps` so với `Bitrate_kbps`.
*   **Luận giải**: Nếu `Estimated_BW_bps` (băng thông dự đoán) luôn bám sát và cao hơn `Bitrate_kbps`, điều đó chứng minh bộ máy dự đoán của H3 rất nhạy bén, giúp trình phát video (Player) luôn chọn được chất lượng hình ảnh (Resolution) cao nhất mà đường truyền cho phép.

### 5.4. Chứng minh gánh nặng phần cứng (Processing Overhead)
*   **Mối liên hệ**: Xem `Throughput_Mbps` cao nhưng `Dropped_Frames` cũng tăng.
*   **Luận giải**: Đây là điểm yếu của H3. Nếu mạng rất nhanh nhưng số khung hình bị bỏ (`Dropped_Frames`) tăng, người đọc hiểu rằng giao thức QUIC đang tiêu tốn nhiều tài nguyên CPU của thiết bị hơn để xử lý gói tin so với H2 truyền thống.

### 5.5. Chứng minh lợi thế của H3 trên mạng thực tế (WiFi vs Simulated)
*   **Mối liên hệ**: So sánh kết quả khi chọn `SimProfile` là **WIFI** và các profile khác.
*   **Luận giải**: Sử dụng profile **WIFI** giúp bạn thiết lập một "điểm chuẩn" (Baseline). Nếu H3 trên WiFi thực tế đạt được `Throughput` cao và `Stalls` bằng 0, bạn có thể chứng minh rằng H3 đã sẵn sàng cho môi trường Internet thực tế, không chỉ trong các kịch bản Lab được kiểm soát.

---