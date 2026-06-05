#!/usr/bin/env python3
"""Build the 1017-case experimental regex dataset.

Groups:
  A. known_bad              — 113 hand-curated ReDoS regexes from test_cases.json
  B. generated_low_complexity — 113 freak-generated shallow-AST regexes (long 'a' literals)
  C. generated_high_complexity — 113 freak-generated regexes at AST depths 3/5/7

Each group is expanded to 3 sizes (small/medium/large) → 113*3*3 = 1017 cases.

Outputs one JSON file per case into the dataset directory and a single
combined index file.
"""

from __future__ import annotations

import json
import re._parser as sre
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST_CASES = ROOT / "test_cases.json"
GENERATOR = ROOT / "freak" / "_build" / "default" / "bin" / "generate.exe"
OUT_DIR = ROOT / "experiment-dataset"
INDEX_FILE = ROOT / "experiment-dataset-index.json"

# Fixed input size for all cases. The "size" dimension varies the regex, not
# the input. Per-case input is a long run of a single character.
INPUT_SIZE = 10_000

# Target large regex length (in characters) per the spec.
LARGE_TARGET_CHARS = 150


# ------------------------------ AST metrics ------------------------------- #

def ast_metrics(pattern: str) -> tuple[int, int]:
    """Return (ast_size, ast_depth) parsed by Python's regex parser.

    Provides a uniform measurement across all three groups regardless of how
    the regex was authored or generated. Returns (-1, -1) if the pattern is
    not parseable by Python (some freak outputs use RE2-only constructs).
    """
    try:
        tree = sre.parse(pattern)
    except Exception:
        return (-1, -1)

    def walk(node, depth):
        # Each SubPattern is a list of (opcode, args) tuples.
        size = 0
        max_d = depth
        for _op, args in node:
            size += 1
            for child in _children(args):
                csize, cdepth = walk(child, depth + 1)
                size += csize
                max_d = max(max_d, cdepth)
        return size, max_d

    size, depth = walk(tree, 1)
    return size, depth


def _children(args):
    """Extract any SubPattern children from a parsed opcode's args."""
    out = []
    if isinstance(args, tuple):
        for a in args:
            out.extend(_subpattern_only(a))
    else:
        out.extend(_subpattern_only(args))
    return out


def _subpattern_only(x):
    # SubPattern is iterable of tuples; treat anything list/SubPattern-like
    # that contains (op, args) pairs as a child node.
    try:
        items = list(x)
    except TypeError:
        return []
    if items and isinstance(items[0], tuple) and len(items[0]) == 2:
        return [x]
    return []


# ------------------------------ Group A ----------------------------------- #

def strip_anchors(pattern: str) -> tuple[str, bool, bool]:
    """Strip leading ^ and trailing $ (if present and not escaped)."""
    has_start = pattern.startswith("^")
    core = pattern[1:] if has_start else pattern
    has_end = core.endswith("$") and not core.endswith(r"\$")
    if has_end:
        core = core[:-1]
    return core, has_start, has_end


def group_a_variants(pattern: str) -> dict[str, str]:
    """Produce small/medium/large variants of a known-bad regex.

    Small  → original.
    Medium → core concatenated 3x (anchors re-applied).
    Large  → core concatenated enough times to reach ~LARGE_TARGET_CHARS.
    Both repetitions still match the same all-repeat-char input as the
    original because the structures are concatenations of the same matcher.
    """
    core, has_start, has_end = strip_anchors(pattern)

    def wrap(core_repeated: str) -> str:
        return ("^" if has_start else "") + core_repeated + ("$" if has_end else "")

    small = pattern
    medium = wrap(core * 3)
    n = max(2, LARGE_TARGET_CHARS // max(1, len(core)))
    large = wrap(core * n)
    return {"small": small, "medium": medium, "large": large}


def load_known_bad() -> list[dict]:
    with TEST_CASES.open() as f:
        return json.load(f)


# ------------------------------ Groups B/C -------------------------------- #

def run_generator(args: list[str]) -> list[dict]:
    proc = subprocess.run(
        [str(GENERATOR), *args], capture_output=True, text=True, check=True
    )
    out = []
    for line in proc.stdout.strip().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def gen_group_b(per_size: int, seed_base: int) -> dict[str, list[dict]]:
    targets = {"small": 15, "medium": 60, "large": LARGE_TARGET_CHARS}
    out = {}
    for i, (size, tc) in enumerate(targets.items()):
        out[size] = run_generator([
            "--mode", "low",
            "--count", str(per_size),
            "--target-chars", str(tc),
            "--seed", str(seed_base + i),
        ])
    return out


def gen_group_c(per_size: int, seed_base: int) -> dict[str, list[dict]]:
    depths = {"small": 3, "medium": 5, "large": 7}
    out = {}
    for i, (size, d) in enumerate(depths.items()):
        # Generate more than needed and keep only those Python can parse,
        # so AST metrics are well-defined for the dataset.
        candidates = run_generator([
            "--mode", "high",
            "--count", str(per_size * 4),
            "--depth", str(d),
            "--seed", str(seed_base + 100 + i),
        ])
        kept = []
        for c in candidates:
            sz, dp = ast_metrics(c["regex"])
            if sz > 0 and dp > 0:
                kept.append(c)
            if len(kept) >= per_size:
                break
        if len(kept) < per_size:
            raise RuntimeError(
                f"Group C size={size}: only {len(kept)}/{per_size} parseable"
            )
        out[size] = kept
    return out


# ------------------------------ Dataset emit ------------------------------ #

def make_input(repeat_char: str, size: int) -> str:
    return repeat_char * size


def emit_case(idx: int, group: str, size: str, regex: str, repeat_char: str,
              extra: dict | None = None) -> dict:
    ast_sz, ast_dp = ast_metrics(regex)
    input_str = make_input(repeat_char, INPUT_SIZE)
    case = {
        "id": idx,
        "regex": regex,
        "input": input_str,
        "regex_size": len(regex),
        "input_size": len(input_str),
        "ast_size": ast_sz,
        "ast_depth": ast_dp,
        "group": group,
        "size": size,
    }
    if extra:
        case.update(extra)
    return case


def main() -> None:
    if not GENERATOR.exists():
        raise SystemExit(
            f"freak generator not built at {GENERATOR}. "
            "Build with: cd freak && dune build bin/generate.exe"
        )

    OUT_DIR.mkdir(exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()

    known_bad = load_known_bad()
    assert len(known_bad) == 113, f"expected 113 known-bad, got {len(known_bad)}"

    group_b = gen_group_b(per_size=113, seed_base=1000)
    group_c = gen_group_c(per_size=113, seed_base=2000)

    cases: list[dict] = []
    idx = 1

    # Group A
    for kb in known_bad:
        variants = group_a_variants(kb["regex"])
        repeat = kb.get("repeat") or "a"
        for size in ("small", "medium", "large"):
            cases.append(emit_case(
                idx, "known_bad", size, variants[size], repeat,
                extra={"source_id": kb["id"],
                       "description": kb.get("description", "")},
            ))
            idx += 1

    # Group B (low complexity)
    for size in ("small", "medium", "large"):
        for entry in group_b[size]:
            cases.append(emit_case(
                idx, "generated_low_complexity", size, entry["regex"], "a",
                extra={"freak_ast_size": entry["ast_size"],
                       "freak_ast_depth": entry["ast_depth"]},
            ))
            idx += 1

    # Group C (high complexity)
    depth_for_size = {"small": 3, "medium": 5, "large": 7}
    for size in ("small", "medium", "large"):
        for entry in group_c[size]:
            cases.append(emit_case(
                idx, "generated_high_complexity", size, entry["regex"], "a",
                extra={"freak_ast_size": entry["ast_size"],
                       "freak_ast_depth": entry["ast_depth"],
                       "freak_gen_depth": depth_for_size[size]},
            ))
            idx += 1

    # Write per-case files + combined index.
    for c in cases:
        (OUT_DIR / f"{c['id']:04d}.json").write_text(json.dumps(c))

    # The combined index omits the bulky `input` field per case to keep it
    # readable; the per-case files are the source of truth for runs.
    index = [{k: v for k, v in c.items() if k != "input"} for c in cases]
    INDEX_FILE.write_text(json.dumps(index, indent=2))

    print(f"wrote {len(cases)} cases to {OUT_DIR}")
    print(f"index: {INDEX_FILE}")

    # Summary
    from collections import Counter
    by_group_size = Counter((c["group"], c["size"]) for c in cases)
    for (g, s), n in sorted(by_group_size.items()):
        print(f"  {g:30s} {s:7s} {n}")


if __name__ == "__main__":
    main()
