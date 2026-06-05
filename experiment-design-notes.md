# Experimental regex dataset — design notes

## What was produced

`experiment-dataset/` — 1017 JSON files, one per regex/input case, plus
`experiment-dataset-index.json` (combined metadata, omits the bulky `input`
field per case to stay readable).

Per-case schema:

```json
{
  "id": 1,
  "regex": "...",
  "input": "...",
  "regex_size": 7,
  "input_size": 10000,
  "ast_size": 6,
  "ast_depth": 5,
  "group": "known_bad | generated_low_complexity | generated_high_complexity",
  "size":  "small | medium | large"
}
```

Plus group-specific extras:

- `known_bad`: `source_id`, `description` (carried from `test_cases.json`).
- generated groups: `freak_ast_size`, `freak_ast_depth` (the metrics
  reported by freak at generation time, in its own grammar).
- `generated_high_complexity`: `freak_gen_depth` (3 / 5 / 7).

## How to regenerate

```sh
cd freak && dune build bin/generate.exe
cd ..
python3 misc-scripts/build_dataset.py
```

The freak generator is a new binary (`freak/bin/generate.ml`) that uses only
the `freak` library (grammar + ascii). It does not depend on `eio_main` or
`base64`, so it builds without needing the full fuzzer toolchain (Rust, Go).

CLI:

```
generate --mode {low|high} --count N [--depth D] [--target-chars N] [--seed N]
```

The orchestrator (`misc-scripts/build_dataset.py`) drives the generator,
loads the 113 known-bad regexes from `test_cases.json`, and emits the full
1017-case dataset.

## Group composition

| Group | Source | Size knob |
| --- | --- | --- |
| A `known_bad` | 113 hand-curated ReDoS regexes from `test_cases.json` | Concat repetitions of the regex core |
| B `generated_low_complexity` | freak `--mode low` (shallow AST, long `a` literals) | `--target-chars` ≈ 15 / 60 / 150 |
| C `generated_high_complexity` | freak `--mode high` (full grammar) | `--depth` 3 / 5 / 7 |

For Group A, leading `^` and trailing `$` are stripped before repetition and
re-applied after; the repeated regex still matches the same single-character
input the original did (repetition of a matcher of `c+` still matches
`ccc…`).

Group C `--depth` is the freak grammar generation depth, *not* the Python
parser depth. Because the freak grammar emits Empty/CharSet leaves at depth
0, the realized AST depth (parsed by Python) is sometimes smaller than the
generator depth — that's expected. The `freak_gen_depth` field records the
generator input for traceability.

## Measurement of `ast_size` and `ast_depth`

Computed in Python via `re._parser.parse()` on the *realized* regex string,
uniformly across all three groups. This means:

- Group A (real-world ReDoS regexes) and Groups B/C (freak-generated) get a
  comparable metric.
- A regex that the Python parser rejects gets `ast_size = -1` and
  `ast_depth = -1`. The orchestrator currently rejects unparseable Group C
  candidates and resamples; in practice all 1017 cases parse.

For Groups B/C we additionally record `freak_ast_size` / `freak_ast_depth`
— freak's own counts on its internal AST — for cross-checking.

## Input strings

- Fixed length 10,000 characters per case (`INPUT_SIZE` in the orchestrator).
- A long run of a single character: the original `repeat` char from
  `test_cases.json` for Group A, and `a` for Groups B and C (matches the
  `a`-literal patterns in Group B; Group C inputs are not required to match).

The "size" dimension varies the **regex**, not the input. The user's
follow-on experiment idea (inputs up to 10⁸ chars) is intentionally out of
scope for the 1017-case dataset and can be a separate sweep.

## Decisions, with rationale

1. **113 per group** — matches the count of known-bad regexes, so all three
   groups are balanced. 113 × 3 groups × 3 sizes = 1017.
2. **Three groups** — known-bad covers real ReDoS reports; low-complexity
   isolates "simple structure, long literal" patterns; high-complexity
   isolates structural complexity at fixed-ish literal length.
3. **Three sizes** — gives a curve, not just a point, for how runtime scales
   with the size knob. ~150 regex chars is the large target for Groups A
   and B; Group C uses AST depth as the knob instead.
4. **Per-language timers** — keep all timing inside the language runtime to
   exclude process-startup overhead. Each language harness must time only
   the match call, not the wrapping process.
5. **No compile-time measurement (yet)** — focus on execution behavior;
   compile-time can be layered on without changing the dataset.
6. **Repeated patterns are designed to match** — concatenating a matcher of
   one character still matches that character; this keeps Groups A and B
   in the "match" regime rather than mixing in failure behavior. Group C is
   random and may or may not match — that's acceptable since the goal there
   is to exercise structural variety.
7. **Engines targeted next** — TypeScript, Python, C#, Rust runners under
   `typescript/`, `python/`, `csharp/`, `rust/` consume per-case JSON. Each
   runner should report runtime per case and, where possible, peak RSS.

## Known caveats

- A handful of high-complexity regexes use constructs (e.g. unusual
  character classes from random ASCII literals) that some engines may
  reject. The dataset filters to only Python-parseable patterns, but
  language-by-language compile failures should still be expected and
  recorded rather than fatal.
- The freak generator uses `Random.self_init ()` only when no `--seed` is
  passed. The orchestrator passes deterministic seeds, so dataset
  regeneration is reproducible.
