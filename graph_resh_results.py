import re
from collections import defaultdict

import matplotlib.pyplot as plt


RESULTS_PATH = "resh_test/results.txt"
OUTPUT_PATH = "images/resh_results.png"


def parse_results(path):
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("Test "):
                continue

            test_match = re.match(r"^Test (\d+) \(([^)]+)\):", line)
            if not test_match:
                continue

            test_id = int(test_match.group(1))
            engine = test_match.group(2)

            pattern_match = re.search(r"pattern=(.*?), input_length=", line)
            input_match = re.search(r"input_length=(\d+)", line)
            match_match = re.search(r"match=([^,]+)", line)
            time_match = re.search(r"time_ms=([0-9.]+)", line)
            error_match = re.search(r"error=([^,]+)", line)
            message_match = re.search(r"message=(.*)$", line)

            records.append(
                {
                    "test_id": test_id,
                    "engine": engine,
                    "pattern": pattern_match.group(1) if pattern_match else None,
                    "input_length": int(input_match.group(1)) if input_match else None,
                    "match": match_match.group(1) if match_match else None,
                    "time_ms": float(time_match.group(1)) if time_match else None,
                    "error": error_match.group(1) if error_match else None,
                    "message": message_match.group(1) if message_match else None,
                }
            )
    return records


def plot_results(records, output_path):
    by_engine = defaultdict(list)
    for rec in records:
        by_engine[rec["engine"]].append(rec)

    engines = sorted(by_engine.keys())
    colors = {"RE#": "#1f77b4", "dotnet": "#ff7f0e"}

    max_time = max(
        rec["time_ms"] for rec in records if rec["time_ms"] is not None
    )
    error_y = max_time * 1.5

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [3, 1]})
    fig.suptitle("RESH Results: Execution Time and Outcomes", fontsize=14, fontweight="bold")

    for engine in engines:
        engine_records = by_engine[engine]
        success = [r for r in engine_records if r["time_ms"] is not None]
        errors = [r for r in engine_records if r["time_ms"] is None]

        ax1.scatter(
            [r["test_id"] for r in success],
            [r["time_ms"] for r in success],
            label=f"{engine} (time)",
            s=40,
            color=colors.get(engine, "#333333"),
            alpha=0.8,
        )
        if errors:
            ax1.scatter(
                [r["test_id"] for r in errors],
                [error_y for _ in errors],
                label=f"{engine} (error/timeout)",
                marker="x",
                s=60,
                color=colors.get(engine, "#333333"),
            )

    ax1.set_ylabel("Time (ms, log scale)")
    ax1.set_xlabel("Test ID")
    ax1.set_yscale("log")
    ax1.grid(True, which="both", alpha=0.3)
    ax1.legend(fontsize=9, ncol=2)
    ax1.text(
        0.01,
        0.95,
        "Errors/timeouts plotted at top",
        transform=ax1.transAxes,
        fontsize=9,
        va="top",
    )

    outcome_counts = []
    for engine in engines:
        counts = {"success": 0, "timeout": 0, "error": 0}
        for rec in by_engine[engine]:
            if rec["time_ms"] is not None:
                counts["success"] += 1
            elif rec["error"] == "TimeoutException":
                counts["timeout"] += 1
            else:
                counts["error"] += 1
        outcome_counts.append(counts)

    x_pos = range(len(engines))
    success_vals = [c["success"] for c in outcome_counts]
    timeout_vals = [c["timeout"] for c in outcome_counts]
    error_vals = [c["error"] for c in outcome_counts]

    ax2.bar(x_pos, success_vals, label="Success", color="#2ca02c")
    ax2.bar(x_pos, timeout_vals, bottom=success_vals, label="Timeout", color="#d62728")
    ax2.bar(
        x_pos,
        error_vals,
        bottom=[s + t for s, t in zip(success_vals, timeout_vals)],
        label="Other Error",
        color="#9467bd",
    )

    ax2.set_xticks(list(x_pos))
    ax2.set_xticklabels(engines)
    ax2.set_ylabel("Count")
    ax2.set_title("Outcome Counts by Engine", fontsize=11)
    ax2.legend(fontsize=9, ncol=3)
    ax2.grid(axis="y", alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(output_path, dpi=200)
    print(f"Saved {output_path}")


def main():
    records = parse_results(RESULTS_PATH)
    if not records:
        raise SystemExit(f"No results parsed from {RESULTS_PATH}")
    plot_results(records, OUTPUT_PATH)


if __name__ == "__main__":
    main()
