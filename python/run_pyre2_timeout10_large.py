import argparse
import ast
import json
from pathlib import Path

from main import Pyre2, RegexLibrary, run_single_test


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    default_results = repo_root / "py_redos_test_results_timeout-10.json"

    parser = argparse.ArgumentParser(
        description="Run only the Pyre2 tests that timed out at ~10 seconds."
    )
    parser.add_argument(
        "--results-file",
        type=Path,
        default=default_results,
        help="Path to py_redos_test_results_timeout-10.json.",
    )
    parser.add_argument(
        "--input-length",
        type=int,
        default=100,
        help="Large input multiplier applied to each test case repeat token.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout in seconds for each test run.",
    )
    parser.add_argument(
        "--target-seconds",
        type=float,
        default=10.0,
        help="Timeout duration (seconds) to filter from the results file.",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=0.25,
        help="Allowed delta around --target-seconds.",
    )
    return parser.parse_args()


def parse_result(raw_result):
    if isinstance(raw_result, dict):
        return raw_result
    if isinstance(raw_result, str):
        try:
            parsed = ast.literal_eval(raw_result)
        except (ValueError, SyntaxError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def collect_timeout_test_ids(
    results_file: Path, target_seconds: float, epsilon: float
) -> list[int]:
    with results_file.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    test_ids = set()
    for entry in payload.get("results", []):
        if entry.get("library") != "Pyre2":
            continue

        result = parse_result(entry.get("result"))
        if not result or not result.get("timed_out"):
            continue

        duration = result.get("time")
        if isinstance(duration, (float, int)) and abs(duration - target_seconds) <= epsilon:
            test_ids.add(int(entry["test_id"]))

    return sorted(test_ids)


def main() -> None:
    args = parse_args()
    RegexLibrary.TIMEOUT_SECONDS = args.timeout

    test_ids = collect_timeout_test_ids(
        results_file=args.results_file,
        target_seconds=args.target_seconds,
        epsilon=args.epsilon,
    )

    if not test_ids:
        print("No matching timed-out Pyre2 test IDs found.")
        return

    print(f"Matched Pyre2 timeout test IDs: {test_ids}")
    print(
        f"Running {len(test_ids)} tests with input_length={args.input_length} "
        f"and timeout={args.timeout}s"
    )

    for test_id in test_ids:
        results = run_single_test(
            test_id=test_id,
            libraries=[Pyre2()],
            input_size=args.input_length,
        )
        for result in results:
            print(result)


if __name__ == "__main__":
    main()
