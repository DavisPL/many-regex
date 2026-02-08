import json
import time
from pathlib import Path

import re2 as pyre2


TARGET_ID = 36


def load_case(test_id: int) -> dict:
    repo_root = Path(__file__).resolve().parent.parent
    test_cases_path = repo_root / "test_cases.json"
    with test_cases_path.open("r", encoding="utf-8") as f:
        cases = json.load(f)

    for case in cases:
        if case.get("id") == test_id:
            return case

    raise ValueError(f"Test case id {test_id} was not found in {test_cases_path}")


def timed_match(pattern: str, text: str) -> tuple[bool, float]:
    start = time.perf_counter()
    match = pyre2.match(pattern, text)
    duration = time.perf_counter() - start
    return match is not None, duration


def main() -> None:
    case = load_case(TARGET_ID)
    pattern = case["regex"]
    repeat = case["repeat"]
    description = case.get("description", "")

    # Build a few inputs from the repeat token to test both match and non-match behavior.
    samples = [
        ("no-trailing-c", repeat * 40),
        ("with-trailing-c", (repeat * 40) + "c"),
        ("single-repeat-with-c", repeat + "c"),
    ]

    print(f"Testing pyre2 on case id {case['id']}")
    print(f"Description: {description}")
    print(f"Pattern: {pattern}")
    print(f"Repeat token: {repeat!r}")
    print()

    for label, text in samples:
        matched, seconds = timed_match(pattern, text)
        print(
            f"{label:20} matched={matched!s:5} "
            f"length={len(text):4} time={seconds * 1000:.4f} ms"
        )


if __name__ == "__main__":
    main()
