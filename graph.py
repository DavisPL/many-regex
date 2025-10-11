import json
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

# Load the JSON data
with open("./redos_test_results.json", "r") as f:
    data = json.load(f)

# Extract summary statistics
summary = data["summary_stats"]
libraries = data["metadata"]["libraries"]

# Process results by test_id
test_results = defaultdict(lambda: defaultdict(list))
for result in data["results"]:
    lib = result["library"]
    test_id = result["test_id"]
    result_data = eval(result["result"])
    test_results[test_id][lib].append(result_data["time"] * 1000)  # Convert to ms

# Calculate averages per test
test_averages = {}
test_patterns = {}
for result in data["results"]:
    test_id = result["test_id"]
    if test_id not in test_patterns:
        test_patterns[test_id] = {
            "pattern": result["pattern"],
            "input": result["input"],
        }

for test_id in test_results:
    test_averages[test_id] = {}
    for lib in libraries:
        if lib in test_results[test_id]:
            test_averages[test_id][lib] = np.mean(test_results[test_id][lib])
        else:
            test_averages[test_id][lib] = 0

# Color scheme for libraries
colors = {"Rure": "#3498db", "Re": "#e74c3c", "Regex": "#2ecc71", "Pyre2": "#f39c12"}

###############################################################################
# FIGURE 1: Original Overview Charts
###############################################################################
fig1 = plt.figure(figsize=(16, 10))
gs1 = fig1.add_gridspec(2, 2, height_ratios=[1, 1], hspace=0.3)

fig1.suptitle(
    "Regex Library Performance Benchmark Comparison", fontsize=16, fontweight="bold"
)

# 1. Mean Execution Time Comparison
ax1 = fig1.add_subplot(gs1[0, 0])
mean_times = [summary[lib]["mean_time"] * 1000 for lib in libraries]  # Convert to ms
bars1 = ax1.bar(
    libraries,
    mean_times,
    color=[colors[lib] for lib in libraries],
    alpha=0.7,
    edgecolor="black",
)
ax1.set_ylabel("Mean Time (ms)", fontweight="bold")
ax1.set_title("Mean Execution Time by Library", fontweight="bold")
ax1.grid(axis="y", alpha=0.3, linestyle="--")

# Add value labels on bars
for bar, val in zip(bars1, mean_times):
    height = bar.get_height()
    ax1.text(
        bar.get_x() + bar.get_width() / 2.0,
        height,
        f"{val:.2f}",
        ha="center",
        va="bottom",
        fontsize=9,
    )

# 2. Success Rate and Timeouts
ax2 = fig1.add_subplot(gs1[0, 1])
success_rates = [
    summary[lib]["successful_count"] / summary[lib]["total_count"] * 100
    for lib in libraries
]
timeout_counts = [summary[lib]["timeout_count"] for lib in libraries]

x_pos = np.arange(len(libraries))
bars2 = ax2.bar(
    x_pos,
    success_rates,
    color=[colors[lib] for lib in libraries],
    alpha=0.7,
    edgecolor="black",
    label="Success Rate",
)
ax2.set_ylabel("Success Rate (%)", fontweight="bold")
ax2.set_title("Success Rate and Timeout Count", fontweight="bold")
ax2.set_xticks(x_pos)
ax2.set_xticklabels(libraries)
ax2.set_ylim([0, 105])
ax2.grid(axis="y", alpha=0.3, linestyle="--")

# Add timeout counts as text
for i, (lib, timeout) in enumerate(zip(libraries, timeout_counts)):
    ax2.text(
        i,
        success_rates[i] + 2,
        f"{success_rates[i]:.0f}%\n({timeout} timeouts)",
        ha="center",
        va="bottom",
        fontsize=9,
        fontweight="bold" if timeout > 0 else "normal",
        color="red" if timeout > 0 else "black",
    )

# 3. Min/Max Range Comparison
ax4 = fig1.add_subplot(gs1[1, 0])
for i, lib in enumerate(libraries):
    min_time = summary[lib]["min_time"] * 1000
    max_time = summary[lib]["max_time"] * 1000
    median_time = summary[lib]["median_time"] * 1000

    # Plot range as a line
    ax4.plot([i, i], [min_time, max_time], color=colors[lib], linewidth=8, alpha=0.3)
    # Plot median as a point
    ax4.scatter(
        i,
        median_time,
        color=colors[lib],
        s=100,
        zorder=5,
        edgecolor="black",
        linewidth=2,
    )
    # Plot min/max as markers
    ax4.scatter(
        i, min_time, color=colors[lib], marker="_", s=200, linewidth=3, zorder=4
    )
    ax4.scatter(
        i, max_time, color=colors[lib], marker="_", s=200, linewidth=3, zorder=4
    )

ax4.set_xticks(range(len(libraries)))
ax4.set_xticklabels(libraries)
ax4.set_ylabel("Execution Time (ms)", fontweight="bold")
ax4.set_title("Execution Time Range (Min/Median/Max)", fontweight="bold")
ax4.set_yscale("log")
ax4.grid(True, alpha=0.3, linestyle="--")
ax4.legend(["Range", "Median"], loc="upper left")

# 4. Performance Summary Table
ax5 = fig1.add_subplot(gs1[1, 1])
ax5.axis("off")

# Create table data
table_data = []
headers = ["Library", "Mean (ms)", "Median (ms)", "Success", "Timeouts"]

for lib in libraries:
    row = [
        lib,
        f"{summary[lib]['mean_time'] * 1000:.2f}",
        f"{summary[lib]['median_time'] * 1000:.2f}",
        f"{summary[lib]['successful_count']}/{summary[lib]['total_count']}",
        f"{summary[lib]['timeout_count']}",
    ]
    table_data.append(row)

table = ax5.table(
    cellText=table_data,
    colLabels=headers,
    cellLoc="center",
    loc="center",
    bbox=[0, 0.2, 1, 0.7],
)
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 2)

# Color code the library names
for i, lib in enumerate(libraries):
    table[(i + 1, 0)].set_facecolor(colors[lib])
    table[(i + 1, 0)].set_alpha(0.3)

# Style header
for i in range(len(headers)):
    table[(0, i)].set_facecolor("#34495e")
    table[(0, i)].set_text_props(weight="bold", color="white")

# Highlight timeout cells
for i, lib in enumerate(libraries):
    if summary[lib]["timeout_count"] > 0:
        table[(i + 1, 4)].set_facecolor("#ffcccb")

ax5.set_title("Performance Summary", fontweight="bold", pad=20)

# Add summary text
summary_text = f"Total Tests: {data['metadata']['total_tests']} | Total Runs: {data['metadata']['total_runs']} | Total Executions: 720"
fig1.text(0.5, 0.02, summary_text, ha="center", fontsize=10, style="italic")

plt.savefig("regex_benchmark_comparison.png", dpi=300, bbox_inches="tight")
print("Graph 1 saved as 'regex_benchmark_comparison.png'")

###############################################################################
# FIGURE 2: Line Chart Performance by Test
###############################################################################
fig2, ax = plt.subplots(figsize=(16, 10))

test_ids = sorted(test_averages.keys())
x = np.arange(len(test_ids))

# Plot lines for each library
for lib in libraries:
    times = [test_averages[test_id].get(lib, 0) for test_id in test_ids]
    ax.plot(
        x,
        times,
        marker="o",
        linewidth=2.5,
        markersize=8,
        label=lib,
        color=colors[lib],
        alpha=0.8,
    )

ax.set_ylabel("Average Time (ms)", fontweight="bold", fontsize=12)
ax.set_xlabel("Test Pattern", fontweight="bold", fontsize=12)
ax.set_title(
    "Regex Library Performance Across Test Patterns (Line Chart)",
    fontweight="bold",
    fontsize=14,
    pad=15,
)
ax.set_xticks(x)

# Create detailed labels
labels = []
for test_id in test_ids:
    pattern = test_patterns[test_id]["pattern"]
    input_str = test_patterns[test_id]["input"]
    # Truncate to 5 characters
    if len(pattern) > 5:
        pattern = pattern[:5] + "..."
    if len(input_str) > 5:
        input_str = input_str[:5] + "..."
    labels.append(f"T{test_id}\n{pattern}\n{input_str}")

ax.set_xticklabels(labels, fontsize=8, rotation=90, ha="center")
ax.legend(loc="upper left", fontsize=11, framealpha=0.9)
ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.7)
ax.set_yscale("log")

# Add a note about log scale
fig2.text(
    0.99,
    0.01,
    "Note: Y-axis uses logarithmic scale",
    ha="right",
    fontsize=9,
    style="italic",
    color="gray",
)

plt.tight_layout()
plt.savefig("regex_benchmark_line_chart.png", dpi=300, bbox_inches="tight")
print("Graph 2 saved as 'regex_benchmark_line_chart.png'")

plt.show()
