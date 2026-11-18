#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script phân tích thống kê kết quả thực nghiệm và vẽ bộ đồ thị khoa học (300 DPI)
theo phương pháp luận của Chủ đề 1.3. Algorithm Analysis.

Đầu vào:
  - results/raw_measurements.csv
  - results/cost_model_counts.csv
  - results/primitive_vs_comparable.csv

Đầu ra:
  - results/summary_statistics.csv
  - results/multiscale_normalized_summary.csv
  - results/key_findings.json
  - results/figures/*.png (6 đồ thị phân tích chuyên sâu)
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Cấu hình phông chữ hỗ trợ đầy đủ tiếng Việt có dấu trên macOS / đa nền tảng
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial Unicode MS", "Helvetica Neue", "Arial"],
    "axes.unicode_minus": False,
    "figure.dpi": 180,
    "savefig.dpi": 180,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.28,
    "grid.linestyle": "--",
    "font.size": 10.5,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 10.5,
    "legend.fontsize": 9.2,
})


def compute_summary(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Tính các đại lượng thống kê chuẩn: Mean, SD, SEM, 95% CI (Student-t), Median, IQR, Min, Max, CV%."""
    records = []
    for keys, grp in df.groupby(group_cols, sort=True):
        vals = grp["elapsed_ms"].to_numpy(dtype=float)
        cnt = len(vals)
        mean = float(np.mean(vals))
        trim_mean = float(stats.trim_mean(vals, 0.10)) if cnt >= 5 else mean
        sd = float(np.std(vals, ddof=1)) if cnt > 1 else 0.0
        sem = sd / np.sqrt(cnt) if cnt > 1 else 0.0
        t_crit = float(stats.t.ppf(0.975, df=cnt - 1)) if cnt > 1 else 0.0
        ci95 = t_crit * sem
        median = float(np.median(vals))
        q25, q75 = np.percentile(vals, [25, 75])
        iqr = float(q75 - q25)
        cv_pct = (sd / mean * 100.0) if mean > 0 else 0.0

        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        row.update({
            "trials": cnt,
            "mean_ms": mean,
            "trimmed_mean_ms": trim_mean,
            "sd_ms": sd,
            "sem_ms": sem,
            "ci95_ms": ci95,
            "ci95_low_ms": mean - ci95,
            "ci95_high_ms": mean + ci95,
            "median_ms": median,
            "iqr_ms": iqr,
            "min_ms": float(np.min(vals)),
            "max_ms": float(np.max(vals)),
            "cv_pct": cv_pct,
        })
        records.append(row)

    summary = pd.DataFrame(records)

    # Tính % cải thiện và hệ số tăng tốc (speedup) so với baseline CUTOFF = 0 của từng dataset
    base_col = [c for c in group_cols if c != "cutoff"]
    baselines = summary[summary["cutoff"] == 0][base_col + ["mean_ms"]].rename(
        columns={"mean_ms": "baseline_ms"}
    )
    summary = summary.merge(baselines, on=base_col, how="left")
    summary["relative_pct"] = (summary["mean_ms"] / summary["baseline_ms"]) * 100.0
    summary["improvement_pct"] = (
        (summary["baseline_ms"] - summary["mean_ms"]) / summary["baseline_ms"]
    ) * 100.0
    summary["speedup"] = summary["baseline_ms"] / summary["mean_ms"]
    return summary


def main():
    root = Path(__file__).resolve().parent.parent
    res_dir = root / "results"
    fig_dir = res_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    raw_df = pd.read_csv(res_dir / "raw_measurements.csv")
    cost_df = pd.read_csv(res_dir / "cost_model_counts.csv")
    prim_df = pd.read_csv(res_dir / "primitive_vs_comparable.csv")

    summary_df = compute_summary(raw_df, ["dataset", "category", "n", "cutoff"])
    summary_df.to_csv(res_dir / "summary_statistics.csv", index=False, float_format="%.6f")

    prim_summary = compute_summary(prim_df, ["dataset", "n", "representation", "cutoff"])
    prim_summary.to_csv(res_dir / "primitive_vs_comparable_summary.csv", index=False, float_format="%.6f")

    # Chuẩn hóa đa quy mô trên các bộ dữ liệu ngẫu nhiên đều N >= 100,000 (9 bộ dữ liệu từ 100k đến 1M)
    multiscale_sets = summary_df[
        (summary_df["category"] == "uniform_random") & (summary_df["n"] >= 100_000)
    ].copy()

    ms_agg = (
        multiscale_sets.groupby("cutoff", as_index=False)
        .agg(
            mean_rel_pct=("relative_pct", "mean"),
            sd_rel_pct=("relative_pct", "std"),
            mean_improvement_pct=("improvement_pct", "mean"),
            mean_speedup=("speedup", "mean"),
            datasets_count=("dataset", "count"),
        )
    )
    ms_agg["ci95_rel_pct"] = (
        stats.t.ppf(0.975, df=ms_agg["datasets_count"] - 1)
        * ms_agg["sd_rel_pct"]
        / np.sqrt(ms_agg["datasets_count"])
    )
    ms_agg.to_csv(res_dir / "multiscale_normalized_summary.csv", index=False, float_format="%.6f")

    # Xác định giá trị tối ưu trên N=1,000,000 và trên trung bình chuẩn hóa đa quy mô
    n1m = summary_df[summary_df["dataset"] == "random_N1000000.txt"].sort_values("cutoff")
    best_n1m_row = n1m.loc[n1m["mean_ms"].idxmin()]
    best_ms_row = ms_agg.loc[ms_agg["mean_rel_pct"].idxmin()]

    # Kiểm định thống kê cặp (Paired t-test & Wilcoxon) trên dữ liệu N=1,000,000 và đa quy mô
    def get_cutoff_metric_ms(c: int) -> dict:
        r_1m = n1m[n1m["cutoff"] == c].iloc[0]
        r_ms = ms_agg[ms_agg["cutoff"] == c].iloc[0]
        return {
            "cutoff": int(c),
            "n1m_mean_ms": float(r_1m["mean_ms"]),
            "n1m_sd_ms": float(r_1m["sd_ms"]),
            "n1m_ci95_ms": float(r_1m["ci95_ms"]),
            "n1m_improvement_pct": float(r_1m["improvement_pct"]),
            "multiscale_rel_pct": float(r_ms["mean_rel_pct"]),
            "multiscale_improvement_pct": float(r_ms["mean_improvement_pct"]),
            "multiscale_speedup": float(r_ms["mean_speedup"]),
        }

    opt_cutoff_ms = int(best_ms_row["cutoff"])
    opt_cutoff_1m = int(best_n1m_row["cutoff"])

    # Tìm dải tối ưu thực tế (trong phạm vi +1.5% so với mức cực tiểu đa quy mô)
    min_rel = float(best_ms_row["mean_rel_pct"])
    plateau_cutoffs = ms_agg[ms_agg["mean_rel_pct"] <= min_rel + 1.5]["cutoff"].astype(int).tolist()

    # Paired test giữa CUTOFF=7, CUTOFF=10 và opt_cutoff_ms trên 9 bộ dữ liệu đa quy mô
    piv_ms = multiscale_sets.pivot(index="dataset", columns="cutoff", values="relative_pct")
    t_7_10, p_7_10 = stats.ttest_rel(piv_ms[7], piv_ms[10])
    t_7_opt, p_7_opt = stats.ttest_rel(piv_ms[7], piv_ms[opt_cutoff_ms])
    t_10_opt, p_10_opt = stats.ttest_rel(piv_ms[10], piv_ms[opt_cutoff_ms])

    findings = {
        "best_cutoff_multiscale": opt_cutoff_ms,
        "best_cutoff_n1m": opt_cutoff_1m,
        "optimal_plateau_within_1_5pct": plateau_cutoffs,
        "baseline_0": get_cutoff_metric_ms(0),
        "baseline_1": get_cutoff_metric_ms(1),
        "textbook_old_7": get_cutoff_metric_ms(7),
        "textbook_new_10": get_cutoff_metric_ms(10),
        "optimal_multiscale": get_cutoff_metric_ms(opt_cutoff_ms),
        "optimal_n1m": get_cutoff_metric_ms(opt_cutoff_1m),
        "paired_tests_multiscale": {
            "7_vs_10": {"t_stat": float(t_7_10), "p_value": float(p_7_10)},
            "7_vs_opt": {"t_stat": float(t_7_opt), "p_value": float(p_7_opt)},
            "10_vs_opt": {"t_stat": float(t_10_opt), "p_value": float(p_10_opt)},
        },
        "per_dataset_best": {},
    }

    for ds_name, grp in summary_df.groupby("dataset"):
        b = grp.loc[grp["mean_ms"].idxmin()]
        findings["per_dataset_best"][ds_name] = {
            "n": int(b["n"]),
            "category": str(b["category"]),
            "best_cutoff": int(b["cutoff"]),
            "best_mean_ms": float(b["mean_ms"]),
            "baseline_mean_ms": float(b["baseline_ms"]),
            "max_improvement_pct": float(b["improvement_pct"]),
        }

    with open(res_dir / "key_findings.json", "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2, ensure_ascii=False)

    # =========================================================================
    # HÌNH 1: Đường cong tổng quan CUTOFF [0..128] trên N=1,000,000 & Đa quy mô
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 5.2))

    ax1.plot(n1m["cutoff"], n1m["mean_ms"], "-o", color="#1d4ed8", markersize=3.8, linewidth=1.8, label="Mean (N = 1,000,000)")
    ax1.fill_between(n1m["cutoff"], n1m["ci95_low_ms"], n1m["ci95_high_ms"], color="#3b82f6", alpha=0.2, label="Khoảng tin cậy 95% CI")
    ax1.axvline(7, color="#d97706", linestyle="--", linewidth=1.3, label="CUTOFF = 7 (Giáo trình cũ)")
    ax1.axvline(10, color="#059669", linestyle="-.", linewidth=1.3, label="CUTOFF = 10 (Giáo trình mới)")
    ax1.axvline(opt_cutoff_1m, color="#dc2626", linestyle=":", linewidth=1.7, label=f"Tối ưu N=1M (CUTOFF = {opt_cutoff_1m})")
    ax1.scatter([opt_cutoff_1m], [best_n1m_row["mean_ms"]], color="#dc2626", s=65, zorder=5)
    ax1.set_title("(a) Thời gian thực thi tuyệt đối tại N = 1,000,000")
    ax1.set_xlabel("Giá trị CUTOFF (độ dài mảng con dùng Insertion Sort)")
    ax1.set_ylabel("Thời gian chạy trung bình (ms)")
    ax1.legend(loc="upper right")

    ax2.plot(ms_agg["cutoff"], ms_agg["mean_rel_pct"], "-s", color="#7c3aed", markersize=3.8, linewidth=1.8, label="Thời gian chuẩn hóa trung bình (9 quy mô N)")
    ax2.fill_between(
        ms_agg["cutoff"],
        ms_agg["mean_rel_pct"] - ms_agg["ci95_rel_pct"],
        ms_agg["mean_rel_pct"] + ms_agg["ci95_rel_pct"],
        color="#8b5cf6", alpha=0.18, label="Khoảng tin cậy 95% CI liên quy mô"
    )
    ax2.axhline(100.0, color="#64748b", linestyle=":", linewidth=1.1, label="Baseline Mergesort thuần (100%)")
    ax2.axvline(7, color="#d97706", linestyle="--", linewidth=1.3, label="CUTOFF = 7")
    ax2.axvline(10, color="#059669", linestyle="-.", linewidth=1.3, label="CUTOFF = 10")
    ax2.axvline(opt_cutoff_ms, color="#dc2626", linestyle=":", linewidth=1.7, label=f"Tối ưu đa quy mô (CUTOFF = {opt_cutoff_ms})")
    ax2.scatter([opt_cutoff_ms], [best_ms_row["mean_rel_pct"]], color="#dc2626", s=65, zorder=5)
    ax2.set_title("(b) Thời gian chuẩn hóa trung bình trên 9 bộ dữ liệu [100k..1M]")
    ax2.set_xlabel("Giá trị CUTOFF")
    ax2.set_ylabel("Thời gian so với Mergesort thuần (%)")
    ax2.legend(loc="upper right")

    fig.suptitle("Đường cong chữ U bất đối xứng của cải tiến CUTOFF trên Apple M4 (JDK 25)", fontsize=13.5, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig1_overview_cutoff_curves.png", bbox_inches="tight")
    plt.close(fig)

    # =========================================================================
    # HÌNH 2: Phóng đại miền lân cận tối ưu CUTOFF [0..36] kèm 95% CI & % Speedup
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 5.2))
    zoom_1m = n1m[n1m["cutoff"] <= 36]
    zoom_ms = ms_agg[ms_agg["cutoff"] <= 36]

    ax1.errorbar(
        zoom_1m["cutoff"], zoom_1m["mean_ms"], yerr=zoom_1m["ci95_ms"],
        fmt="-o", color="#1e40af", ecolor="#93c5fd", elinewidth=1.4, capsize=2.8, markersize=4.5,
        label="Mean ± 95% CI (N = 1,000,000)"
    )
    for c, col, lbl in [(7, "#d97706", "CUTOFF=7"), (10, "#059669", "CUTOFF=10"), (opt_cutoff_1m, "#dc2626", f"Min={opt_cutoff_1m}")]:
        row_c = zoom_1m[zoom_1m["cutoff"] == c]
        if not row_c.empty:
            ax1.scatter(row_c["cutoff"], row_c["mean_ms"], color=col, s=75, zorder=6, label=f"{lbl}: {row_c['mean_ms'].values[0]:.2f} ms")
    ax1.set_title("(a) Phóng đại CUTOFF ∈ [0..36] tại N = 1,000,000")
    ax1.set_xlabel("Giá trị CUTOFF (bước nhảy Δ = 1)")
    ax1.set_ylabel("Thời gian chạy trung bình (ms)")
    ax1.set_xticks(range(0, 37, 2))
    ax1.legend(loc="upper right")

    ax2.errorbar(
        zoom_ms["cutoff"], zoom_ms["mean_improvement_pct"], yerr=zoom_ms["ci95_rel_pct"],
        fmt="-s", color="#0f766e", ecolor="#5eead4", elinewidth=1.4, capsize=2.8, markersize=4.5,
        label="% Cải thiện trung bình ± 95% CI"
    )
    if plateau_cutoffs:
        p_lo, p_hi = min(plateau_cutoffs), max(plateau_cutoffs)
        ax2.axvspan(p_lo, p_hi, color="#fef08a", alpha=0.38, label=f"Vùng đáy tối ưu [{p_lo}..{p_hi}] (sai lệch ≤ 1.5%)")
    ax2.axvline(7, color="#d97706", linestyle="--", linewidth=1.3, label="CUTOFF = 7")
    ax2.axvline(10, color="#059669", linestyle="-.", linewidth=1.3, label="CUTOFF = 10")
    ax2.axvline(opt_cutoff_ms, color="#dc2626", linestyle=":", linewidth=1.7, label=f"Đỉnh cải thiện (CUTOFF = {opt_cutoff_ms})")
    ax2.set_title("(b) Tỷ lệ cải thiện tốc độ trung bình trên 9 quy mô N ∈ [100k..1M]")
    ax2.set_xlabel("Giá trị CUTOFF (bước nhảy Δ = 1)")
    ax2.set_ylabel("Mức giảm thời gian chạy so với Baseline (%)")
    ax2.set_xticks(range(0, 37, 2))
    ax2.legend(loc="lower right")

    fig.suptitle("Phân tích chi tiết vùng lân cận tối ưu CUTOFF ∈ [0..36]", fontsize=13.5, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig2_zoom_optimal_region_ci95.png", bbox_inches="tight")
    plt.close(fig)

    # =========================================================================
    # HÌNH 3: Hiệu ứng bậc thang lượng tử hóa kích thước mảng con theo N
    # =========================================================================
    fig, ax = plt.subplots(figsize=(11.2, 5.4))
    step_datasets = [
        ("random_N262144_pow2.txt", "N = 262,144 = 2¹⁸ (lá lũy thừa 2: 4, 8, 16, 32)", "#dc2626", "-o"),
        ("random_N180000.txt",      "N = 180,000 (lá: 5/6, 10/11, 21/22)",              "#2563eb", "-s"),
        ("random_N100000.txt",      "N = 100,000 (lá: 6/7, 12/13, 24/25)",              "#059669", "-^"),
        ("random_N1000000.txt",     "N = 1,000,000 (lá: 7/8, 15/16, 30/31)",            "#7c3aed", "-D"),
    ]
    for fname, label, color, style in step_datasets:
        sub = summary_df[(summary_df["dataset"] == fname) & (summary_df["cutoff"] <= 36)].sort_values("cutoff")
        ax.plot(sub["cutoff"], sub["relative_pct"], style, color=color, markersize=4.2, linewidth=1.65, label=label)

    sub_ms = ms_agg[ms_agg["cutoff"] <= 36]
    ax.plot(
        sub_ms["cutoff"], sub_ms["mean_rel_pct"], "--", color="#111827", linewidth=2.4,
        label="Trung bình đa quy mô (triệt tiêu bậc thang cục bộ)"
    )
    for k_pow2 in [2, 4, 8, 16, 32]:
        ax.axvline(k_pow2, color="#fca5a5", linestyle=":", linewidth=1.0)

    ax.set_title("Hiện tượng bậc thang (Subarray Quantization) trong Top-down Mergesort theo kích thước N")
    ax.set_xlabel("Giá trị CUTOFF")
    ax.set_ylabel("Thời gian chạy chuẩn hóa so với CUTOFF = 0 (%)")
    ax.set_xticks(range(0, 37, 2))
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(fig_dir / "fig3_step_effect_quantization.png", bbox_inches="tight")
    plt.close(fig)

    # =========================================================================
    # HÌNH 4: Mô hình chi phí lý thuyết & thực nghiệm (Cost Model - Chủ đề 1.3)
    # =========================================================================
    c1m = cost_df[cost_df["dataset"] == "random_N1000000.txt"].sort_values("cutoff")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 5.2))

    ax1_twin = ax1.twinx()
    ax1_twin.spines["top"].set_visible(False)
    p1 = ax1.plot(c1m["cutoff"], c1m["recursive_calls"] / 1e6, "-o", color="#dc2626", markersize=4, linewidth=1.8, label="Số lời gọi đệ quy (triệu lần)")
    p2 = ax1_twin.plot(c1m["cutoff"], c1m["array_writes"] / 1e6, "-s", color="#2563eb", markersize=4, linewidth=1.8, label="Tổng số phép ghi mảng (triệu lần)")
    ax1.set_title("(a) Giảm chi phí đệ quy & ghi mảng khi tăng CUTOFF (N = 1M)")
    ax1.set_xlabel("Giá trị CUTOFF")
    ax1.set_ylabel("Số lời gọi đệ quy (× 10⁶)", color="#dc2626")
    ax1_twin.set_ylabel("Số phép ghi mảng aux/a/exch (× 10⁶)", color="#2563eb")
    ax1_twin.grid(False)
    lines = p1 + p2
    ax1.legend(lines, [l.get_label() for l in lines], loc="center right")

    ax2.plot(c1m["cutoff"], c1m["total_compares"] / 1e6, "-o", color="#111827", markersize=4, linewidth=1.9, label="Tổng số phép so sánh (Merge + Insertion)")
    ax2.plot(c1m["cutoff"], c1m["merge_compares"] / 1e6, "--^", color="#059669", markersize=3.8, linewidth=1.5, label="Số phép so sánh trong Merge")
    ax2.plot(c1m["cutoff"], c1m["insert_compares"] / 1e6, ":d", color="#d97706", markersize=3.8, linewidth=1.6, label="Số phép so sánh trong Insertion Sort")
    ax2.axvline(7, color="#d97706", linestyle="--", alpha=0.6)
    ax2.axvline(10, color="#059669", linestyle="-.", alpha=0.6)
    ax2.axvline(opt_cutoff_ms, color="#dc2626", linestyle=":", linewidth=1.5, label=f"CUTOFF tối ưu = {opt_cutoff_ms}")
    ax2.set_title("(b) Đánh đổi số phép so sánh khóa less() tại N = 1,000,000")
    ax2.set_xlabel("Giá trị CUTOFF")
    ax2.set_ylabel("Số lượng phép so sánh (× 10⁶)")
    ax2.legend(loc="upper left")

    fig.suptitle("Giải thích cơ chế tối ưu qua Mô hình Chi phí (Cost Model - Chủ đề 1.3)", fontsize=13.5, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig4_cost_model_tradeoff.png", bbox_inches="tight")
    plt.close(fig)

    # =========================================================================
    # HÌNH 5: So sánh ảnh hưởng của các phân phối dữ liệu đầu vào khác nhau
    # =========================================================================
    fig, ax = plt.subplots(figsize=(11.0, 5.3))
    dist_specs = [
        ("random_N220000.txt",         "Ngẫu nhiên phân phối đều (Uniform Random)",       "#1d4ed8", "-o"),
        ("nearly_sorted_N200000.txt",  "Gần như đã sắp xếp (Nearly Sorted - 2% tráo)",    "#059669", "-s"),
        ("reverse_sorted_N200000.txt", "Sắp xếp ngược giảm dần (Reverse Sorted - Worst)", "#dc2626", "-^"),
        ("few_unique_N200000.txt",     "Nhiều khóa trùng lặp (Few Unique - 50 giá trị)",  "#7c3aed", "-D"),
    ]
    for fname, label, color, style in dist_specs:
        sub = summary_df[summary_df["dataset"] == fname].sort_values("cutoff")
        ax.plot(sub["cutoff"], sub["relative_pct"], style, color=color, markersize=4.0, linewidth=1.75, label=label)

    ax.axhline(100.0, color="#64748b", linestyle=":", linewidth=1.1)
    ax.axvline(7, color="#d97706", linestyle="--", linewidth=1.2, label="CUTOFF = 7")
    ax.axvline(10, color="#059669", linestyle="-.", linewidth=1.2, label="CUTOFF = 10")
    ax.axvline(opt_cutoff_ms, color="#111827", linestyle=":", linewidth=1.6, label=f"CUTOFF đề xuất = {opt_cutoff_ms}")
    ax.set_title("Độ nhạy của CUTOFF đối với các phân phối dữ liệu đầu vào khác nhau (N ≈ 200,000)")
    ax.set_xlabel("Giá trị CUTOFF")
    ax.set_ylabel("Thời gian chạy so với Baseline CUTOFF = 0 của từng phân phối (%)")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(fig_dir / "fig5_distributions_impact.png", bbox_inches="tight")
    plt.close(fig)

    # =========================================================================
    # HÌNH 6: Đối chứng Comparable[] (Integer[] chuẩn bài giảng) vs int[] nguyên thủy
    # =========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 5.0))
    p500_obj = prim_summary[(prim_summary["dataset"] == "random_N500000.txt") & (prim_summary["representation"] == "comparable_integer")].sort_values("cutoff")
    p500_int = prim_summary[(prim_summary["dataset"] == "random_N500000.txt") & (prim_summary["representation"] == "primitive_int")].sort_values("cutoff")

    ax1.plot(p500_obj["cutoff"], p500_obj["mean_ms"], "-o", color="#1d4ed8", markersize=4, linewidth=1.8, label="Comparable[] (Integer[] - Chuẩn bài giảng)")
    ax1.plot(p500_int["cutoff"], p500_int["mean_ms"], "-s", color="#ea580c", markersize=4, linewidth=1.8, label="Primitive int[] (Mảng nguyên thủy thanh ghi)")
    ax1.set_title("(a) Thời gian chạy tuyệt đối tại N = 500,000")
    ax1.set_xlabel("Giá trị CUTOFF")
    ax1.set_ylabel("Thời gian chạy trung bình (ms)")
    ax1.legend(loc="upper right")

    sub_obj = p500_obj[p500_obj["cutoff"] <= 48]
    sub_int = p500_int[p500_int["cutoff"] <= 48]
    best_obj_c = int(sub_obj.loc[sub_obj["mean_ms"].idxmin()]["cutoff"])
    best_int_c = int(sub_int.loc[sub_int["mean_ms"].idxmin()]["cutoff"])

    ax2.plot(sub_obj["cutoff"], sub_obj["relative_pct"], "-o", color="#1d4ed8", markersize=4, linewidth=1.8, label=f"Comparable[] (Min tại CUTOFF = {best_obj_c})")
    ax2.plot(sub_int["cutoff"], sub_int["relative_pct"], "-s", color="#ea580c", markersize=4, linewidth=1.8, label=f"Primitive int[] (Min tại CUTOFF = {best_int_c})")
    ax2.axvline(best_obj_c, color="#1d4ed8", linestyle=":", linewidth=1.4)
    ax2.axvline(best_int_c, color="#ea580c", linestyle="--", linewidth=1.4)
    ax2.set_title("(b) So sánh chuẩn hóa (%) và sự dịch chuyển ngưỡng CUTOFF tối ưu")
    ax2.set_xlabel("Giá trị CUTOFF (miền [0..48])")
    ax2.set_ylabel("Thời gian chạy so với CUTOFF = 0 (%)")
    ax2.legend(loc="upper right")

    fig.suptitle("Ảnh hưởng của cơ chế biểu diễn dữ liệu trên JVM (Comparable[] vs int[])", fontsize=13.5, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig6_comparable_vs_primitive.png", bbox_inches="tight")
    plt.close(fig)

    print("Hoàn tất phân tích thống kê và xuất 6 đồ thị vào:", fig_dir)
    print(f"-> CUTOFF tối ưu đa quy mô: {opt_cutoff_ms} (vùng đáy 1.5%: {plateau_cutoffs})")
    print(f"-> CUTOFF tối ưu tại N=1,000,000: {opt_cutoff_1m}")


if __name__ == "__main__":
    main()
