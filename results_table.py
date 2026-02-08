#!/usr/bin/env python3
"""Generate concise comparison tables from regex benchmark JSON outputs."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from statistics import mean, median

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build dataset and library summary tables from benchmark JSON files."
    )
    parser.add_argument(
        "--py",
        type=Path,
        default=Path("py_redos_test_results.json"),
        help="Path to Python results JSON.",
    )
    parser.add_argument(
        "--ts",
        type=Path,
        default=Path("ts_redos_test_results.json"),
        help="Path to TypeScript results JSON.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("images/results_table.png"),
        help="Output image path for the table figure.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=250,
        help="Output image DPI.",
    )
    parser.add_argument(
        "--graphs-dir",
        type=Path,
        default=None,
        help="Directory for extra chart outputs (default: same directory as --out).",
    )
    return parser.parse_args()


def to_result_dict(raw_result: object) -> dict:
    if isinstance(raw_result, dict):
        return raw_result
    if isinstance(raw_result, str):
        return ast.literal_eval(raw_result)
    raise TypeError(f"Unsupported result payload type: {type(raw_result)}")


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = (len(sorted_values) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def load_dataset(path: Path, label: str) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    metadata = data["metadata"]
    results = data["results"]
    summary = data["summary_stats"]

    tests_with_timeout: set[int] = set()
    lib_timeout_tests: dict[str, set[int]] = {lib: set() for lib in metadata["libraries"]}
    lib_times_ms: dict[str, list[float]] = {lib: [] for lib in metadata["libraries"]}

    for row in results:
        parsed = to_result_dict(row["result"])
        lib = row["library"]
        test_id = row["test_id"]
        lib_times_ms[lib].append(parsed["time"] * 1000.0)
        if parsed.get("timed_out"):
            tests_with_timeout.add(test_id)
            lib_timeout_tests[lib].add(test_id)

    dataset_row = {
        "dataset": label,
        "file": str(path),
        "tests": metadata["total_tests"],
        "runs_per_test": metadata["total_runs"],
        "libraries": metadata["total_libraries"],
        "executions": len(results),
        "tests_with_timeout": len(tests_with_timeout),
    }

    library_rows = []
    for lib in metadata["libraries"]:
        lib_summary = summary[lib]
        executions = lib_summary["total_count"]
        timeouts = lib_summary["timeout_count"]
        times = sorted(lib_times_ms[lib])
        library_rows.append(
            {
                "dataset": label,
                "library": lib,
                "executions": executions,
                "timeouts": timeouts,
                "timeout_rate": (timeouts / executions) * 100 if executions else 0.0,
                "tests_with_timeout": len(lib_timeout_tests[lib]),
                "mean_ms": mean(times),
                "median_ms": median(times),
                "p95_ms": percentile(times, 0.95),
                "max_ms": max(times) if times else 0.0,
            }
        )

    return {"dataset_row": dataset_row, "library_rows": library_rows}


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_float(value: float) -> str:
    return f"{value:.2f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([header_line, sep_line, *body])


def draw_table(ax, headers: list[str], rows: list[list[str]], title: str, font_size: int) -> None:
    ax.axis("off")
    table = ax.table(
        cellText=rows,
        colLabels=headers,
        loc="center",
        cellLoc="center",
        colLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1, 1.5)

    for col_idx in range(len(headers)):
        cell = table[0, col_idx]
        cell.set_facecolor("#263238")
        cell.set_text_props(color="white", weight="bold")

    for row_idx in range(1, len(rows) + 1):
        for col_idx in range(len(headers)):
            cell = table[row_idx, col_idx]
            if row_idx % 2 == 0:
                cell.set_facecolor("#f5f7fa")
            else:
                cell.set_facecolor("white")

    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)


def save_matplotlib_tables(
    dataset_headers: list[str],
    dataset_rows: list[list[str]],
    library_headers: list[str],
    library_rows: list[list[str]],
    output_path: Path,
    dpi: int,
) -> None:
    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 2.2], hspace=0.25)

    ax_top = fig.add_subplot(gs[0, 0])
    draw_table(
        ax_top,
        dataset_headers,
        dataset_rows,
        title="Regex Benchmark Dataset Summary",
        font_size=10,
    )

    ax_bottom = fig.add_subplot(gs[1, 0])
    draw_table(
        ax_bottom,
        library_headers,
        library_rows,
        title="Regex Benchmark Library Performance Summary",
        font_size=9,
    )

    fig.suptitle("Combined Results from Python + TypeScript Benchmarks", fontsize=14, fontweight="bold")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def dataset_color(dataset: str) -> str:
    if dataset == "Python":
        return "#1f77b4"
    if dataset == "TypeScript":
        return "#ff7f0e"
    return "#7f7f7f"


def save_overall_dashboard(library_rows: list[dict], output_path: Path, dpi: int) -> None:
    sorted_rows = sorted(library_rows, key=lambda r: (r["dataset"], r["library"]))
    labels = [f'{row["dataset"]}:{row["library"]}' for row in sorted_rows]
    colors = [dataset_color(row["dataset"]) for row in sorted_rows]
    mean_ms = [row["mean_ms"] for row in sorted_rows]
    timeout_pct = [row["timeout_rate"] for row in sorted_rows]

    fig = plt.figure(figsize=(18, 11))
    gs = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.25)

    ax1 = fig.add_subplot(gs[0, 0])
    y_pos = np.arange(len(labels))
    bars = ax1.barh(y_pos, mean_ms, color=colors, alpha=0.9)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(labels, fontsize=9)
    ax1.invert_yaxis()
    ax1.set_xlabel("Mean Time (ms)")
    ax1.set_title("Average Speed by Library")
    ax1.grid(axis="x", alpha=0.3, linestyle="--")
    for bar, val in zip(bars, mean_ms):
        ax1.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f" {val:.2f}", va="center", fontsize=8)

    ax2 = fig.add_subplot(gs[0, 1])
    bars2 = ax2.bar(labels, timeout_pct, color=colors, alpha=0.9)
    ax2.set_ylabel("Timeout Rate (%)")
    ax2.set_title("Failure Rate by Library")
    ax2.set_xticks(range(len(labels)))
    ax2.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax2.grid(axis="y", alpha=0.3, linestyle="--")
    for bar, val in zip(bars2, timeout_pct):
        ax2.text(bar.get_x() + bar.get_width() / 2.0, bar.get_height(), f"{val:.2f}%", ha="center", va="bottom", fontsize=8)

    ax3 = fig.add_subplot(gs[1, :])
    for row in sorted_rows:
        x = row["mean_ms"]
        y = row["timeout_rate"]
        ax3.scatter(
            x,
            y,
            s=90,
            color=dataset_color(row["dataset"]),
            edgecolor="black",
            linewidth=0.7,
            alpha=0.9,
        )
        ax3.text(x, y, f' {row["dataset"]}:{row["library"]}', fontsize=8, va="center")
    ax3.set_xlabel("Mean Time (ms)")
    ax3.set_ylabel("Timeout Rate (%)")
    ax3.set_title("Speed vs Failure Tradeoff")
    ax3.grid(alpha=0.3, linestyle="--")

    fig.suptitle("Regex Benchmark Overview", fontsize=15, fontweight="bold")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def save_speed_chart(library_rows: list[dict], output_path: Path, dpi: int) -> None:
    sorted_rows = sorted(library_rows, key=lambda r: r["mean_ms"])
    labels = [f'{row["dataset"]}:{row["library"]}' for row in sorted_rows]
    x = np.arange(len(labels))

    mean_vals = [row["mean_ms"] for row in sorted_rows]
    median_vals = [row["median_ms"] for row in sorted_rows]
    p95_vals = [row["p95_ms"] for row in sorted_rows]

    width = 0.25
    fig, ax = plt.subplots(figsize=(16, 7))
    ax.bar(x - width, median_vals, width=width, color="#2ca02c", label="Median (ms)")
    ax.bar(x, mean_vals, width=width, color="#1f77b4", label="Mean (ms)")
    ax.bar(x + width, p95_vals, width=width, color="#d62728", label="P95 (ms)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Execution Time (ms)")
    ax.set_title("Speed Breakdown (Median / Mean / P95)")
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.legend()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def save_failure_chart(library_rows: list[dict], output_path: Path, dpi: int) -> None:
    sorted_rows = sorted(library_rows, key=lambda r: (-r["timeout_rate"], -r["timeouts"], r["dataset"], r["library"]))
    labels = [f'{row["dataset"]}:{row["library"]}' for row in sorted_rows]
    x = np.arange(len(labels))

    timeout_rate = [row["timeout_rate"] for row in sorted_rows]
    timeout_counts = [row["timeouts"] for row in sorted_rows]
    timeout_tests = [row["tests_with_timeout"] for row in sorted_rows]

    fig, ax1 = plt.subplots(figsize=(16, 7))
    bars = ax1.bar(x, timeout_rate, color="#9467bd", alpha=0.9, label="Timeout Rate (%)")
    ax1.set_ylabel("Timeout Rate (%)", color="#9467bd")
    ax1.tick_params(axis="y", labelcolor="#9467bd")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax1.set_title("Failure Breakdown by Library")
    ax1.grid(axis="y", alpha=0.25, linestyle="--")

    ax2 = ax1.twinx()
    ax2.plot(x, timeout_counts, color="#d62728", marker="o", linewidth=2, label="Timeout Count")
    ax2.plot(x, timeout_tests, color="#ff9896", marker="s", linewidth=2, label="Tests with Timeout")
    ax2.set_ylabel("Counts", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")

    for bar, pct in zip(bars, timeout_rate):
        ax1.text(bar.get_x() + bar.get_width() / 2.0, bar.get_height(), f"{pct:.2f}%", ha="center", va="bottom", fontsize=8)

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, loc="upper right")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def save_speed_vs_failure_scatter(library_rows: list[dict], output_path: Path, dpi: int) -> None:
    fig, ax = plt.subplots(figsize=(11, 8))
    for row in library_rows:
        x = row["mean_ms"]
        y = row["timeout_rate"]
        size = 30 + min(row["executions"] / 4.0, 140)
        ax.scatter(
            x,
            y,
            s=size,
            color=dataset_color(row["dataset"]),
            alpha=0.85,
            edgecolor="black",
            linewidth=0.7,
        )
        ax.text(x, y, f' {row["library"]} ({row["dataset"]})', fontsize=9, va="center")

    ax.set_xlabel("Mean Time (ms)")
    ax.set_ylabel("Timeout Rate (%)")
    ax.set_title("Speed vs Failure Rate")
    ax.grid(alpha=0.3, linestyle="--")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()

    datasets = [
        load_dataset(args.py, "Python"),
        load_dataset(args.ts, "TypeScript"),
    ]

    dataset_rows = [d["dataset_row"] for d in datasets]
    library_rows = [r for d in datasets for r in d["library_rows"]]
    library_rows.sort(key=lambda r: (r["dataset"], -r["timeouts"], -r["mean_ms"], r["library"]))

    dataset_headers = [
        "Dataset",
        "File",
        "Tests",
        "Runs/Test",
        "Libraries",
        "Executions",
        "Tests w/ Timeout",
    ]
    dataset_table_rows = [
        [
            row["dataset"],
            row["file"],
            fmt_int(row["tests"]),
            fmt_int(row["runs_per_test"]),
            fmt_int(row["libraries"]),
            fmt_int(row["executions"]),
            fmt_int(row["tests_with_timeout"]),
        ]
        for row in dataset_rows
    ]

    library_headers = [
        "Dataset",
        "Library",
        "Executions",
        "Timeouts",
        "Timeout %",
        "Timeout Tests",
        "Mean (ms)",
        "Median (ms)",
        "P95 (ms)",
        "Max (ms)",
    ]
    library_table_rows = [
        [
            row["dataset"],
            row["library"],
            fmt_int(row["executions"]),
            fmt_int(row["timeouts"]),
            fmt_float(row["timeout_rate"]),
            fmt_int(row["tests_with_timeout"]),
            fmt_float(row["mean_ms"]),
            fmt_float(row["median_ms"]),
            fmt_float(row["p95_ms"]),
            fmt_float(row["max_ms"]),
        ]
        for row in library_rows
    ]

    save_matplotlib_tables(
        dataset_headers,
        dataset_table_rows,
        library_headers,
        library_table_rows,
        output_path=args.out,
        dpi=args.dpi,
    )
    print(f"Saved table image to {args.out}")

    graphs_dir = args.graphs_dir if args.graphs_dir is not None else args.out.parent
    save_overall_dashboard(library_rows, graphs_dir / "results_overall_dashboard.png", args.dpi)
    save_speed_chart(library_rows, graphs_dir / "results_speed_breakdown.png", args.dpi)
    save_failure_chart(library_rows, graphs_dir / "results_failure_breakdown.png", args.dpi)
    save_speed_vs_failure_scatter(library_rows, graphs_dir / "results_speed_vs_failure.png", args.dpi)
    print(f"Saved extra charts to {graphs_dir}")


if __name__ == "__main__":
    main()
