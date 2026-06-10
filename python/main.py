from abc import ABC, abstractmethod
import argparse
from multiprocessing import Pipe, Process
import signal
import time
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, replace
from typing import List, Optional

import re  # default python
import rure  # https://pypi.org/project/rure/
import regex  # https://pypi.org/project/regex/
import re2 as pyre2  # https://pypi.org/project/pyre2/


@dataclass
class LibraryResult:
    library: str
    result: Optional[bool]
    time: float
    timed_out: bool


@dataclass
class SingleTestResult:
    test_id: int
    pattern: str
    input: str
    library: str
    result: LibraryResult


@dataclass
class CaseMetadata:
    """Per-case metadata carried from the new experiment-dataset schema.

    Absent (None on the result entry) when running the legacy
    `test_cases.json` flow, so backward compatibility is preserved.
    """
    group: Optional[str]
    size: Optional[str]
    ast_size: Optional[int]
    ast_depth: Optional[int]
    regex_size: Optional[int]
    input_size: Optional[int]


@dataclass
class PreparedCase:
    test_id: int
    pattern: str
    input: str
    metadata: Optional[CaseMetadata]


@dataclass
class ScalingTestEntry:
    test_id: int
    size: int
    result: List[SingleTestResult]


class RegexLibrary(ABC):
    TIMEOUT_SECONDS = 2

    @abstractmethod
    def setup_test(self, pattern: str, input: str) -> bool:
        pass

    def test(self, pattern: str, input: str):
        start_time = time.perf_counter()
        parent_conn, child_conn = Pipe(duplex=False)
        process = Process(
            target=run_library_match_in_subprocess,
            args=(self.__class__.__name__, pattern, input, child_conn),
        )

        try:
            process.start()
            child_conn.close()
            process.join(self.TIMEOUT_SECONDS)

            if process.is_alive():
                process.terminate()
                process.join()
                duration = time.perf_counter() - start_time
                return {
                    "library": self.__class__.__name__,
                    "result": None,
                    "time": duration,
                    "timed_out": True,
                }

            if parent_conn.poll():
                response = parent_conn.recv()
            else:
                response = {"ok": False, "error": "NoResult"}

            if response.get("ok"):
                duration = time.perf_counter() - start_time
                return {
                    "library": self.__class__.__name__,
                    "result": response["result"],
                    "time": duration,
                    "timed_out": False,
                }

            if response.get("error") == "RegexSyntaxError":
                return {
                    "library": self.__class__.__name__,
                    "result": None,
                    "time": 0,
                    "timed_out": False,
                }

            duration = time.perf_counter() - start_time
            return {
                "library": self.__class__.__name__,
                "result": None,
                "time": duration,
                "timed_out": False,
            }
        finally:
            parent_conn.close()


def run_library_match_in_subprocess(library_name: str, pattern: str, input: str, conn):
    try:
        if library_name == "Rure":
            match = rure.match(pattern, input)
            result = bool(match) if match is not None else False
        elif library_name == "Re":
            result = re.match(pattern, input) is not None
        elif library_name == "Regex":
            result = regex.match(pattern, input) is not None
        elif library_name == "Pyre2":
            result = pyre2.match(pattern, input) is not None
        else:
            conn.send({"ok": False, "error": f"UnknownLibrary:{library_name}"})
            return

        conn.send({"ok": True, "result": result})
    except rure.exceptions.RegexSyntaxError:
        conn.send({"ok": False, "error": "RegexSyntaxError"})
    except KeyboardInterrupt:
        conn.send({"ok": False, "error": "KeyboardInterrupt"})
    except Exception as exc:
        conn.send({"ok": False, "error": f"Unhandled:{type(exc).__name__}"})
    finally:
        conn.close()


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


# ---------- In-process timing (no subprocess) ---------- #

class _InProcessTimeout(Exception):
    pass


def _sigalrm_handler(signum, frame):
    raise _InProcessTimeout()


def run_in_process(library, pattern: str, text: str, timeout: float) -> dict:
    """Time library.setup_test() directly in the host process.

    Uses SIGALRM to enforce a wall-clock timeout (Linux-only). On timeout,
    the alarm raises _InProcessTimeout and we record a timed-out result with
    the requested timeout as the time.
    """
    name = library.__class__.__name__
    signal.signal(signal.SIGALRM, _sigalrm_handler)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    start = time.perf_counter()
    try:
        result = library.setup_test(pattern, text)
        duration = time.perf_counter() - start
        return {"library": name, "result": result,
                "time": duration, "timed_out": False}
    except _InProcessTimeout:
        return {"library": name, "result": None,
                "time": timeout, "timed_out": True}
    except Exception:
        duration = time.perf_counter() - start
        return {"library": name, "result": None,
                "time": duration, "timed_out": False}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def get_test_cases(input_size=20):
    test_cases_path = Path("test_cases.json")

    with test_cases_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    cases = []
    for i, entry in enumerate(data):
        pattern = entry["regex"]
        repeat = entry["repeat"] * input_size
        cases.append(PreparedCase(
            test_id=i + 1,
            pattern=pattern,
            input=repeat,
            metadata=None,
        ))

    return cases


# Default input sizes (chars) swept per dataset case when --input-sweep is not
# given. Mirrors the Rust runner so all engines share the heatmap's input axis.
DEFAULT_INPUT_SWEEP = [1000, 10000, 25000, 50000, 75000, 100000, 150000, 200000]


def resize_input(base: str, target: int) -> str:
    """Rebuild an input of exactly `target` chars from a case's base string by
    repeating then truncating it. Dataset inputs are runs of a single repeat
    unit, so any prefix/extension is still a valid same-character input."""
    if target <= 0 or not base:
        return ""
    reps = -(-target // len(base))  # ceil division
    return (base * reps)[:target]


def expand_with_sweep(cases, sweep):
    """One PreparedCase per (case, swept input size), rebuilding the input and
    overriding metadata.input_size."""
    expanded = []
    for case in cases:
        for target in sweep:
            new_input = resize_input(case.input, target)
            meta = case.metadata
            new_meta = (replace(meta, input_size=len(new_input))
                        if meta is not None else None)
            expanded.append(PreparedCase(
                test_id=case.test_id,
                pattern=case.pattern,
                input=new_input,
                metadata=new_meta,
            ))
    return expanded


def parse_input_sweep(raw):
    """Parse --input-sweep: a comma list of ints, or `none` to disable. Returns
    None when the flag is absent (caller uses DEFAULT_INPUT_SWEEP)."""
    if raw is None:
        return None
    if raw.strip().lower() == "none":
        return []
    return [int(s) for s in raw.split(",") if s.strip()]


def get_dataset_cases(dataset_dir):
    """Load every *.json file in [dataset_dir] as a new-schema per-case JSON.

    Files are sorted by filename so the order matches the dataset `id`.
    """
    dataset_path = Path(dataset_dir)
    cases = []
    for path in sorted(dataset_path.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            c = json.load(f)
        cases.append(PreparedCase(
            test_id=c["id"],
            pattern=c["regex"],
            input=c["input"],
            metadata=CaseMetadata(
                group=c.get("group"),
                size=c.get("size"),
                ast_size=c.get("ast_size"),
                ast_depth=c.get("ast_depth"),
                regex_size=c.get("regex_size"),
                input_size=c.get("input_size"),
            ),
        ))
    return cases


def get_libraries():
    """Get all regex library instances."""
    return [Rure(), Re(), Regex(), Pyre2()]


def _metadata_dict(meta):
    if meta is None:
        return None
    return {
        "group": meta.group,
        "size": meta.size,
        "ast_size": meta.ast_size,
        "ast_depth": meta.ast_depth,
        "regex_size": meta.regex_size,
        "input_size": meta.input_size,
    }


def _exec_library(library, pattern, text, in_process: bool, timeout: float):
    if in_process:
        return run_in_process(library, pattern, text, timeout)
    return library.test(pattern, text)


def run_single_test(test_id, libraries=None, input_size=20, tests=None,
                    in_process: bool = False, timeout: float = 2.0):
    """Run a single test case across all libraries.

    Pass [tests] to reuse a preloaded case list (e.g. when running the new
    dataset). When omitted, falls back to the legacy `test_cases.json` flow.
    """
    if libraries is None:
        libraries = get_libraries()

    if tests is None:
        tests = get_test_cases(input_size)

    if test_id < 1 or test_id > len(tests):
        raise ValueError(f"Invalid test_id. Must be between 1 and {len(tests)}")

    case = tests[test_id - 1]
    pattern, text = case.pattern, case.input
    results = []

    print(f"Running test {test_id}: pattern={pattern}, input_length={len(text)}")

    for library in libraries:
        print(f"  Testing with {library.__class__.__name__}...")
        res = _exec_library(library, pattern, text, in_process, timeout)
        entry = {
            "test_id": test_id,
            "pattern": pattern,
            "input": text,
            "library": library.__class__.__name__,
            "result": res,
        }
        md = _metadata_dict(case.metadata)
        if md is not None:
            entry["metadata"] = md
        results.append(entry)

    return results


def run_all_tests(num_runs=3, libraries=None, input_size=20, tests=None,
                  in_process: bool = False, timeout: float = 2.0):
    """Run all test cases for multiple iterations.

    Pass [tests] to use the preloaded new-schema dataset; otherwise the
    legacy `test_cases.json` cases are loaded.
    """
    if libraries is None:
        libraries = get_libraries()

    if tests is None:
        tests = get_test_cases(input_size)
    all_results = []

    mode = "in-process" if in_process else "subprocess"
    print(
        f"Running {num_runs} iterations of {len(tests)} tests "
        f"across {len(libraries)} libraries ({mode})..."
    )

    for run in range(num_runs):
        print(f"\nRun {run + 1}/{num_runs}")

        for case in tests:
            pattern, text = case.pattern, case.input
            md = _metadata_dict(case.metadata)
            for library in libraries:
                print(f"  {library.__class__.__name__} - Test {case.test_id}")

                res = _exec_library(library, pattern, text, in_process, timeout)

                result_entry = {
                    "run": run + 1,
                    "test_id": case.test_id,
                    "pattern": pattern,
                    "input": text,
                    "library": library.__class__.__name__,
                    "result": str(res),
                }
                if md is not None:
                    result_entry["metadata"] = md
                all_results.append(result_entry)

    return all_results


def calculate_summary_stats(all_results, libraries):
    """Calculate summary statistics from test results."""
    summary_stats = {}

    for lib in libraries:
        lib_name = lib.__class__.__name__
        lib_results = [r for r in all_results if r["library"] == lib_name]
        unique_test_ids = {r["test_id"] for r in lib_results}
        run_ids = {r["run"] for r in lib_results}

        times = []
        timeout_count = 0
        timeout_test_ids = set()

        for r in lib_results:
            result_dict = eval(r["result"])
            if result_dict["timed_out"]:
                timeout_count += 1
                timeout_test_ids.add(r["test_id"])
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
                "timeout_tests_count": len(timeout_test_ids),
                "successful_count": len(times),
                "total_count": len(lib_results),
                "total_test_cases": len(unique_test_ids),
                "run_count": len(run_ids),
            }
        else:
            summary_stats[lib_name] = {
                "mean_time": None,
                "median_time": None,
                "min_time": None,
                "max_time": None,
                "timeout_count": timeout_count,
                "timeout_tests_count": len(timeout_test_ids),
                "successful_count": 0,
                "total_count": len(lib_results),
                "total_test_cases": len(unique_test_ids),
                "run_count": len(run_ids),
            }

    return summary_stats


def save_results(
    all_results,
    summary_stats,
    libraries,
    num_runs,
    tests_count,
    filename="py_redos_test_results.json",
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
        print(
            f"  Timeouts (executions): {stats['timeout_count']}/{stats['total_count']}"
        )
        print(
            "  Timeout test cases (unique): "
            f"{stats['timeout_tests_count']}/{stats['total_test_cases']}"
        )
        print(
            f"  Runs: {stats['run_count']} | Unique test cases: {stats['total_test_cases']}"
        )


def run_scaling_test():
    all_results = []

    tests_count = len(get_test_cases())

    for test_id in range(1, tests_count):
        for size in range(30):
            results = run_single_test(test_id=test_id, input_size=size)

            all_results.append(
                {"test_id": test_id, "size": size, "result": results},
            )

    with open("py_scaling_test.json", "w") as file:
        json.dump(all_results, file)


def timeout_label(timeout_seconds: float) -> str:
    if float(timeout_seconds).is_integer():
        return str(int(timeout_seconds))
    return str(timeout_seconds).replace(".", "_")


def build_output_filename(timeout_seconds: float) -> str:
    return f"py_redos_test_results_timeout-{timeout_label(timeout_seconds)}.json"


def parse_args():
    parser = argparse.ArgumentParser(description="Run regex tests across Python libraries.")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--single", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--input-length", type=int, default=20)
    parser.add_argument(
        "--input-size",
        type=int,
        default=None,
        help="Deprecated alias for --input-length.",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to a directory of new-schema per-case JSON files "
             "(e.g. experiment-dataset/). Overrides --input-length.",
    )
    parser.add_argument(
        "--input-sweep",
        type=str,
        default=None,
        help="Comma-separated input sizes (chars) to sweep per dataset case, "
             "or 'none' to use each case's stored input. Default: built-in "
             "sweep. Only applies in --dataset mode.",
    )
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="Time each match in the host process (no subprocess). Uses "
             "SIGALRM (Linux) to enforce --timeout. Faster, lower overhead, "
             "but a hung regex blocks the whole run until the alarm fires.",
    )
    return parser.parse_args()


def main_run_all_tests(tests, num_runs: int, output_filename: str,
                       in_process: bool = False, timeout: float = 2.0):

    # Run all tests
    libraries = get_libraries()
    all_results = run_all_tests(
        num_runs=num_runs, libraries=libraries, tests=tests,
        in_process=in_process, timeout=timeout,
    )
    summary_stats = calculate_summary_stats(all_results, libraries)
    save_results(
        all_results,
        summary_stats,
        libraries,
        num_runs,
        len(tests),
        output_filename,
    )
    print_summary_stats(summary_stats)


def main_run_single_test(test_id: int, tests, in_process: bool = False,
                         timeout: float = 2.0):

    # Run a single test
    print("Running single test example:")
    results = run_single_test(
        test_id=test_id, tests=tests,
        in_process=in_process, timeout=timeout,
    )
    for result in results:
        print(f"{result['library']}: {result['result']}")


if __name__ == "__main__":
    args = parse_args()
    input_length = args.input_size if args.input_size is not None else args.input_length
    RegexLibrary.TIMEOUT_SECONDS = args.timeout

    inproc_tag = "_inproc" if args.in_process else ""
    if args.dataset is not None:
        tests = get_dataset_cases(args.dataset)
        sweep = parse_input_sweep(args.input_sweep)
        if sweep is None:
            sweep = DEFAULT_INPUT_SWEEP
        if sweep:
            print(f"Sweeping input sizes: {sweep}")
            tests = expand_with_sweep(tests, sweep)
        output_filename = (
            f"py_redos_test_results_dataset{inproc_tag}_timeout-"
            f"{timeout_label(args.timeout)}.json"
        )
    else:
        tests = get_test_cases(input_length)
        legacy_name = build_output_filename(args.timeout)
        if args.in_process:
            legacy_name = legacy_name.replace(
                "py_redos_test_results", "py_redos_test_results_inproc"
            )
        output_filename = legacy_name

    scaling_test = False

    if scaling_test:
        run_scaling_test()
    else:
        if args.single is None:
            main_run_all_tests(
                tests=tests,
                num_runs=args.runs,
                output_filename=output_filename,
                in_process=args.in_process,
                timeout=args.timeout,
            )
        else:
            main_run_single_test(
                args.single, tests,
                in_process=args.in_process, timeout=args.timeout,
            )
