"""
H3-DASH Lab — CSV Data Analyzer & Quality Gate
================================================
Môn: Đánh giá và Kiểm định Chất lượng Phần mềm

Mục đích:
  1. Đọc file CSV xuất từ Dashboard (LAB_DATA_*.csv)
  2. Thống kê và phân tích các chỉ số QoE (Quality of Experience) theo profile mạng
  3. Kiểm tra Pass/Fail theo Quality Criteria đã định nghĩa
  4. Xuất báo cáo và vẽ biểu đồ so sánh

Sử dụng:
  python3 solutions/analyze_lab_data.py <path_to_csv_file>

Ví dụ:
  python3 solutions/analyze_lab_data.py LAB_DATA_1717758000.csv
"""

import argparse
import os
import sys
import warnings
from dataclasses import dataclass, field
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ==========================================
# QUALITY CRITERIA (Pass/Fail Thresholds)
# Nguồn: ITU-T G.1010, ETSI TS 103 294 (QoE for adaptive streaming)
# ==========================================
@dataclass
class QualityCriteria:
    """
    Tiêu chí chất lượng cho từng profile mạng.
    Một session được đánh giá PASS nếu đáp ứng TẤT CẢ điều kiện.
    """
    profile_name: str                   # Tên profile (3G, 4G, ...)
    max_stalls: int                     # Số lần đứng hình tối đa cho phép
    max_buffering_time_sec: float       # Tổng thời gian chờ đệm tối đa (giây)
    min_avg_bitrate_kbps: float         # Bitrate trung bình tối thiểu
    min_avg_buffer_sec: float           # Buffer trung bình tối thiểu (giây)
    max_avg_latency_ms: float           # Độ trễ trung bình tối đa (ms)
    max_dropped_frame_rate: float       # Tỷ lệ frame bị drop tối đa (%)
    description: str = ""               # Mô tả tiêu chí


# Bảng tiêu chí — có thể điều chỉnh theo yêu cầu thực nghiệm
QUALITY_CRITERIA_TABLE = {
    "2G GPRS": QualityCriteria(
        profile_name="2G GPRS",
        max_stalls=10,
        max_buffering_time_sec=30.0,
        min_avg_bitrate_kbps=100,
        min_avg_buffer_sec=0.5,
        max_avg_latency_ms=700,
        max_dropped_frame_rate=5.0,
        description="Mạng GPRS — chấp nhận chất lượng thấp, ưu tiên không crash"
    ),
    "3G UMTS": QualityCriteria(
        profile_name="3G UMTS",
        max_stalls=5,
        max_buffering_time_sec=15.0,
        min_avg_bitrate_kbps=300,
        min_avg_buffer_sec=1.0,
        max_avg_latency_ms=200,
        max_dropped_frame_rate=3.0,
        description="Mạng 3G — chấp nhận chất lượng SD, thi thoảng buffer"
    ),
    "4G LTE": QualityCriteria(
        profile_name="4G LTE",
        max_stalls=2,
        max_buffering_time_sec=5.0,
        min_avg_bitrate_kbps=1500,
        min_avg_buffer_sec=3.0,
        max_avg_latency_ms=80,
        max_dropped_frame_rate=1.0,
        description="Mạng 4G/LTE — phải đạt HD, rất ít buffer"
    ),
    "LTE": QualityCriteria(
        profile_name="LTE",
        max_stalls=2,
        max_buffering_time_sec=5.0,
        min_avg_bitrate_kbps=1500,
        min_avg_buffer_sec=3.0,
        max_avg_latency_ms=80,
        max_dropped_frame_rate=1.0,
        description="Mạng LTE — như 4G"
    ),
    "Actual WiFi": QualityCriteria(
        profile_name="Actual WiFi",
        max_stalls=0,
        max_buffering_time_sec=2.0,
        min_avg_bitrate_kbps=3000,
        min_avg_buffer_sec=5.0,
        max_avg_latency_ms=30,
        max_dropped_frame_rate=0.5,
        description="WiFi thực tế — phải đạt Full HD, không đứng hình"
    ),
    "5G NR": QualityCriteria(
        profile_name="5G NR",
        max_stalls=0,
        max_buffering_time_sec=1.0,
        min_avg_bitrate_kbps=5000,
        min_avg_buffer_sec=8.0,
        max_avg_latency_ms=15,
        max_dropped_frame_rate=0.2,
        description="Mạng 5G — phải đạt 4K, gần như không có buffer"
    ),
    "Unlimited": QualityCriteria(
        profile_name="Unlimited",
        max_stalls=0,
        max_buffering_time_sec=1.0,
        min_avg_bitrate_kbps=3000,
        min_avg_buffer_sec=5.0,
        max_avg_latency_ms=50,
        max_dropped_frame_rate=0.5,
        description="Không giới hạn mạng — baseline tham chiếu"
    ),
}

# Fallback criteria nếu profile không có trong bảng
DEFAULT_CRITERIA = QualityCriteria(
    profile_name="Unknown",
    max_stalls=5,
    max_buffering_time_sec=20.0,
    min_avg_bitrate_kbps=200,
    min_avg_buffer_sec=1.0,
    max_avg_latency_ms=500,
    max_dropped_frame_rate=5.0,
    description="Tiêu chí mặc định"
)


# ==========================================
# DATA LOADING & PREPROCESSING
# ==========================================
REQUIRED_COLUMNS = [
    "Elapsed_Sec", "SimProfile", "Protocol", "Bitrate_kbps",
    "Throughput_Mbps", "Buffer_Sec", "Latency_ms",
    "Dropped_Frames", "Decoded_Frames", "Stalls", "Buffering_Time",
]


def load_csv(filepath: str) -> pd.DataFrame:
    """Tải và tiền xử lý file CSV từ Dashboard."""
    if not os.path.exists(filepath):
        print(f"[ERROR] Không tìm thấy file: {filepath}")
        sys.exit(1)

    df = pd.read_csv(filepath)

    # Kiểm tra cột bắt buộc
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        print(f"[WARNING] File CSV thiếu các cột: {missing}")
        print(f"          Các cột hiện có: {list(df.columns)}")

    # Chuyển kiểu dữ liệu
    numeric_cols = [
        "Elapsed_Sec", "Bitrate_kbps", "Throughput_Mbps",
        "Buffer_Sec", "Latency_ms", "Dropped_Frames",
        "Decoded_Frames", "Corrupted_Frames", "Stalls",
        "Buffering_Time", "Manifest_Time", "License_Time", "Estimated_BW_bps"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Tính tỷ lệ drop frame (%)
    if "Dropped_Frames" in df.columns and "Decoded_Frames" in df.columns:
        df["Drop_Frame_Rate_Pct"] = np.where(
            df["Decoded_Frames"] > 0,
            (df["Dropped_Frames"] / df["Decoded_Frames"]) * 100,
            0.0
        )

    return df


# ==========================================
# STATISTICAL ANALYSIS
# ==========================================
def analyze_by_profile(df: pd.DataFrame) -> dict:
    """Thống kê các chỉ số QoE theo từng profile mạng."""
    if "SimProfile" not in df.columns:
        return {}

    results = {}
    for profile, group in df.groupby("SimProfile"):
        stats = {
            "n_samples": len(group),
            "duration_sec": group["Elapsed_Sec"].max() - group["Elapsed_Sec"].min()
                            if "Elapsed_Sec" in group.columns else 0,
            "protocol": group["Protocol"].mode()[0] if "Protocol" in group.columns else "N/A",
        }

        # Các chỉ số chính
        metrics = {
            "avg_bitrate_kbps":    ("Bitrate_kbps", "mean"),
            "max_bitrate_kbps":    ("Bitrate_kbps", "max"),
            "avg_throughput_mbps": ("Throughput_Mbps", "mean"),
            "max_throughput_mbps": ("Throughput_Mbps", "max"),
            "avg_buffer_sec":      ("Buffer_Sec", "mean"),
            "min_buffer_sec":      ("Buffer_Sec", "min"),
            "avg_latency_ms":      ("Latency_ms", "mean"),
            "max_latency_ms":      ("Latency_ms", "max"),
            "total_stalls":        ("Stalls", "max"),  # Stalls là cumulative
            "total_buffering_sec": ("Buffering_Time", "max"),
            "total_dropped_frames":("Dropped_Frames", "max"),
            "total_decoded_frames":("Decoded_Frames", "max"),
            "avg_drop_rate_pct":   ("Drop_Frame_Rate_Pct", "mean"),
        }

        for key, (col, agg) in metrics.items():
            if col in group.columns:
                val = getattr(group[col], agg)()
                stats[key] = round(float(val), 3) if not pd.isna(val) else 0.0
            else:
                stats[key] = 0.0

        results[profile] = stats

    return results


# ==========================================
# QUALITY GATE — PASS / FAIL
# ==========================================
@dataclass
class CheckResult:
    check_name: str
    passed: bool
    actual: float
    threshold: float
    unit: str
    verdict: str = field(init=False)

    def __post_init__(self):
        self.verdict = "✅ PASS" if self.passed else "❌ FAIL"


def evaluate_quality_gate(profile_name: str, stats: dict) -> list[CheckResult]:
    """So sánh kết quả thực nghiệm với tiêu chí Pass/Fail."""
    criteria = QUALITY_CRITERIA_TABLE.get(profile_name, DEFAULT_CRITERIA)
    checks = []

    checks.append(CheckResult(
        "Số lần đứng hình (Stalls)",
        stats.get("total_stalls", 99) <= criteria.max_stalls,
        stats.get("total_stalls", 99), criteria.max_stalls, "lần"
    ))
    checks.append(CheckResult(
        "Tổng thời gian chờ đệm",
        stats.get("total_buffering_sec", 99) <= criteria.max_buffering_time_sec,
        stats.get("total_buffering_sec", 99), criteria.max_buffering_time_sec, "giây"
    ))
    checks.append(CheckResult(
        "Bitrate trung bình",
        stats.get("avg_bitrate_kbps", 0) >= criteria.min_avg_bitrate_kbps,
        stats.get("avg_bitrate_kbps", 0), criteria.min_avg_bitrate_kbps, "kbps"
    ))
    checks.append(CheckResult(
        "Buffer trung bình",
        stats.get("avg_buffer_sec", 0) >= criteria.min_avg_buffer_sec,
        stats.get("avg_buffer_sec", 0), criteria.min_avg_buffer_sec, "giây"
    ))
    checks.append(CheckResult(
        "Độ trễ trung bình",
        stats.get("avg_latency_ms", 9999) <= criteria.max_avg_latency_ms,
        stats.get("avg_latency_ms", 9999), criteria.max_avg_latency_ms, "ms"
    ))
    checks.append(CheckResult(
        "Tỷ lệ frame drop",
        stats.get("avg_drop_rate_pct", 99) <= criteria.max_dropped_frame_rate,
        stats.get("avg_drop_rate_pct", 99), criteria.max_dropped_frame_rate, "%"
    ))

    return checks


# ==========================================
# VISUALIZATION
# ==========================================
COLORS = {
    "bitrate": "#fbc02d",
    "throughput": "#00e676",
    "buffer": "#00d2ff",
    "latency": "#ff5252",
    "stalls": "#ce93d8",
    "pass": "#00e676",
    "fail": "#ff5252",
    "neutral": "#546e7a",
}


def plot_timeseries(df: pd.DataFrame, output_dir: str):
    """Vẽ biểu đồ time-series cho toàn bộ session."""
    if "Elapsed_Sec" not in df.columns:
        return

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#0a0e17")
    fig.suptitle("H3-DASH Lab — Session Time Series", color="white",
                 fontsize=14, fontweight="bold", y=0.98)

    plot_cfg = [
        ("Throughput_Mbps", "Throughput (Mbps)", COLORS["throughput"]),
        ("Bitrate_kbps",    "Bitrate (kbps)",    COLORS["bitrate"]),
        ("Buffer_Sec",      "Buffer (sec)",      COLORS["buffer"]),
    ]

    for ax, (col, label, color) in zip(axes, plot_cfg):
        ax.set_facecolor("#0d1117")
        if col in df.columns:
            for profile, grp in df.groupby("SimProfile") if "SimProfile" in df.columns else [("All", df)]:
                ax.plot(grp["Elapsed_Sec"], grp[col], linewidth=1.2,
                        label=profile, alpha=0.85)
        ax.set_ylabel(label, color="white", fontsize=9)
        ax.tick_params(colors="gray", labelsize=8)
        ax.spines[:].set_color("#333")
        ax.grid(alpha=0.15, color="white")
        ax.legend(fontsize=7, framealpha=0.3, facecolor="#111",
                  labelcolor="white", loc="upper right")

    axes[-1].set_xlabel("Thời gian (giây)", color="white", fontsize=9)
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    out = os.path.join(output_dir, "timeseries.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#0a0e17")
    plt.close()
    print(f"  → Đã lưu: {out}")


def plot_profile_comparison(analysis: dict, output_dir: str):
    """Vẽ biểu đồ so sánh các chỉ số giữa các profile mạng."""
    profiles = list(analysis.keys())
    if not profiles:
        return

    metrics_to_plot = [
        ("avg_bitrate_kbps",    "Avg Bitrate (kbps)",   COLORS["bitrate"]),
        ("avg_throughput_mbps", "Avg Throughput (Mbps)", COLORS["throughput"]),
        ("avg_buffer_sec",      "Avg Buffer (sec)",      COLORS["buffer"]),
        ("avg_latency_ms",      "Avg Latency (ms)",      COLORS["latency"]),
        ("total_stalls",        "Total Stalls",          COLORS["stalls"]),
    ]

    fig, axes = plt.subplots(1, len(metrics_to_plot), figsize=(16, 5),
                             facecolor="#0a0e17")
    fig.suptitle("H3-DASH Lab — Profile Comparison", color="white",
                 fontsize=13, fontweight="bold")

    for ax, (metric, label, color) in zip(axes, metrics_to_plot):
        ax.set_facecolor("#0d1117")
        values = [analysis[p].get(metric, 0) for p in profiles]
        bars = ax.bar(profiles, values, color=color, alpha=0.8, width=0.6)
        ax.set_title(label, color="white", fontsize=9, pad=6)
        ax.set_xticks(range(len(profiles)))
        ax.set_xticklabels(profiles, rotation=30, ha="right",
                           color="gray", fontsize=8)
        ax.tick_params(axis="y", colors="gray", labelsize=8)
        ax.spines[:].set_color("#333")
        ax.grid(axis="y", alpha=0.15, color="white")

        # Label trên mỗi bar
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01 * max(values or [1]),
                    f"{val:.1f}", ha="center", va="bottom", color="white",
                    fontsize=7, fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    out = os.path.join(output_dir, "profile_comparison.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#0a0e17")
    plt.close()
    print(f"  → Đã lưu: {out}")


def plot_quality_gate_summary(all_gate_results: dict, output_dir: str):
    """Vẽ bảng tổng hợp Pass/Fail cho từng profile."""
    profiles = list(all_gate_results.keys())
    if not profiles:
        return

    sample_checks = next(iter(all_gate_results.values()))
    check_names = [c.check_name for c in sample_checks]

    matrix = np.array([
        [1 if c.passed else 0 for c in all_gate_results[p]]
        for p in profiles
    ])

    fig, ax = plt.subplots(figsize=(max(10, len(check_names) * 1.8), max(4, len(profiles) * 0.8 + 2)),
                            facecolor="#0a0e17")
    ax.set_facecolor("#0d1117")

    cmap = plt.cm.RdYlGn
    im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(check_names)))
    ax.set_xticklabels(check_names, rotation=30, ha="right", color="white", fontsize=9)
    ax.set_yticks(range(len(profiles)))
    ax.set_yticklabels(profiles, color="white", fontsize=9)

    for i in range(len(profiles)):
        for j, check in enumerate(all_gate_results[profiles[i]]):
            txt = "PASS" if check.passed else "FAIL"
            color = "white" if check.passed else "black"
            ax.text(j, i, txt, ha="center", va="center",
                    color=color, fontsize=8, fontweight="bold")

    ax.set_title("Quality Gate — Pass/Fail Matrix", color="white",
                 fontsize=12, fontweight="bold", pad=10)
    ax.spines[:].set_color("#333")

    plt.tight_layout()
    out = os.path.join(output_dir, "quality_gate.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#0a0e17")
    plt.close()
    print(f"  → Đã lưu: {out}")


# ==========================================
# TEXT REPORT
# ==========================================
def print_report(analysis: dict, all_gate_results: dict, csv_path: str):
    """In báo cáo phân tích ra terminal."""
    SEP = "=" * 70
    print(f"\n{SEP}")
    print(f"  H3-DASH LAB — BÁO CÁO PHÂN TÍCH CHẤT LƯỢNG")
    print(f"  File: {os.path.basename(csv_path)}")
    print(f"{SEP}\n")

    total_pass = 0
    total_checks = 0

    for profile, stats in analysis.items():
        print(f"┌─ Profile: {profile:20s} │ Giao thức: {stats.get('protocol','N/A'):10s} │ Mẫu: {stats.get('n_samples',0)}")
        print(f"│  Avg Bitrate: {stats.get('avg_bitrate_kbps',0):>8.1f} kbps │ "
              f"Avg Buffer: {stats.get('avg_buffer_sec',0):>6.2f}s │ "
              f"Avg Latency: {stats.get('avg_latency_ms',0):>6.1f}ms")
        print(f"│  Throughput:  {stats.get('avg_throughput_mbps',0):>8.2f} Mbps │ "
              f"Stalls: {stats.get('total_stalls',0):>4.0f} lần  │ "
              f"Drop Rate: {stats.get('avg_drop_rate_pct',0):>5.2f}%")
        print("│")
        print("│  Quality Gate:")

        checks = all_gate_results.get(profile, [])
        for c in checks:
            total_checks += 1
            if c.passed:
                total_pass += 1
            sign = "✅" if c.passed else "❌"
            print(f"│    {sign} {c.check_name:<35s} → "
                  f"Thực tế: {c.actual:>8.2f} {c.unit:5s} │ "
                  f"Ngưỡng: {c.threshold:>8.2f} {c.unit}")

        overall = "🎉 PASS" if all(c.passed for c in checks) else "🚨 FAIL"
        print(f"│  Kết luận: {overall}")
        print("└" + "─" * 68)
        print()

    pass_rate = (total_pass / total_checks * 100) if total_checks > 0 else 0
    print(f"{'─'*70}")
    print(f"  TỔNG KẾT: {total_pass}/{total_checks} kiểm tra đạt yêu cầu ({pass_rate:.1f}%)")
    print(f"{'─'*70}\n")


def save_report_md(analysis: dict, all_gate_results: dict,
                   csv_path: str, output_dir: str):
    """Lưu báo cáo dạng Markdown."""
    lines = [
        "# H3-DASH Lab — Báo cáo Phân tích Chất lượng\n",
        f"**File dữ liệu:** `{os.path.basename(csv_path)}`\n",
        "---\n",
    ]
    for profile, stats in analysis.items():
        checks = all_gate_results.get(profile, [])
        overall = "✅ PASS" if all(c.passed for c in checks) else "❌ FAIL"
        lines.append(f"## Profile: {profile} — {overall}\n")
        lines.append(f"- **Giao thức:** {stats.get('protocol','N/A')}\n")
        lines.append(f"- **Số mẫu:** {stats.get('n_samples',0)}\n")
        lines.append(f"- **Avg Bitrate:** {stats.get('avg_bitrate_kbps',0):.1f} kbps\n")
        lines.append(f"- **Avg Throughput:** {stats.get('avg_throughput_mbps',0):.2f} Mbps\n")
        lines.append(f"- **Avg Buffer:** {stats.get('avg_buffer_sec',0):.2f}s\n")
        lines.append(f"- **Avg Latency:** {stats.get('avg_latency_ms',0):.1f}ms\n")
        lines.append(f"- **Total Stalls:** {stats.get('total_stalls',0):.0f}\n")
        lines.append(f"- **Drop Rate:** {stats.get('avg_drop_rate_pct',0):.2f}%\n")
        lines.append("\n### Quality Gate\n")
        lines.append("| Kiểm tra | Thực tế | Ngưỡng | Kết quả |\n")
        lines.append("|:---|---:|---:|:---:|\n")
        for c in checks:
            lines.append(f"| {c.check_name} | {c.actual:.2f} {c.unit} "
                         f"| {c.threshold:.2f} {c.unit} | {c.verdict} |\n")
        lines.append("\n")

    out = os.path.join(output_dir, "quality_report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"  → Đã lưu: {out}")


# ==========================================
# MAIN
# ==========================================
def main():
    parser = argparse.ArgumentParser(
        description="Phân tích file CSV từ H3-DASH Lab Dashboard"
    )
    parser.add_argument("csv_file", help="Đường dẫn đến file CSV (LAB_DATA_*.csv)")
    parser.add_argument(
        "--output-dir", "-o",
        default="solutions/analysis_output",
        help="Thư mục lưu kết quả (mặc định: solutions/analysis_output)"
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"\n[INFO] Đang tải dữ liệu: {args.csv_file}")
    df = load_csv(args.csv_file)
    print(f"[INFO] Đã tải {len(df)} dòng dữ liệu từ {df['SimProfile'].nunique() if 'SimProfile' in df.columns else '?'} profile(s)")

    print("\n[INFO] Đang phân tích theo profile...")
    analysis = analyze_by_profile(df)

    print("[INFO] Đang đánh giá Quality Gate...")
    all_gate_results = {
        profile: evaluate_quality_gate(profile, stats)
        for profile, stats in analysis.items()
    }

    print("\n[INFO] Đang xuất báo cáo...\n")
    print_report(analysis, all_gate_results, args.csv_file)

    print("[INFO] Đang vẽ biểu đồ...")
    plot_timeseries(df, args.output_dir)
    plot_profile_comparison(analysis, args.output_dir)
    plot_quality_gate_summary(all_gate_results, args.output_dir)
    save_report_md(analysis, all_gate_results, args.csv_file, args.output_dir)

    print(f"\n[DONE] Tất cả kết quả đã lưu vào: {args.output_dir}/\n")


if __name__ == "__main__":
    main()
