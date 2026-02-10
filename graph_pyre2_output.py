"""Graph pyre2 scaling output from pyre2_scaling.py."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot pyre2 scaling results from pyre2_output.json."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("pyre2_output.json"),
        help="Path to pyre2 output JSON (default: pyre2_output.json).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("images/pyre2_scaling.png"),
        help="Output image path (default: images/pyre2_scaling.png).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Output image DPI (default: 200).",
    )
    return parser.parse_args()


def load_rows(path: Path) -> tuple[list[int], list[float], list[float], list[list[float]]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    rows = sorted(((int(k), v) for k, v in data.items()), key=lambda item: item[0])
    if not rows:
        raise RuntimeError(f"No data found in {path}.")

    sizes = [size for size, _ in rows]
    means = [row["mean"] for _, row in rows]
    stdevs = [row.get("stdev", 0.0) for _, row in rows]
    runs = [row["times"] for _, row in rows]
    return sizes, means, stdevs, runs


def plot(sizes: list[int], means: list[float], stdevs: list[float], out: Path, dpi: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)

    fig, ax1 = plt.subplots(figsize=(11, 6))

    lower = [max(1e-12, m - s) for m, s in zip(means, stdevs, strict=True)]
    upper = [m + s for m, s in zip(means, stdevs, strict=True)]
    ax1.plot(sizes, means, color="#1f77b4", linewidth=2, marker="o", label="Mean time")
    ax1.fill_between(sizes, lower, upper, color="#1f77b4", alpha=0.2, label="+/-1 stdev")
    ax1.set_ylabel("Seconds")
    ax1.set_title("pyre2 Scaling: mean runtime by input size")
    ax1.grid(True, which="both", alpha=0.25)
    ax1.legend(loc="upper left")
    ax1.set_xlabel('Input size (number of "a" characters)')

    fig.tight_layout()
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    sizes, means, stdevs, _runs = load_rows(args.input)
    plot(sizes, means, stdevs, args.out, args.dpi)
    print(f"Saved graph: {args.out}")


if __name__ == "__main__":
    main()
