#!/usr/bin/env python3
"""Plots explaining regex size vs execution time.

Three views:
  1. faceted scatter (one panel per engine, all libraries overlaid,
     log-log axes, points colored by group). Shows the per-case cloud
     and where ReDoS spikes break above the trend.
  2. median trend lines per (engine, library), log-log. Bins regex_size
     geometrically and plots the median time per bin so trends are clean.
  3. Rust-only deep dive — same scatter but only Rust, larger, so the
     actual algorithmic scaling is visible without process-spawn noise.

Outputs:
  experiment-results/size_vs_time_scatter_by_engine.png
  experiment-results/size_vs_time_medians.png
  experiment-results/size_vs_time_rust_only.png
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
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "experiment-results"
OUT_DIR.mkdir(exist_ok=True)

# Prefer in-process result files when present (they measure actual match
# time rather than per-case process/worker spawn overhead). Fall back to
# the subprocess file if no in-process run was completed for that engine.
def _pick(*candidates: str) -> Path:
    for name in candidates:
        p = ROOT / name
        if p.exists():
            return p
    return ROOT / candidates[-1]  # nonexistent; loader will skip


ENGINE_FILES = {
    "Rust":       _pick("rust_redos_test_results_dataset.json"),
    "Python":     _pick("py_redos_test_results_dataset_inproc_timeout-2.json",
                        "py_redos_test_results_dataset_timeout-2.json"),
    "TypeScript": _pick("ts_redos_test_results_dataset_inproc_timeout-2.json",
                        "ts_redos_test_results_dataset_timeout-2.json"),
    "C#":         _pick("csharp_redos_test_results_dataset_inproc_timeout-2.json",
                        "csharp_redos_test_results_dataset_timeout-2.json"),
}

# Track which engines are using in-process timing. Rust is always in-process
# (the runner has no subprocess layer); the others are flagged by filename.
INPROC_ENGINES = {
    e: (e == "Rust") or ("inproc" in p.name)
    for e, p in ENGINE_FILES.items()
}

GROUP_COLORS = {
    "known_bad":                 "#d62728",
    "generated_low_complexity":  "#1f77b4",
    "generated_high_complexity": "#2ca02c",
}
GROUP_LABEL = {
    "known_bad":                 "known bad",
    "generated_low_complexity":  "low complexity",
    "generated_high_complexity": "high complexity",
}


def _parse_time(engine: str, r: dict) -> tuple[float, bool]:
    res = r["result"]
    if engine == "Python" and isinstance(res, str):
        res = eval(res, {"__builtins__": {}}, {})
    return float(res["time"]), bool(res["timed_out"])


def load_rows() -> list[dict]:
    rows: list[dict] = []
    for engine, path in ENGINE_FILES.items():
        if not path.exists():
            print(f"  [skip] {engine}: missing {path.name}")
            continue
        with path.open() as f:
            data = json.load(f)
        n = 0
        for r in data.get("results", []):
            md = r.get("metadata") or {}
            t, timed_out = _parse_time(engine, r)
            if timed_out:
                continue
            rs = md.get("regex_size")
            if rs is None or rs <= 0 or t <= 0:
                continue
            rows.append({
                "engine":     engine,
                "library":    r["library"],
                "group":      md.get("group"),
                "regex_size": int(rs),
                "time":       t,
            })
            n += 1
        print(f"  {engine}: {n} usable rows")
    return rows


# ---------------------------------------------------------------- plot 1 -- #

def plot_scatter_by_engine(rows: list[dict], path: Path) -> None:
    engines = sorted({r["engine"] for r in rows})
    n = len(engines)
    cols = 2 if n > 1 else 1
    rows_n = math.ceil(n / cols)
    fig, axes = plt.subplots(rows_n, cols, figsize=(13, 4.2 * rows_n),
                             sharex=True, sharey=True, squeeze=False)
    flat_axes = [ax for row in axes for ax in row]

    for ax, engine in zip(flat_axes, engines):
        for group, color in GROUP_COLORS.items():
            xs = [r["regex_size"] for r in rows
                  if r["engine"] == engine and r["group"] == group]
            ys = [r["time"] for r in rows
                  if r["engine"] == engine and r["group"] == group]
            ax.scatter(xs, ys, s=10, alpha=0.35, color=color,
                       label=GROUP_LABEL[group], edgecolor="none")
        ax.set_xscale("log")
        ax.set_yscale("log")
        mode = "in-process" if INPROC_ENGINES.get(engine) else "subprocess"
        ax.set_title(f"{engine}  ({mode})")
        ax.grid(which="both", linestyle=":", alpha=0.3)

    # Common axis labels & legend
    for ax in flat_axes[-cols:]:
        ax.set_xlabel("regex size (chars, log)")
    for ax in axes[:, 0]:
        ax.set_ylabel("match time (s, log)")
    handles, labels = flat_axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3,
               bbox_to_anchor=(0.5, 1.02), frameon=False)
    fig.suptitle(
        "Per-case match time vs regex size, faceted by engine\n"
        "(panel mode noted; in-process times the match call directly, "
        "subprocess includes spawn overhead)",
        y=1.08, fontsize=11,
    )

    # Hide any unused subplots.
    for ax in flat_axes[len(engines):]:
        ax.set_visible(False)

    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path}")


# ---------------------------------------------------------------- plot 2 -- #

def plot_median_trend(rows: list[dict], path: Path) -> None:
    """One line per (engine, library): regex_size (log bins) → median time."""
    # Geometric bin edges across the full regex_size range.
    sizes = [r["regex_size"] for r in rows]
    lo, hi = max(1, min(sizes)), max(sizes)
    edges = np.geomspace(lo, hi + 1, 14)

    # Bucket by (engine, library) → bin_idx → [times]
    buckets: dict[tuple[str, str], dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list))
    for r in rows:
        b = int(np.searchsorted(edges, r["regex_size"], side="right") - 1)
        b = max(0, min(b, len(edges) - 2))
        buckets[(r["engine"], r["library"])][b].append(r["time"])

    fig, ax = plt.subplots(figsize=(11, 6.5))
    centers = np.sqrt(edges[:-1] * edges[1:])  # geometric midpoint

    # Distinct colors per engine; line styles per library within engine.
    engine_colors = {
        "Rust":       "#d62728",
        "Python":     "#1f77b4",
        "TypeScript": "#9467bd",
        "C#":         "#ff7f0e",
    }
    library_styles = ["-", "--", "-.", ":"]
    seen_per_engine: dict[str, int] = defaultdict(int)

    for (engine, library), per_bin in sorted(buckets.items()):
        idx = seen_per_engine[engine]
        seen_per_engine[engine] += 1
        style = library_styles[idx % len(library_styles)]
        xs, ys = [], []
        for b in sorted(per_bin):
            if not per_bin[b]:
                continue
            xs.append(centers[b])
            ys.append(statistics.median(per_bin[b]))
        ax.plot(xs, ys,
                color=engine_colors.get(engine, "#444"),
                linestyle=style,
                marker="o", markersize=3.5,
                label=f"{engine} / {library}")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("regex size (chars, log)")
    ax.set_ylabel("median match time (s, log)")
    ax.set_title("Median match time vs regex size, per engine and library")
    ax.grid(which="both", linestyle=":", alpha=0.35)
    ax.legend(fontsize=8, ncol=2, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"wrote {path}")


# ---------------------------------------------------------------- plot 3 -- #

def plot_rust_only(rows: list[dict], path: Path) -> None:
    rust = [r for r in rows if r["engine"] == "Rust"]
    fig, ax = plt.subplots(figsize=(11, 6.5))

    for group, color in GROUP_COLORS.items():
        xs = [r["regex_size"] for r in rust if r["group"] == group]
        ys = [r["time"] for r in rust if r["group"] == group]
        ax.scatter(xs, ys, s=18, alpha=0.55, color=color,
                   label=GROUP_LABEL[group], edgecolor="none")

    # Highlight the slowest 8 points with their regex_size value.
    rust_sorted = sorted(rust, key=lambda r: r["time"], reverse=True)[:8]
    for r in rust_sorted:
        ax.annotate(f"  {r['regex_size']}c",
                    (r["regex_size"], r["time"]),
                    fontsize=7, color="#444")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("regex size (chars, log)")
    ax.set_ylabel("match time (s, log)")
    ax.set_title("Rust regex crate — per-case match time vs regex size\n"
                 "(in-process timing — no subprocess overhead)")
    ax.grid(which="both", linestyle=":", alpha=0.35)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"wrote {path}")


def main() -> None:
    rows = load_rows()
    if not rows:
        raise SystemExit("no rows loaded")

    plot_scatter_by_engine(rows, OUT_DIR / "size_vs_time_scatter_by_engine.png")
    plot_median_trend(rows, OUT_DIR / "size_vs_time_medians.png")
    plot_rust_only(rows, OUT_DIR / "size_vs_time_rust_only.png")


if __name__ == "__main__":
    main()
