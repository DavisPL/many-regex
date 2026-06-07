#!/usr/bin/env python3
"""Aggregate dataset-mode result JSONs from all four engine runners and
produce a summary table + matplotlib charts.

Inputs (must already exist; produced by each runner with --dataset):
  rust_redos_test_results_dataset.json
  py_redos_test_results_dataset_timeout-2.json
  ts_redos_test_results_dataset_timeout-2.json
  csharp_redos_test_results_dataset_timeout-2.json

Outputs:
  experiment-results/summary.json
  experiment-results/summary.txt
  experiment-results/median_time_by_group_size.png
  experiment-results/timeouts_by_library.png
  experiment-results/time_vs_regex_size.png
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "experiment-results"

ENGINE_FILES = {
    "Rust":       ROOT / "rust_redos_test_results_dataset.json",
    "Python":     ROOT / "py_redos_test_results_dataset_timeout-2.json",
    "TypeScript": ROOT / "ts_redos_test_results_dataset_timeout-2.json",
    "C#":         ROOT / "csharp_redos_test_results_dataset_timeout-2.json",
}

GROUPS = ["known_bad", "generated_low_complexity", "generated_high_complexity"]
SIZES = ["small", "medium", "large"]
GROUP_SIZE_ORDER = [(g, s) for g in GROUPS for s in SIZES]


def _parse_python_result(r):
    # Python runner serializes the inner dict via str(); decode it.
    res = r["result"]
    if isinstance(res, str):
        res = eval(res, {"__builtins__": {}}, {})
    return float(res["time"]), bool(res["timed_out"]), res["result"]


def load_engine(engine: str, path: Path) -> list[dict]:
    """Return a list of flattened per-(engine, library, case) result rows."""
    if not path.exists():
        print(f"  [skip] {engine}: missing {path.name}")
        return []
    with path.open() as f:
        data = json.load(f)

    rows = []
    for r in data.get("results", []):
        md = r.get("metadata") or {}
        if engine == "Python":
            t, timed_out, match = _parse_python_result(r)
        else:
            res = r["result"]
            t, timed_out, match = float(res["time"]), bool(res["timed_out"]), res["result"]

        rows.append({
            "engine":     engine,
            "library":    r["library"],
            "test_id":    r["test_id"],
            "group":      md.get("group"),
            "size":       md.get("size"),
            "regex_size": md.get("regex_size"),
            "ast_size":   md.get("ast_size"),
            "ast_depth":  md.get("ast_depth"),
            "time":       t,
            "timed_out":  timed_out,
            "match":      match,
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    """Build a nested {engine: {library: {(group,size): stats}}} summary."""
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    timeouts = defaultdict(lambda: defaultdict(int))
    for r in rows:
        key = (r["group"], r["size"])
        if r["timed_out"]:
            timeouts[r["engine"]][r["library"]] += 1
        else:
            grouped[r["engine"]][r["library"]][key].append(r["time"])

    summary = {}
    for engine, libs in grouped.items():
        summary[engine] = {}
        for lib, buckets in libs.items():
            entry = {"timeouts_total": timeouts[engine][lib], "by_group_size": {}}
            for key, times in buckets.items():
                if not times:
                    continue
                entry["by_group_size"][f"{key[0]}|{key[1]}"] = {
                    "n":      len(times),
                    "mean":   statistics.mean(times),
                    "median": statistics.median(times),
                    "min":    min(times),
                    "max":    max(times),
                }
            summary[engine][lib] = entry
    return summary


def print_text_summary(summary: dict) -> str:
    lines = []
    lines.append("Engine / library median match time (s) by group×size")
    lines.append("-" * 100)
    header = f"{'engine':<10} {'library':<15} " + " ".join(
        f"{g[:9]:>9}/{s[:3]:<3}" for g, s in GROUP_SIZE_ORDER
    ) + f" {'TO':>5}"
    lines.append(header)
    for engine, libs in summary.items():
        for lib, entry in libs.items():
            cells = []
            for gs in GROUP_SIZE_ORDER:
                key = f"{gs[0]}|{gs[1]}"
                stat = entry["by_group_size"].get(key)
                if stat is None:
                    cells.append(f"{'-':>13}")
                else:
                    med = stat["median"]
                    if med < 1e-3:
                        s = f"{med*1e6:.0f}us"
                    elif med < 1.0:
                        s = f"{med*1e3:.1f}ms"
                    else:
                        s = f"{med:.2f}s"
                    cells.append(f"{s:>13}")
            cells_s = " ".join(cells)
            to = entry["timeouts_total"]
            lines.append(f"{engine:<10} {lib:<15} {cells_s} {to:>5}")
    return "\n".join(lines)


# --------------------------- Plots ---------------------------------------- #

def plot_median_by_group_size(rows: list[dict], path: Path) -> None:
    """Grouped bar chart: x = group×size buckets, y = median time (log),
    one bar per (engine, library)."""
    fig, ax = plt.subplots(figsize=(14, 6))

    series = defaultdict(dict)  # (engine, library) -> {(group,size): median}
    for r in rows:
        if r["timed_out"]:
            continue
        series[(r["engine"], r["library"])].setdefault((r["group"], r["size"]), []).append(r["time"])

    medians = {
        k: {gs: statistics.median(vs) for gs, vs in d.items()}
        for k, d in series.items()
    }

    labels = [f"{g.replace('generated_', '')}\n{s}" for g, s in GROUP_SIZE_ORDER]
    x_base = list(range(len(GROUP_SIZE_ORDER)))
    series_keys = sorted(medians.keys())
    n_series = len(series_keys)
    width = 0.8 / max(n_series, 1)

    for i, key in enumerate(series_keys):
        vals = [medians[key].get(gs, 0) or 1e-9 for gs in GROUP_SIZE_ORDER]
        offsets = [x + (i - (n_series - 1) / 2) * width for x in x_base]
        ax.bar(offsets, vals, width=width, label=f"{key[0]}/{key[1]}")

    ax.set_yscale("log")
    ax.set_xticks(x_base)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("median match time (s, log scale)")
    ax.set_title("Median regex match time by group×size, per engine/library")
    ax.legend(fontsize=8, ncol=2, loc="upper left")
    ax.grid(axis="y", which="both", linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_timeouts(rows: list[dict], path: Path) -> None:
    """Bar chart of timeout counts per (engine, library), stacked by group."""
    counts = defaultdict(lambda: defaultdict(int))  # (engine, library) -> group -> n
    for r in rows:
        if r["timed_out"]:
            counts[(r["engine"], r["library"])][r["group"]] += 1

    if not counts:
        # Still draw an empty axis to make the absence visible.
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "no timeouts across any engine/library",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        fig.savefig(path, dpi=130)
        plt.close(fig)
        return

    keys = sorted(counts.keys())
    labels = [f"{k[0]}/{k[1]}" for k in keys]
    fig, ax = plt.subplots(figsize=(max(8, len(keys) * 1.2), 5))
    bottoms = [0] * len(keys)
    for grp in GROUPS:
        vals = [counts[k].get(grp, 0) for k in keys]
        ax.bar(labels, vals, bottom=bottoms, label=grp)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_ylabel("timeouts (count)")
    ax.set_title("Per-case timeouts by engine/library, stacked by group")
    ax.legend()
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_time_vs_regex_size(rows: list[dict], path: Path) -> None:
    """Scatter: regex_size vs match time, colored by engine. Skips timeouts."""
    fig, ax = plt.subplots(figsize=(10, 6))
    engines = sorted({r["engine"] for r in rows})
    cmap = plt.colormaps.get_cmap("tab10")
    for i, eng in enumerate(engines):
        xs, ys = [], []
        for r in rows:
            if r["engine"] != eng or r["timed_out"]:
                continue
            if r["regex_size"] is None or r["time"] <= 0:
                continue
            xs.append(r["regex_size"])
            ys.append(r["time"])
        ax.scatter(xs, ys, s=8, alpha=0.35, color=cmap(i % 10), label=eng)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("regex size (chars, log)")
    ax.set_ylabel("match time (s, log)")
    ax.set_title("Per-case match time vs regex size, by engine")
    ax.legend()
    ax.grid(which="both", linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    rows: list[dict] = []
    for engine, path in ENGINE_FILES.items():
        loaded = load_engine(engine, path)
        print(f"  {engine}: {len(loaded)} rows")
        rows.extend(loaded)

    if not rows:
        raise SystemExit("no engine results loaded; run the engine binaries first")

    summary = summarize(rows)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    text = print_text_summary(summary)
    (OUT_DIR / "summary.txt").write_text(text + "\n")
    print()
    print(text)

    plot_median_by_group_size(rows, OUT_DIR / "median_time_by_group_size.png")
    plot_timeouts(rows, OUT_DIR / "timeouts_by_library.png")
    plot_time_vs_regex_size(rows, OUT_DIR / "time_vs_regex_size.png")

    print(f"\nwrote summary.json, summary.txt, and 3 PNGs to {OUT_DIR}")


if __name__ == "__main__":
    main()
