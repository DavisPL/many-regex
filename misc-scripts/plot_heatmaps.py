#!/usr/bin/env python3
"""Per-size heatmaps: regex_size (X) vs input_size (Y), color = median time.

One row of subplots: small | medium | large. Each cell shows the median match
time (across all engines and libraries) for cases whose regex_size falls in
that X bin and whose input_size matches that Y row. Cells with no cases are
blank.

Outputs:
  experiment-results/heatmap_time_regex_x_input_<small|medium|large>.png
  experiment-results/heatmap_time_regex_x_input_combined.png
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LogNorm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "experiment-results"
OUT_DIR.mkdir(exist_ok=True)

ENGINE_FILES = {
    "Rust":       ROOT / "rust_redos_test_results_dataset.json",
    "Python":     ROOT / "py_redos_test_results_dataset_timeout-2.json",
    "TypeScript": ROOT / "ts_redos_test_results_dataset_timeout-2.json",
    "C#":         ROOT / "csharp_redos_test_results_dataset_timeout-2.json",
}

SIZES = ["small", "medium", "large"]

# Fine-grained regex-size binning: one column per integer width up to the
# largest case in the dataset (~330 chars). Bins are computed once per call
# from the actual data so empty columns are still drawn on a uniform grid.
# ~10× the granularity of the original 10-bin version: aim for ~100 columns
# at the dataset's largest regex_size (~330 chars), so width = 3.
REGEX_BIN_WIDTH = 3
REGEX_BIN_MAX = 330


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
            if md.get("size") not in SIZES:
                continue
            t, timed_out = _parse_time(engine, r)
            if timed_out:
                continue
            rs = md.get("regex_size")
            isz = md.get("input_size")
            if rs is None or isz is None:
                continue
            rows.append({
                "engine":     engine,
                "library":    r["library"],
                "size":       md["size"],
                "regex_size": int(rs),
                "input_size": int(isz),
                "time":       t,
            })
            n += 1
        print(f"  {engine}: {n} rows kept (non-timeout, with metadata)")
    return rows


def regex_bin_index(rs: int) -> int:
    return min(rs // REGEX_BIN_WIDTH, REGEX_BIN_MAX // REGEX_BIN_WIDTH - 1)


def regex_bin_label(i: int) -> str:
    lo = i * REGEX_BIN_WIDTH
    hi = lo + REGEX_BIN_WIDTH - 1
    return f"{lo}-{hi}"


def build_grid(rows: list[dict], size: str):
    """Return (matrix, input_sizes, regex_bin_labels).

    Trims trailing all-NaN columns so each subplot only shows the populated
    x-range for that size group. The y-axis is limited to the discrete
    input_size values that actually appear in the dataset (6 values).
    """
    subset = [r for r in rows if r["size"] == size]
    if not subset:
        return None, [], []

    input_sizes = sorted({r["input_size"] for r in subset})
    n_rs_bins_full = REGEX_BIN_MAX // REGEX_BIN_WIDTH
    n_inp = len(input_sizes)

    buckets: dict[tuple[int, int], list[float]] = defaultdict(list)
    for r in subset:
        x = regex_bin_index(r["regex_size"])
        y = input_sizes.index(r["input_size"])
        buckets[(y, x)].append(r["time"])

    mat = np.full((n_inp, n_rs_bins_full), np.nan, dtype=float)
    for (y, x), ts in buckets.items():
        mat[y, x] = statistics.median(ts)

    # Trim trailing empty columns so the subplot tightens to actual data.
    populated_cols = ~np.all(np.isnan(mat), axis=0)
    if populated_cols.any():
        last = int(np.where(populated_cols)[0].max()) + 1
        mat = mat[:, :last]
    rs_labels = [regex_bin_label(i) for i in range(mat.shape[1])]
    return mat, input_sizes, rs_labels


def _vmin_vmax(matrices) -> tuple[float, float]:
    """Shared color scale across the three subplots so colors compare."""
    all_vals = []
    for m in matrices:
        if m is not None:
            all_vals.extend(v for v in m.flatten() if not np.isnan(v) and v > 0)
    if not all_vals:
        return 1e-6, 1.0
    return max(min(all_vals), 1e-6), max(all_vals)


def _draw(ax, mat, input_sizes, rs_labels, title, vmin, vmax):
    if mat is None or mat.size == 0:
        ax.text(0.5, 0.5, "no data", ha="center", va="center",
                transform=ax.transAxes)
        ax.set_axis_off()
        return None
    im = ax.imshow(
        mat,
        aspect="auto",
        origin="lower",
        cmap="viridis",
        norm=LogNorm(vmin=vmin, vmax=vmax),
        interpolation="nearest",
    )
    # Sparse x ticks every ~10% of the populated range.
    n_cols = len(rs_labels)
    tick_step = max(1, n_cols // 12)
    xticks = list(range(0, n_cols, tick_step))
    ax.set_xticks(xticks)
    ax.set_xticklabels([rs_labels[i] for i in xticks], rotation=0, fontsize=8)
    ax.set_yticks(range(len(input_sizes)))
    ax.set_yticklabels([f"{v:,}" for v in input_sizes], fontsize=8)
    ax.set_xlabel(f"regex size (chars, {REGEX_BIN_WIDTH}-wide bins)")
    ax.set_ylabel("input size (chars)")
    ax.set_title(title)
    return im


def main() -> None:
    rows = load_rows()
    if not rows:
        raise SystemExit("no rows loaded — run the engine binaries first")

    grids = {sz: build_grid(rows, sz) for sz in SIZES}
    matrices = [g[0] for g in grids.values()]
    vmin, vmax = _vmin_vmax(matrices)

    # Individual per-size plots
    for sz in SIZES:
        mat, input_sizes, rs_labels = grids[sz]
        fig, ax = plt.subplots(figsize=(10, max(3, 0.6 * len(input_sizes) + 2)))
        im = _draw(ax, mat, input_sizes, rs_labels,
                   f"Median match time — size = {sz}", vmin, vmax)
        if im is not None:
            cbar = fig.colorbar(im, ax=ax)
            cbar.set_label("median time (s, log)")
        fig.tight_layout()
        out = OUT_DIR / f"heatmap_time_regex_x_input_{sz}.png"
        fig.savefig(out, dpi=140)
        plt.close(fig)
        print(f"wrote {out}")

    # Combined 1×3 figure for side-by-side comparison
    fig, axes = plt.subplots(1, 3, figsize=(20, 5), sharey=False)
    last_im = None
    for ax, sz in zip(axes, SIZES):
        mat, input_sizes, rs_labels = grids[sz]
        im = _draw(ax, mat, input_sizes, rs_labels,
                   f"size = {sz}", vmin, vmax)
        if im is not None:
            last_im = im
    if last_im is not None:
        cbar = fig.colorbar(last_im, ax=axes.ravel().tolist(),
                            fraction=0.025, pad=0.02)
        cbar.set_label("median time (s, log)")
    fig.suptitle("Median match time vs regex × input size, per size group "
                 "(all engines & libraries)", y=1.02)
    out = OUT_DIR / "heatmap_time_regex_x_input_combined.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
