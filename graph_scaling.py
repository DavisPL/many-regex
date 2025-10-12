import json
import matplotlib.pyplot as plt
from collections import defaultdict

# Load the JSON data
with open("./scaling_test.json", "r") as f:
    data = json.load(f)

# Organize data by test_id
tests = defaultdict(lambda: defaultdict(lambda: {"sizes": [], "times": []}))

for entry in data:
    test_id = entry["test_id"]
    size = entry["size"]

    for result in entry["result"]:
        library = result["library"]
        time = result["result"]["time"]

        tests[test_id][library]["sizes"].append(size)
        tests[test_id][library]["times"].append(time)

# Get pattern info for titles
pattern_info = {}
for entry in data:
    test_id = entry["test_id"]
    if test_id not in pattern_info and entry["result"]:
        pattern_info[test_id] = entry["result"][0]["pattern"]

# Create a graph for each test_id
for test_id in sorted(tests.keys()):
    plt.figure(figsize=(12, 7))

    # Plot each library
    for library in sorted(tests[test_id].keys()):
        sizes = tests[test_id][library]["sizes"]
        times = tests[test_id][library]["times"]
        plt.plot(sizes, times, marker="o", label=library, linewidth=2)

    plt.xlabel('Input Size (number of "a" characters)', fontsize=12)
    plt.ylabel("Time (seconds, log scale)", fontsize=12)
    plt.yscale("log")

    pattern = pattern_info.get(test_id, "Unknown")
    plt.title(
        f'Test {test_id}: Pattern "{pattern}"\nExecution Time vs Input Size',
        fontsize=14,
        fontweight="bold",
    )

    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3, which="both")
    plt.tight_layout()

    # Save the figure
    filename = f"test_{test_id}_performance.png"
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    print(f"Saved: {filename}")

    plt.close()

print(f"\nGenerated {len(tests)} graphs successfully!")
