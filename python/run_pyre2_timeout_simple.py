import re2 as pyre2  # https://pypi.org/project/pyre2/
import time


print("Running Regex: ^(?=(a+)+b)\\w+$")

for input_size in range(100):

    start = time.time()
    result = pyre2.match("^(?=(a+)+b)\\w+$", "a" * input_size)

    end = time.time()

    seconds = round(end - start, 4)
    print(f"{result=}, {seconds=}")
