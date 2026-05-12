#!/usr/bin/env python3
"""Plot a simple ReDoS library comparison chart and table."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

LANGUAGE_COLORS = {
    "Python": "#1f77b4",  # blue
    "C#": "#9467bd",  # purple
    "TypeScript": "#f2c200",  # yellow
}

LIBRARY_DISPLAY_NAMES = {
    "NativeRegExp": "RegExp",
    "dotnet": "Regex",
}


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Graph library max time, successful runs, and timeouts from JSON result files."
    )
    parser.add_argument(
        "--py", type=Path, default=Path("py_redos_test_results_timeout-10.json")
    )
    parser.add_argument(
        "--ts", type=Path, default=Path("ts_redos_test_results_timeout-10.json")
    )
    parser.add_argument(
        "--cs", type=Path, default=Path("csharp_redos_test_results_timeout-10.json")
    )
    parser.add_argument("--out", type=Path, default=Path("images/simply_10_graph.png"))
    parser.add_argument("--dpi", type=int, default=220)
    return parser.parse_args()


def parse_result_blob(raw_result: object) -> dict:
    if isinstance(raw_result, dict):
        return raw_result
    if isinstance(raw_result, str):
        return ast.literal_eval(raw_result)
    raise TypeError(f"Unsupported result payload type: {type(raw_result)}")


def load_rows(path: Path, language: str) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary_stats"]
    rows = []

    for library, stats in summary.items():
        timeout_count = int(stats.get("timeout_count", 0))
        total_count = int(stats.get("total_count", 0))
        successful_count = stats.get("successful_count")

        if successful_count is None:
            successful_count = total_count - timeout_count

        rows.append(
            {
                "language": language,
                "library": library,
                "max_ms": float(stats.get("max_time", 0.0)) * 1000.0,
                "success_runs": int(successful_count),
                "timeouts": timeout_count,
            }
        )

    # Fallback if summary is incomplete.
    if not rows:
        per_lib: dict[str, dict[str, int | float]] = {}
        for item in data.get("results", []):
            lib = item["library"]
            parsed = parse_result_blob(item["result"])
            if lib not in per_lib:
                per_lib[lib] = {"max_ms": 0.0, "success_runs": 0, "timeouts": 0}
            elapsed_ms = float(parsed.get("time", 0.0)) * 1000.0
            per_lib[lib]["max_ms"] = max(float(per_lib[lib]["max_ms"]), elapsed_ms)
            if parsed.get("timed_out"):
                per_lib[lib]["timeouts"] = int(per_lib[lib]["timeouts"]) + 1
            else:
                per_lib[lib]["success_runs"] = int(per_lib[lib]["success_runs"]) + 1

        rows = [
            {
                "language": language,
                "library": lib,
                "max_ms": float(stats["max_ms"]),
                "success_runs": int(stats["success_runs"]),
                "timeouts": int(stats["timeouts"]),
            }
            for lib, stats in per_lib.items()
        ]

    return rows


def build_plot(rows: list[dict], out_path: Path, dpi: int) -> None:
    rows = sorted(rows, key=lambda r: r["max_ms"], reverse=True)

    fig, ax_table = plt.subplots(figsize=(7.6, 6.8), facecolor="#f7f8fb")
    ax_table.axis("off")
    ax_table.set_title("Regex Library ReDoS Summary", fontsize=15, weight="bold", pad=14)
    fig.text(
        0.5,
        0.965,
        "Note: results use ~100-character test input with a 10-second timeout.",
        ha="center",
        va="top",
        fontsize=9,
        color="#444444",
    )

    col_labels = ["Library", "Max ms", "Success", "Timeouts"]
    table_rows = [
        [
            LIBRARY_DISPLAY_NAMES.get(r["library"], r["library"]),
            f"{r['max_ms']:,.2f}",
            f"{r['success_runs']:,}",
            f"{r['timeouts']:,}",
        ]
        for r in rows
    ]

    table = ax_table.table(
        cellText=table_rows,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
        colLoc="center",
        colWidths=[0.23, 0.243, 0.2367, 0.2016],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.4)
    table.scale(1, 1.42)

    for i in range(len(col_labels)):
        header = table[0, i]
        header.set_facecolor("#263238")
        header.set_text_props(color="white", weight="bold")

    for row_idx, row in enumerate(rows, start=1):
        lang_color = LANGUAGE_COLORS[row["language"]]
        library_bg = blend_with_white(lang_color, 0.22)

        for col_idx in range(len(col_labels)):
            cell = table[row_idx, col_idx]
            cell.set_edgecolor("#d0d3da")
            cell.set_linewidth(0.6)
            cell.set_facecolor("#ffffff" if row_idx % 2 else "#f4f6fb")

        first_col = table[row_idx, 0]
        first_col.set_facecolor(library_bg)
        first_col.set_text_props(color="#000000", weight="bold")

        timeout_cell = table[row_idx, 3]
        if row["timeouts"] > 0:
            timeout_cell.set_facecolor("#ffd9d9")
            timeout_cell.set_text_props(color="#b00020", weight="bold")
        else:
            timeout_cell.set_text_props(color="#222222")

    legend_handles = [
        Patch(facecolor=blend_with_white(color, 0.22), edgecolor="#d0d3da", label=lang)
        for lang, color in LANGUAGE_COLORS.items()
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=9.6,
        bbox_to_anchor=(0.5, 0.03),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", pad_inches=0.15)


def main() -> None:
    args = parse_args()

    rows = []
    rows.extend(load_rows(args.py, "Python"))
    rows.extend(load_rows(args.ts, "TypeScript"))
    rows.extend(load_rows(args.cs, "C#"))

    if not rows:
        raise RuntimeError("No rows found to plot.")

    build_plot(rows, args.out, args.dpi)
    print(f"Saved graph to {args.out}")


if __name__ == "__main__":
    main()
