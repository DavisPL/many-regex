#!/usr/bin/env python3
"""Generate concise comparison tables from regex benchmark JSON outputs."""

from __future__ import annotations

import argparse
import ast
import glob
import json
from pathlib import Path
from statistics import mean, median

import matplotlib.pyplot as plt
import numpy as np

LANGUAGE_COLORS = {
    "Python": "#1f77b4",  # blue
    "C#": "#9467bd",  # purple
    "TypeScript": "#f2c200",  # yellow
}

METRIC_COLORS = {
    "green": "#2ca02c",
    "orange": "#ff8c00",
    "red": "#d62728",
}


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
        type=str,
        nargs="+",
        default=["ts_redos_test_results.json"],
        help="TypeScript results JSON path(s) or glob pattern(s).",
    )
    parser.add_argument(
        "--cs",
        type=Path,
        default=Path("csharp_redos_test_results.json"),
        help="Path to C# results JSON.",
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


def expand_input_paths(raw_paths: list[str], arg_name: str) -> list[Path]:
    expanded: list[Path] = []
    for raw_path in raw_paths:
        matches = sorted(Path(match) for match in glob.glob(raw_path))
        if matches:
            expanded.extend(path for path in matches if path.is_file())
        else:
            candidate = Path(raw_path)
            if candidate.exists() and candidate.is_file():
                expanded.append(candidate)
            else:
                raise FileNotFoundError(f"No files matched {arg_name} value: {raw_path}")

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in expanded:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_paths.append(path)
    return unique_paths


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_float(value: float) -> str:
    return f"{value:.2f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([header_line, sep_line, *body])


def parse_numeric_cell(cell: str) -> float | None:
    cleaned = cell.replace(",", "").replace("%", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def blend_with_white(color: str, amount: float) -> str:
    r, g, b = hex_to_rgb(color)
    mixed = (
        int((1 - amount) * 255 + amount * r),
        int((1 - amount) * 255 + amount * g),
        int((1 - amount) * 255 + amount * b),
        )
    return rgb_to_hex(mixed)


def interpolate_color(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    mixed = (
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )
    return rgb_to_hex(mixed)


def metric_heat_color(value: float, min_val: float, max_val: float) -> str:
    if max_val <= min_val:
        return blend_with_white(METRIC_COLORS["orange"], 0.35)
    t = (value - min_val) / (max_val - min_val)
    if t <= 0.5:
        return blend_with_white(interpolate_color(METRIC_COLORS["green"], METRIC_COLORS["orange"], t * 2.0), 0.38)
    return blend_with_white(interpolate_color(METRIC_COLORS["orange"], METRIC_COLORS["red"], (t - 0.5) * 2.0), 0.38)


def draw_table(
    ax,
    headers: list[str],
    rows: list[list[str]],
    title: str,
    font_size: int,
    col_widths: list[float] | None = None,
) -> None:
    ax.axis("off")
    table = ax.table(
        cellText=rows,
        colLabels=headers,
        loc="center",
        cellLoc="center",
        colLoc="center",
        colWidths=col_widths,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1, 1.5)

    for col_idx in range(len(headers)):
        cell = table[0, col_idx]
        cell.set_facecolor("#263238")
        cell.set_text_props(color="white", weight="bold")

    dataset_col_idx = headers.index("Dataset") if "Dataset" in headers else None
    timeout_cols = {
        i
        for i, h in enumerate(headers)
        if h in {"Timeouts", "Timeout %", "Timeout Tests", "Tests w/ Timeout"}
    }
    timeout_bad_cols = {i for i, h in enumerate(headers) if h in {"Timeout Tests", "Tests w/ Timeout"}}
    speed_cols = {i for i, h in enumerate(headers) if h in {"Mean (ms)", "Median (ms)", "P95 (ms)", "Max (ms)"}}
    metric_cols = timeout_cols | speed_cols

    metric_ranges: dict[int, tuple[float, float]] = {}
    for col_idx in metric_cols:
        values: list[float] = []
        for row in rows:
            parsed = parse_numeric_cell(row[col_idx])
            if parsed is not None:
                values.append(parsed)
        if values:
            metric_ranges[col_idx] = (min(values), max(values))

    for row_idx in range(1, len(rows) + 1):
        dataset_value = rows[row_idx - 1][dataset_col_idx] if dataset_col_idx is not None else None
        row_tint = blend_with_white(dataset_color(dataset_value), 0.08) if dataset_value else None
        for col_idx in range(len(headers)):
            cell = table[row_idx, col_idx]
            base_color = "#f5f7fa" if row_idx % 2 == 0 else "white"
            cell.set_facecolor(row_tint if row_tint is not None else base_color)
            if dataset_col_idx is not None and col_idx == dataset_col_idx:
                cell.set_facecolor(blend_with_white(dataset_color(rows[row_idx - 1][col_idx]), 0.25))
                cell.set_text_props(weight="bold")
                continue
            if col_idx in metric_ranges:
                value = parse_numeric_cell(rows[row_idx - 1][col_idx])
                if value is not None:
                    if col_idx in timeout_bad_cols and value > 0:
                        cell.set_facecolor(blend_with_white(METRIC_COLORS["red"], 0.3))
                        continue
                    min_val, max_val = metric_ranges[col_idx]
                    cell.set_facecolor(metric_heat_color(value, min_val, max_val))

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
    dataset_col_widths = [0.13, 0.26, 0.13, 0.13, 0.13, 0.13, 0.14]
    draw_table(
        ax_top,
        dataset_headers,
        dataset_rows,
        title="Regex Benchmark Dataset Summary",
        font_size=10,
        col_widths=dataset_col_widths,
    )

    ax_bottom = fig.add_subplot(gs[1, 0])
    draw_table(
        ax_bottom,
        library_headers,
        library_rows,
        title="Regex Benchmark Library Performance Summary",
        font_size=9,
    )

    fig.suptitle("Combined Results from Python + TypeScript + C# Benchmarks", fontsize=14, fontweight="bold")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def dataset_color(dataset: str) -> str:
    for language, color in LANGUAGE_COLORS.items():
        if dataset == language or dataset.startswith(f"{language} ("):
            return color
    return "#7f7f7f"


def save_overall_dashboard(library_rows: list[dict], output_path: Path, dpi: int) -> None:
    sorted_rows = sorted(library_rows, key=lambda r: (r["dataset"], r["library"]))
    labels = [f'{row["dataset"]}:{row["library"]}' for row in sorted_rows]
    lang_colors = [dataset_color(row["dataset"]) for row in sorted_rows]
    mean_ms = [row["mean_ms"] for row in sorted_rows]
    timeout_pct = [row["timeout_rate"] for row in sorted_rows]

    fig = plt.figure(figsize=(18, 11))
    gs = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.25)

    ax1 = fig.add_subplot(gs[0, 0])
    y_pos = np.arange(len(labels))
    bars = ax1.barh(y_pos, mean_ms, color=METRIC_COLORS["orange"], alpha=0.9)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(labels, fontsize=9)
    ax1.invert_yaxis()
    ax1.set_xlabel("Mean Time (ms)")
    ax1.set_title("Average Speed by Library")
    ax1.grid(axis="x", alpha=0.3, linestyle="--")
    for bar, val in zip(bars, mean_ms):
        ax1.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f" {val:.2f}", va="center", fontsize=8)

    ax2 = fig.add_subplot(gs[0, 1])
    bars2 = ax2.bar(labels, timeout_pct, color=METRIC_COLORS["red"], alpha=0.9)
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
    ax.bar(x - width, median_vals, width=width, color=METRIC_COLORS["green"], label="Median (ms)")
    ax.bar(x, mean_vals, width=width, color=METRIC_COLORS["orange"], label="Mean (ms)")
    ax.bar(x + width, p95_vals, width=width, color=METRIC_COLORS["red"], label="P95 (ms)")
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
    bars = ax1.bar(x, timeout_rate, color=METRIC_COLORS["red"], alpha=0.9, label="Timeout Rate (%)")
    ax1.set_ylabel("Timeout Rate (%)", color=METRIC_COLORS["red"])
    ax1.tick_params(axis="y", labelcolor=METRIC_COLORS["red"])
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax1.set_title("Failure Breakdown by Library")
    ax1.grid(axis="y", alpha=0.25, linestyle="--")

    ax2 = ax1.twinx()
    ax2.plot(x, timeout_counts, color=METRIC_COLORS["orange"], marker="o", linewidth=2, label="Timeout Count")
    ax2.plot(x, timeout_tests, color=METRIC_COLORS["green"], marker="s", linewidth=2, label="Tests with Timeout")
    ax2.set_ylabel("Counts", color=METRIC_COLORS["orange"])
    ax2.tick_params(axis="y", labelcolor=METRIC_COLORS["orange"])

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

    ts_paths = expand_input_paths(args.ts, "--ts")
    ts_labels = (
        ["TypeScript"] if len(ts_paths) == 1 else [f"TypeScript ({path.stem})" for path in ts_paths]
    )

    datasets = [load_dataset(args.py, "Python")]
    datasets.extend(load_dataset(path, label) for path, label in zip(ts_paths, ts_labels))
    datasets.append(load_dataset(args.cs, "C#"))

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
