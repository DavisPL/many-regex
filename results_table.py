#!/usr/bin/env python3
"""Generate concise comparison tables from regex benchmark JSON outputs."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from statistics import mean, median

import matplotlib.pyplot as plt


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


if __name__ == "__main__":
    main()
