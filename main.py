from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor, TimeoutError
import time
import json
from pathlib import Path
from datetime import datetime

import re  # default python
import rure  # https://pypi.org/project/rure/
import regex  # https://pypi.org/project/regex/
import re2 as pyre2  # https://pypi.org/project/pyre2/


class RegexLibrary(ABC):
    TIMEOUT_SECONDS = 2

    @abstractmethod
    def setup_test(self, pattern: str, input: str) -> bool:
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
        return bool(match) if match is not None else False


class Re(RegexLibrary):
    def setup_test(self, pattern: str, input: str):
        match = re.match(pattern, input)
        return match is not None


class Regex(RegexLibrary):
    def setup_test(self, pattern: str, input: str):
        match = regex.match(pattern, input)
        return match is not None


class Pyre2(RegexLibrary):
    def setup_test(self, pattern: str, input: str):
        match = pyre2.match(pattern, input)
        return match is not None


def get_test_cases(input_size=20):
    test_cases_path = Path(__file__).with_name("test_cases.json")

    with test_cases_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    cases = []
    for entry in data:
        pattern = entry["regex"]
        repeat = entry["repeat"] * input_size
        cases.append((pattern, repeat))

    return cases


def get_libraries():
    """Get all regex library instances."""
    return [Rure(), Re(), Regex(), Pyre2()]


def run_single_test(test_id, libraries=None, input_size=20):
    """Run a single test case across all libraries."""
    if libraries is None:
        libraries = get_libraries()

    tests = get_test_cases(input_size)

    if test_id < 1 or test_id > len(tests):
        raise ValueError(f"Invalid test_id. Must be between 1 and {len(tests)}")

    pattern, text = tests[test_id - 1]
    results = []

    print(f"Running test {test_id}: pattern={pattern}, input_length={len(text)}")

    for library in libraries:
        print(f"  Testing with {library.__class__.__name__}...")
        res = library.test(pattern, text)
        results.append(
            {
                "test_id": test_id,
                "pattern": pattern,
                "input": text,
                "library": library.__class__.__name__,
                "result": res,
            }
        )

    return results


def run_all_tests(num_runs=3, libraries=None, input_size=20):
    """Run all test cases for multiple iterations."""
    if libraries is None:
        libraries = get_libraries()

    tests = get_test_cases(input_size)
    all_results = []

    print(
        f"Running {num_runs} iterations of {len(tests)} tests across {len(libraries)} libraries..."
    )
    print(f"Input size multiplier: {input_size}")

    for run in range(num_runs):
        print(f"\nRun {run + 1}/{num_runs}")

        for test_idx, (pattern, text) in enumerate(tests):
            for library in libraries:
                print(f"  {library.__class__.__name__} - Test {test_idx + 1}")

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

    return all_results


def calculate_summary_stats(all_results, libraries):
    """Calculate summary statistics from test results."""
    summary_stats = {}

    for lib in libraries:
        lib_name = lib.__class__.__name__
        lib_results = [r for r in all_results if r["library"] == lib_name]

        times = []
        timeout_count = 0

        for r in lib_results:
            result_dict = eval(r["result"])
            if result_dict["timed_out"]:
                timeout_count += 1
            else:
                times.append(result_dict["time"])

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

    return summary_stats


def save_results(
    all_results,
    summary_stats,
    libraries,
    num_runs,
    tests_count,
    filename="redos_test_results.json",
):
    """Save results to a JSON file."""
    output_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_runs": num_runs,
            "total_tests": tests_count,
            "total_libraries": len(libraries),
            "libraries": [lib.__class__.__name__ for lib in libraries],
        },
        "summary_stats": summary_stats,
        "results": all_results,
    }

    with open(filename, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n{len(all_results)} total test results saved to {filename}")


def print_summary_stats(summary_stats):
    """Print summary statistics in a readable format."""
    print("\nSummary Statistics:")
    for lib_name, stats in summary_stats.items():
        print(f"\n{lib_name}:")
        if stats["mean_time"]:
            print(f"  Mean time: {stats['mean_time']:.6f}s")
            print(f"  Median time: {stats['median_time']:.6f}s")
            print(f"  Min time: {stats['min_time']:.6f}s")
            print(f"  Max time: {stats['max_time']:.6f}s")
        else:
            print("  No successful completions")
        print(f"  Timeouts: {stats['timeout_count']}/{stats['total_count']}")


def run_scaling_test():
    all_results = []

    for test_id in range(1, 37):
        for size in range(30):
            results = run_single_test(test_id=test_id, input_size=size)

            all_results.append(
                {"test_id": test_id, "size": size, "result": results},
            )

    with open("scaling_test.json", "w") as file:
        json.dump(all_results, file)


def main_run_all_tests():
    INPUT_SIZE = 20
    NUM_RUNS = 3

    # Run all tests
    libraries = get_libraries()
    all_results = run_all_tests(
        num_runs=NUM_RUNS, libraries=libraries, input_size=INPUT_SIZE
    )
    summary_stats = calculate_summary_stats(all_results, libraries)
    save_results(
        all_results,
        summary_stats,
        libraries,
        NUM_RUNS,
        len(get_test_cases(INPUT_SIZE)),
    )
    print_summary_stats(summary_stats)


def main_run_single_test():
    INPUT_SIZE = 20

    # Run a single test
    print("Running single test example:")
    results = run_single_test(test_id=run_specific_test, input_size=INPUT_SIZE)
    for result in results:
        print(f"{result['library']}: {result['result']}")


if __name__ == "__main__":
    scaling_test = True

    if scaling_test:
        run_scaling_test()
    else:
        # Either a test ID to run or None
        run_specific_test = None

        if run_specific_test is None:
            main_run_all_tests()
        else:
            main_run_single_test()
