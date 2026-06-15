#!/usr/bin/env python3
"""
=============================================================================
H3-DASH Automated Results Analyzer
=============================================================================
Môn   : Đánh giá và Kiểm định Chất lượng Phần mềm
Khóa  : 3 - Introduction to Automated Analysis
Dự án : H3-DASH Analytical Lab Tool

Mô tả : Script này đọc file CSV log xuất từ Dashboard H3-DASH và tự động
        kiểm tra xem kết quả thực nghiệm có đạt các ngưỡng chất lượng
        (Quality Gates) theo tiêu chuẩn ITU-T G.1010 không.

Chạy  : python3 analyze_results.py <path_to_csv>
         python3 analyze_results.py  (dùng dữ liệu mẫu tự sinh)
=============================================================================
"""

import csv
import sys
import os
import random
import statistics
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# QUALITY GATES — Ngưỡng chất lượng theo ITU-T G.1010 & tài liệu nghiên cứu
# ─────────────────────────────────────────────────────────────────────────────
QUALITY_GATES = {
    # [QG-01] Số lần dừng hình không được vượt quá 3 lần/phiên
    "max_stalls": {
        "threshold": 3,
        "description": "Tổng số lần dừng hình (Stalls) ≤ 3",
        "standard": "ITU-T G.1010 §6.2",
        "metric": "Stalls",
    },
    # [QG-02] Buffer trung bình phải ≥ 2 giây
    "min_avg_buffer": {
        "threshold": 2.0,
        "description": "Buffer trung bình (Avg Buffer) ≥ 2.0 giây",
        "standard": "MPEG-DASH Best Practice",
        "metric": "Buffer_Sec",
    },
    # [QG-03] Throughput trung bình phải ≥ 1 Mbps
    "min_avg_throughput": {
        "threshold": 1.0,
        "description": "Throughput trung bình ≥ 1.0 Mbps",
        "standard": "H3-DASH Lab Spec",
        "metric": "Throughput_Mbps",
    },
    # [QG-04] Tỷ lệ dropped frames không quá 5%
    "max_dropped_frame_ratio": {
        "threshold": 0.05,
        "description": "Tỷ lệ Dropped/Decoded Frames ≤ 5%",
        "standard": "W3C Media Performance",
        "metric": "Dropped_Frames / Decoded_Frames",
    },
    # [QG-05] Thời gian khởi tạo manifest ≤ 500ms
    "max_manifest_time": {
        "threshold": 500.0,
        "description": "Thời gian tải Manifest ≤ 500ms (0-RTT benefit)",
        "standard": "QUIC RFC 9000",
        "metric": "Manifest_Time",
    },
    # [QG-06] Tổng thời gian chờ đệm ≤ 10 giây
    "max_total_buffering": {
        "threshold": 10.0,
        "description": "Tổng Buffering Time ≤ 10 giây",
        "standard": "ITU-T G.1010 §6.3",
        "metric": "Buffering_Time",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class MetricsRow:
    timestamp: str = ""
    elapsed_sec: float = 0.0
    sim_profile: str = ""
    protocol: str = ""
    bitrate_kbps: float = 0.0
    resolution: str = ""
    latency_ms: float = 0.0
    throughput_mbps: float = 0.0
    buffer_sec: float = 0.0
    stalls: int = 0
    buffering_time: float = 0.0
    dropped_frames: int = 0
    decoded_frames: int = 0
    corrupted_frames: int = 0
    manifest_time: float = 0.0
    license_time: float = 0.0
    estimated_bw_bps: float = 0.0


@dataclass
class QualityGateResult:
    gate_id: str
    description: str
    standard: str
    passed: bool
    actual_value: float
    threshold: float
    unit: str = ""

    def status_icon(self) -> str:
        return "✅ PASS" if self.passed else "❌ FAIL"


@dataclass
class AnalysisReport:
    session_id: str
    csv_file: str
    generated_at: str
    total_rows: int
    profiles_found: List[str]
    gate_results: List[QualityGateResult] = field(default_factory=list)
    summary_stats: dict = field(default_factory=dict)
    overall_pass: bool = False
    pass_count: int = 0
    fail_count: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# SAMPLE DATA GENERATOR
# ─────────────────────────────────────────────────────────────────────────────
def generate_sample_data(output_path: str = "sample_h3_log.csv") -> str:
    """Tạo dữ liệu CSV mẫu mô phỏng kết quả thực nghiệm H3-DASH."""
    print(f"[INFO] Đang tạo file CSV mẫu: {output_path}")

    profiles = [
        ("wifi",  100.0, 15,  0.1),
        ("5g",    200.0, 10,  0.0),
        ("4g",    20.0,  40,  0.2),
        ("3g",    2.0,   100, 0.5),
        ("lte",   50.0,  20,  0.0),
        ("2g",    0.128, 500, 5.0),
    ]

    rows = []
    start_time = datetime.now()
    elapsed = 0.0

    for profile_name, bw_mbit, lat_ms, loss_pct in profiles:
        num_samples = random.randint(8, 15)
        stall_count = 0
        buffering_total = 0.0

        for i in range(num_samples):
            elapsed += random.uniform(1.5, 3.0)
            throughput = max(0.1, random.gauss(bw_mbit * 0.8, bw_mbit * 0.1))
            bitrate = throughput * 900  # kbps estimate
            buffer = max(0.0, random.gauss(5.0 - lat_ms / 50, 1.0))
            stall = 1 if random.random() < (loss_pct / 100 * 2) else 0
            stall_count += stall
            buf_time = random.uniform(0, 0.5) if stall else 0.0
            buffering_total += buf_time
            decoded = random.randint(280, 320)
            dropped = int(decoded * random.uniform(0, loss_pct / 100 * 0.5))

            rows.append({
                "Timestamp": (start_time).strftime("%Y-%m-%dT%H:%M:%S"),
                "Elapsed_Sec": round(elapsed, 2),
                "SimProfile": profile_name.upper(),
                "Protocol": "H3",
                "Bitrate_kbps": round(bitrate, 1),
                "Resolution": "1080p" if throughput > 10 else ("720p" if throughput > 3 else "480p"),
                "Latency_ms": lat_ms + random.uniform(-5, 5),
                "Throughput_Mbps": round(throughput, 3),
                "Buffer_Sec": round(buffer, 2),
                "Stalls": stall_count,
                "Buffering_Time": round(buffering_total, 3),
                "Dropped_Frames": dropped,
                "Decoded_Frames": decoded,
                "Corrupted_Frames": 0,
                "Manifest_Time": round(random.uniform(50, 350), 1),
                "License_Time": round(random.uniform(10, 80), 1),
                "Estimated_BW_bps": round(throughput * 1_000_000, 0),
            })

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[INFO] ✅ Đã tạo {len(rows)} dòng dữ liệu mẫu → {output_path}")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# CSV PARSER
# ─────────────────────────────────────────────────────────────────────────────
def parse_csv(filepath: str) -> List[MetricsRow]:
    """Đọc và parse file CSV log từ H3-DASH Dashboard."""
    rows = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, raw in enumerate(reader):
            try:
                row = MetricsRow(
                    timestamp=raw.get("Timestamp", ""),
                    elapsed_sec=float(raw.get("Elapsed_Sec", 0) or 0),
                    sim_profile=raw.get("SimProfile", "").strip().lower(),
                    protocol=raw.get("Protocol", ""),
                    bitrate_kbps=float(raw.get("Bitrate_kbps", 0) or 0),
                    resolution=raw.get("Resolution", ""),
                    latency_ms=float(raw.get("Latency_ms", 0) or 0),
                    throughput_mbps=float(raw.get("Throughput_Mbps", 0) or 0),
                    buffer_sec=float(raw.get("Buffer_Sec", 0) or 0),
                    stalls=int(float(raw.get("Stalls", 0) or 0)),
                    buffering_time=float(raw.get("Buffering_Time", 0) or 0),
                    dropped_frames=int(float(raw.get("Dropped_Frames", 0) or 0)),
                    decoded_frames=int(float(raw.get("Decoded_Frames", 1) or 1)),
                    corrupted_frames=int(float(raw.get("Corrupted_Frames", 0) or 0)),
                    manifest_time=float(raw.get("Manifest_Time", 0) or 0),
                    license_time=float(raw.get("License_Time", 0) or 0),
                    estimated_bw_bps=float(raw.get("Estimated_BW_bps", 0) or 0),
                )
                rows.append(row)
            except (ValueError, KeyError) as e:
                print(f"  [WARN] Dòng {i+2} bị lỗi, bỏ qua: {e}")
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# QUALITY GATE EVALUATOR
# ─────────────────────────────────────────────────────────────────────────────
def evaluate_quality_gates(rows: List[MetricsRow]) -> List[QualityGateResult]:
    """Kiểm tra tất cả Quality Gates và trả về kết quả."""
    results = []

    if not rows:
        return results

    # Lấy giá trị cuối cùng cho stalls (tích lũy)
    total_stalls = rows[-1].stalls

    avg_buffer = statistics.mean(r.buffer_sec for r in rows)
    avg_throughput = statistics.mean(r.throughput_mbps for r in rows)

    total_decoded = sum(r.decoded_frames for r in rows)
    total_dropped = sum(r.dropped_frames for r in rows)
    drop_ratio = total_dropped / total_decoded if total_decoded > 0 else 0.0

    valid_manifest = [r.manifest_time for r in rows if r.manifest_time > 0]
    avg_manifest = statistics.mean(valid_manifest) if valid_manifest else 0.0

    total_buffering = rows[-1].buffering_time if rows else 0.0

    gate_data = [
        ("QG-01", "max_stalls",            total_stalls,    3,    "lần",   True),
        ("QG-02", "min_avg_buffer",         avg_buffer,      2.0,  "giây",  False),
        ("QG-03", "min_avg_throughput",     avg_throughput,  1.0,  "Mbps",  False),
        ("QG-04", "max_dropped_frame_ratio",drop_ratio,      0.05, "%",     True),
        ("QG-05", "max_manifest_time",      avg_manifest,    500.0,"ms",    True),
        ("QG-06", "max_total_buffering",    total_buffering, 10.0, "giây",  True),
    ]

    for gate_id, key, actual, threshold, unit, is_max in gate_data:
        gate = QUALITY_GATES[key]
        passed = (actual <= threshold) if is_max else (actual >= threshold)
        results.append(QualityGateResult(
            gate_id=gate_id,
            description=gate["description"],
            standard=gate["standard"],
            passed=passed,
            actual_value=actual,
            threshold=threshold,
            unit=unit,
        ))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# STATISTICS CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────
def compute_summary_stats(rows: List[MetricsRow]) -> dict:
    """Tính toán thống kê tổng hợp theo từng profile mạng."""
    profiles = {}
    for r in rows:
        p = r.sim_profile.upper()
        if p not in profiles:
            profiles[p] = []
        profiles[p].append(r)

    stats = {}
    for profile, prows in sorted(profiles.items()):
        throughputs = [r.throughput_mbps for r in prows]
        buffers = [r.buffer_sec for r in prows]
        bitrates = [r.bitrate_kbps for r in prows]
        stats[profile] = {
            "samples": len(prows),
            "avg_throughput_mbps": round(statistics.mean(throughputs), 3),
            "max_throughput_mbps": round(max(throughputs), 3),
            "avg_buffer_sec": round(statistics.mean(buffers), 2),
            "min_buffer_sec": round(min(buffers), 2),
            "avg_bitrate_kbps": round(statistics.mean(bitrates), 1),
            "stalls": prows[-1].stalls,
            "total_buffering_sec": round(prows[-1].buffering_time, 2),
        }
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# REPORT PRINTER
# ─────────────────────────────────────────────────────────────────────────────
SEP = "=" * 70
SEP2 = "-" * 70


def print_report(report: AnalysisReport):
    """In báo cáo phân tích ra terminal theo định dạng học thuật."""
    print(f"\n{SEP}")
    print(f"  H3-DASH AUTOMATED ANALYSIS REPORT")
    print(f"  Môn: Đánh giá và Kiểm định Chất lượng Phần mềm")
    print(SEP)
    print(f"  Session ID   : {report.session_id}")
    print(f"  File CSV     : {report.csv_file}")
    print(f"  Thời gian    : {report.generated_at}")
    print(f"  Tổng mẫu    : {report.total_rows} dòng dữ liệu")
    print(f"  Profiles     : {', '.join(report.profiles_found)}")

    # ── Quality Gates ──────────────────────────────────────────────────────
    print(f"\n{SEP2}")
    print(f"  KIỂM TRA QUALITY GATES")
    print(f"{SEP2}")
    print(f"  {'ID':<7} {'Mô tả':<42} {'Thực tế':>10} {'Ngưỡng':>9} {'Kết quả'}")
    print(f"  {'-'*7} {'-'*42} {'-'*10} {'-'*9} {'-'*10}")

    for r in report.gate_results:
        actual_str = f"{r.actual_value:.3f} {r.unit}"
        thresh_str = f"{r.threshold} {r.unit}"
        print(f"  {r.gate_id:<7} {r.description:<42} {actual_str:>12} {thresh_str:>10}  {r.status_icon()}")

    print(f"\n  Kết quả: {report.pass_count}/{report.pass_count + report.fail_count} Quality Gates ĐẠT")

    overall_label = "✅ ĐẠT CHUẨN CHẤT LƯỢNG" if report.overall_pass else "❌ CHƯA ĐẠT — Cần cải thiện"
    print(f"  Tổng đánh giá: {overall_label}")

    # ── Per-profile stats ─────────────────────────────────────────────────
    print(f"\n{SEP2}")
    print(f"  THỐNG KÊ THEO PROFILE MẠNG")
    print(f"{SEP2}")
    print(f"  {'Profile':<8} {'Mẫu':>5} {'Throughput TB':>14} {'Buffer TB':>10} {'Bitrate TB':>11} {'Stalls':>7} {'BufTime':>8}")
    print(f"  {'-'*8} {'-'*5} {'-'*14} {'-'*10} {'-'*11} {'-'*7} {'-'*8}")
    for profile, s in sorted(report.summary_stats.items()):
        print(
            f"  {profile:<8} {s['samples']:>5} "
            f"{s['avg_throughput_mbps']:>11.3f} Mbps "
            f"{s['avg_buffer_sec']:>7.2f}s "
            f"{s['avg_bitrate_kbps']:>8.1f} kbps "
            f"{s['stalls']:>7} "
            f"{s['total_buffering_sec']:>6.2f}s"
        )

    # ── Phân tích tự động ─────────────────────────────────────────────────
    print(f"\n{SEP2}")
    print(f"  PHÂN TÍCH TỰ ĐỘNG — LUẬN GIẢI KẾT QUẢ")
    print(f"{SEP2}")

    stats = report.summary_stats
    if "WIFI" in stats and "3G" in stats:
        wifi_bw = stats["WIFI"]["avg_throughput_mbps"]
        g3_bw   = stats["3G"]["avg_throughput_mbps"]
        ratio   = wifi_bw / g3_bw if g3_bw > 0 else 0
        print(f"\n  [1] Lợi thế băng thông:")
        print(f"      WiFi ({wifi_bw:.2f} Mbps) gấp {ratio:.1f}x so với 3G ({g3_bw:.2f} Mbps).")

    if "WIFI" in stats and "5G" in stats:
        wifi_stall = stats["WIFI"]["stalls"]
        g5_stall   = stats["5G"]["stalls"]
        print(f"\n  [2] Khả năng chống nghẽn (Anti-HoL Blocking):")
        print(f"      WiFi stalls={wifi_stall}, 5G stalls={g5_stall}.")
        if wifi_stall == 0 and g5_stall == 0:
            print(f"      → H3/QUIC hoạt động tốt trên cả hai môi trường nhanh.")

    gate_05 = next((g for g in report.gate_results if g.gate_id == "QG-05"), None)
    if gate_05:
        print(f"\n  [3] Lợi thế 0-RTT Handshake (QUIC):")
        print(f"      Manifest Time trung bình = {gate_05.actual_value:.1f}ms (ngưỡng ≤ {gate_05.threshold}ms).")
        if gate_05.passed:
            print(f"      → Thời gian khởi tạo ngắn xác nhận tính năng 0-RTT/1-RTT của QUIC.")

    print(f"\n{SEP}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MARKDOWN EXPORTER
# ─────────────────────────────────────────────────────────────────────────────
def export_markdown(report: AnalysisReport, output_path: str = "analysis_output.md"):
    """Xuất báo cáo ra file Markdown để dán vào báo cáo nhóm."""
    lines = []
    lines.append("# H3-DASH — Báo Cáo Phân Tích Tự Động\n")
    lines.append(f"**Môn:** Đánh giá và Kiểm định Chất lượng Phần mềm  ")
    lines.append(f"**Khóa 3:** Introduction to Automated Analysis  ")
    lines.append(f"**Session:** `{report.session_id}`  ")
    lines.append(f"**Ngày:** {report.generated_at}  ")
    lines.append(f"**File dữ liệu:** `{report.csv_file}`  \n")

    lines.append("## 1. Kiểm Tra Quality Gates\n")
    lines.append("| ID | Mô tả | Tiêu chuẩn | Thực tế | Ngưỡng | Kết quả |")
    lines.append("|:---|:------|:-----------|--------:|-------:|:-------:|")
    for r in report.gate_results:
        icon = "✅ PASS" if r.passed else "❌ FAIL"
        lines.append(f"| {r.gate_id} | {r.description} | {r.standard} | {r.actual_value:.3f} {r.unit} | {r.threshold} {r.unit} | {icon} |")

    overall = "✅ **ĐẠT CHUẨN**" if report.overall_pass else "❌ **CHƯA ĐẠT**"
    lines.append(f"\n**Kết quả tổng thể:** {report.pass_count}/{report.pass_count + report.fail_count} gates đạt → {overall}\n")

    lines.append("## 2. Thống Kê Theo Profile Mạng\n")
    lines.append("| Profile | Mẫu | Throughput TB (Mbps) | Buffer TB (s) | Bitrate TB (kbps) | Stalls | Buffering (s) |")
    lines.append("|:--------|----:|--------------------:|--------------:|------------------:|-------:|-------------:|")
    for profile, s in sorted(report.summary_stats.items()):
        lines.append(
            f"| {profile} | {s['samples']} | {s['avg_throughput_mbps']:.3f} "
            f"| {s['avg_buffer_sec']:.2f} | {s['avg_bitrate_kbps']:.1f} "
            f"| {s['stalls']} | {s['total_buffering_sec']:.2f} |"
        )

    lines.append("\n## 3. Kết Luận Tự Động\n")
    lines.append("> Script này chạy hoàn toàn tự động — không cần can thiệp thủ công.")
    lines.append("> Các Quality Gates được xây dựng theo tiêu chuẩn ITU-T G.1010 và QUIC RFC 9000.\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[INFO] ✅ Đã xuất báo cáo Markdown → {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print(SEP)
    print("  H3-DASH Automated Results Analyzer")
    print("  Khóa 3 — Introduction to Automated Analysis")
    print(SEP)

    # Xác định file CSV đầu vào
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        if not os.path.exists(csv_path):
            print(f"[ERROR] Không tìm thấy file: {csv_path}")
            sys.exit(1)
        print(f"[INFO] Đọc file CSV: {csv_path}")
    else:
        print("[INFO] Không có file CSV → Tạo dữ liệu mẫu để demo...")
        csv_path = generate_sample_data("sample_h3_log.csv")

    # Parse dữ liệu
    rows = parse_csv(csv_path)
    if not rows:
        print("[ERROR] File CSV rỗng hoặc không có dữ liệu hợp lệ.")
        sys.exit(1)
    print(f"[INFO] Đã đọc {len(rows)} dòng dữ liệu.")

    # Phân tích
    gate_results  = evaluate_quality_gates(rows)
    summary_stats = compute_summary_stats(rows)
    pass_count    = sum(1 for g in gate_results if g.passed)
    fail_count    = len(gate_results) - pass_count

    report = AnalysisReport(
        session_id=datetime.now().strftime("SES-%Y%m%d-%H%M%S"),
        csv_file=os.path.basename(csv_path),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_rows=len(rows),
        profiles_found=sorted(set(r.sim_profile.upper() for r in rows)),
        gate_results=gate_results,
        summary_stats=summary_stats,
        overall_pass=(fail_count == 0),
        pass_count=pass_count,
        fail_count=fail_count,
    )

    # In và xuất báo cáo
    print_report(report)
    export_markdown(report, "analysis_output.md")
    print(f"[DONE] Phân tích hoàn tất.\n")


if __name__ == "__main__":
    main()
