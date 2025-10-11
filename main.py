from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor, TimeoutError
import time
import json
from datetime import datetime

import re  # default python
import rure  # https://pypi.org/project/rure/
import regex  # https://pypi.org/project/regex/
import re2 as pyre2  # https://pypi.org/project/pyre2/
import hyperscan  # https://pypi.org/project/hyperscan/


class RegexLibrary(ABC):
    TIMEOUT_SECONDS = 2

    @abstractmethod
    def setup_test(self, pattern: str, input: str):
        pass

    def test(self, pattern: str, input: str):
        start_time = time.perf_counter()

        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.setup_test, pattern, input)
            try:
                result = future.result(timeout=self.TIMEOUT_SECONDS)
                duration = time.perf_counter() - start_time
                return {
                    "library": self.__class__.__name__,
                    "result": result,
                    "time": duration,
                    "timed_out": False,
                }
            except TimeoutError:
                # Force kill the process by canceling and shutting down
                future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                duration = time.perf_counter() - start_time
                return {
                    "library": self.__class__.__name__,
                    "result": None,
                    "time": duration,
                    "timed_out": True,
                }


class Rure(RegexLibrary):
    def setup_test(self, pattern: str, input: str):
        match = rure.match(pattern, input)
        # Convert to picklable format
        return bool(match) if match is not None else None


class Re(RegexLibrary):
    def setup_test(self, pattern: str, input: str):
        match = re.match(pattern, input)
        # Convert to picklable format
        return match is not None


class Regex(RegexLibrary):
    def setup_test(self, pattern: str, input: str):
        match = regex.match(pattern, input)
        # Convert to picklable format
        return match is not None


class Pyre2(RegexLibrary):
    def setup_test(self, pattern: str, input: str):
        match = pyre2.match(pattern, input)
        # Convert to picklable format
        return match is not None


class Hyperscan(RegexLibrary):
    def setup_test(self, pattern: str, input: str):
        match = hyperscan.match(pattern, input)
        # Convert to picklable format
        return bool(match) if match is not None else None


if __name__ == "__main__":
    libraries = [Rure(), Re(), Regex(), Pyre2()]

    tests = [
        # Classic nested quantifiers
        ("^(a+)+$", "a" * 20 + "B"),
        ("^(a*)*$", "a" * 20 + "B"),
        ("^(a+)+b$", "a" * 20 + "c"),
        # Alternation with overlapping patterns
        ("^(a|a)*$", "a" * 20 + "B"),
        ("^(a|ab)*$", "a" * 20 + "B"),
        ("(a|a|a|a|a|b)*c", "a" * 25 + "d"),
        # Nested groups with quantifiers
        ("^((a+)+)+$", "a" * 18 + "B"),
        ("^(a*)*b$", "a" * 20 + "c"),
        ("^(a+)*b$", "a" * 20 + "c"),
        # Email-like patterns (common real-world ReDoS)
        (
            "^([a-zA-Z0-9])(([\\-.]|[_]+)?([a-zA-Z0-9]+))*(@){1}[a-z0-9]+[.]{1}(([a-z]{2,3})|([a-z]{2,3}[.]{1}[a-z]{2,3}))$",
            "a" * 30 + "@",
        ),
        # Overlapping character classes
        ("^([a-z]+)+[A-Z]$", "a" * 25 + "1"),
        ("^([0-9a-z]+)+[A-Z]$", "a" * 25 + "!"),
        # Grouping with wildcards
        ("^(.*)*$", "a" * 20 + "B"),
        ("^(.+)+$", "a" * 20 + "B"),
        ("^(.*)+b$", "a" * 20 + "c"),
        # Multiple overlapping quantifiers
        ("^(a*)+b$", "a" * 25 + "c"),
        ("^(a?)+b$", "a" * 25 + "c"),
        ("^(a*?)*b$", "a" * 20 + "c"),
        # Word boundary catastrophic cases
        ("^(\\w+\\s*)+$", "a " * 15 + "!"),
        ("^([\\w]+[\\s]*)*$", "test " * 10 + "!"),
        # Digit patterns
        ("^(\\d+)+$", "1" * 25 + "a"),
        ("^([0-9]+)*$", "9" * 25 + "x"),
        # Complex alternation
        ("^(a+|a+)+$", "a" * 20 + "B"),
        ("^(a*|a*)*$", "a" * 20 + "B"),
        ("^(aa+|a+)+$", "a" * 22 + "B"),
        # Real-world URL pattern (simplified)
        ("^(http://)?([a-z]+\\.)*[a-z]+\\.[a-z]{2,}$", "http://a." * 10 + "!"),
        # Whitespace patterns
        ("^(\\s*a+\\s*)+$", " a" * 15 + "!"),
        ("^(\\s+|a+)*b$", "a " * 15 + "c"),
        # Optional group patterns
        ("^(a+)?b?(a+)?$", "a" * 25 + "c"),
        ("^(a+b?)+c$", "a" * 20 + "d"),
        # Character class repetition
        ("^([a-zA-Z]+)*$", "a" * 25 + "1"),
        ("^([a-z0-9]+)+[!]$", "abc123" * 5 + "?"),
        # Nested alternation
        ("^((a|b)+)+c$", "a" * 25 + "d"),
        ("^((a|ab)+)+c$", "a" * 20 + "d"),
        # Long repeating patterns
        ("^(a+b)+c$", "ab" * 15 + "d"),
        ("^(ab+)+c$", "ab" * 15 + "d"),
    ]

    all_results = []
    num_runs = 3

    print(
        f"Running {num_runs} iterations of {len(tests)} tests across {len(libraries)} libraries..."
    )

    for run in range(num_runs):
        print(f"Run {run + 1}/{num_runs}")

        for test_idx, (pattern, text) in enumerate(tests):
            for library in libraries:
                print(f"Running {library.__class__.__name__} test {pattern} on {text}")

                res = library.test(pattern, text)

                result_entry = {
                    "run": run + 1,
                    "test_id": test_idx + 1,
                    "pattern": pattern,
                    "input": text,
                    "library": library.__class__.__name__,
                    "result": str(res),
                }
                all_results.append(result_entry)

    # Calculate summary statistics
    summary_stats = {}

    for lib in libraries:
        lib_name = lib.__class__.__name__

        # Filter results for this library
        lib_results = [r for r in all_results if r["library"] == lib_name]

        # Extract times and timeout info
        times = []
        timeout_count = 0

        for r in lib_results:
            result_dict = eval(r["result"])  # Convert string back to dict
            if result_dict["timed_out"]:
                timeout_count += 1
            else:
                times.append(result_dict["time"])

        # Calculate stats
        if times:
            times_sorted = sorted(times)
            n = len(times)
            summary_stats[lib_name] = {
                "mean_time": sum(times) / n,
                "median_time": times_sorted[n // 2]
                if n % 2 == 1
                else (times_sorted[n // 2 - 1] + times_sorted[n // 2]) / 2,
                "min_time": min(times),
                "max_time": max(times),
                "timeout_count": timeout_count,
                "successful_count": len(times),
                "total_count": len(lib_results),
            }
        else:
            summary_stats[lib_name] = {
                "mean_time": None,
                "median_time": None,
                "min_time": None,
                "max_time": None,
                "timeout_count": timeout_count,
                "successful_count": 0,
                "total_count": len(lib_results),
            }

    output_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_runs": num_runs,
            "total_tests": len(tests),
            "total_libraries": len(libraries),
            "libraries": [lib.__class__.__name__ for lib in libraries],
        },
        "summary_stats": summary_stats,
        "results": all_results,
    }

    output_filename = "redos_test_results.json"
    with open(output_filename, "w") as f:
        json.dump(output_data, f, indent=2)

    print(
        f"\nComplete! {len(all_results)} total test results saved to {output_filename}"
    )
    print("\nSummary Statistics:")
    for lib_name, stats in summary_stats.items():
        print(f"\n{lib_name}:")
        print(
            f"  Mean time: {stats['mean_time']:.6f}s"
            if stats["mean_time"]
            else "  Mean time: N/A"
        )
        print(
            f"  Median time: {stats['median_time']:.6f}s"
            if stats["median_time"]
            else "  Median time: N/A"
        )
        print(
            f"  Min time: {stats['min_time']:.6f}s"
            if stats["min_time"]
            else "  Min time: N/A"
        )
        print(
            f"  Max time: {stats['max_time']:.6f}s"
            if stats["max_time"]
            else "  Max time: N/A"
        )
        print(f"  Timeouts: {stats['timeout_count']}/{stats['total_count']}")
