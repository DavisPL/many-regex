import re2 as pyre2  # https://pypi.org/project/pyre2/
import time
import statistics
import json

output = {}

for input_size in range(30):

    times = []

    for run in range(5):

        start = time.time()

        result = pyre2.match("^(?=(a+)+b)\\w+$", "a" * input_size)

        end = time.time()

        times.append(end - start)

        print(f"{input_size=}, {end - start}")

    average = sum(times) / len(times)

    print(f"Summary: {input_size=} {average=}")

    output[input_size] = {
        "times": times, "mean": average, "stdev": statistics.stdev(times),
    }


with open("pyre2_output.json", "w") as file:
    json.dump(output, file)
