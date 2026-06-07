#!/usr/bin/env bash
# Run all four engine runners over experiment-dataset sequentially, then
# aggregate. Sequential (not parallel) because each runner stresses CPU and
# spawn-heavy stages can exhaust resources when stacked.
#
# Env overrides:
#   RUNS=1         iterations per case (default 1)
#   TIMEOUT=2      per-case timeout in seconds (default 2)
#   DATASET=...    path to per-case JSON dir (default experiment-dataset)
#   SKIP=rust,ts   comma-separated engines to skip (rust|python|ts|csharp)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUNS="${RUNS:-1}"
TIMEOUT="${TIMEOUT:-2}"
DATASET="${DATASET:-experiment-dataset}"
SKIP="${SKIP:-}"

skip() { [[ ",$SKIP," == *",$1,"* ]]; }
log()  { printf '\n=== %s ===\n' "$*"; }
fmt_t() { local s=$1; printf '%dm %ds' $((s/60)) $((s%60)); }

run_step() {
    local label="$1"; shift
    log "$label"
    local start=$SECONDS
    if "$@"; then
        log "$label done in $(fmt_t $((SECONDS - start)))"
    else
        local rc=$?
        log "$label FAILED (exit $rc) after $(fmt_t $((SECONDS - start)))"
        return $rc
    fi
}

[[ -d "$DATASET" ]] || { echo "dataset dir not found: $DATASET"; exit 1; }

# ---------- 1. Rust ----------
if ! skip rust; then
    run_step "Rust build (release)" \
        bash -c "cd rust && cargo build --release"
    run_step "Rust runner" \
        rust/target/release/rust --dataset "$DATASET" --runs "$RUNS"
fi

# ---------- 2. Python ----------
if ! skip python; then
    run_step "Python runner" \
        uv run --project python python/main.py \
            --dataset "$DATASET" --runs "$RUNS" --timeout "$TIMEOUT"
fi

# ---------- 3. TypeScript ----------
# Node, not Bun: Bun crashes when spawning 3000+ short-lived workers in a row.
if ! skip ts; then
    run_step "TypeScript runner" \
        bash -c "cd typescript && node --experimental-strip-types index.ts \
            --dataset=../$DATASET --runs=$RUNS --timeout=$TIMEOUT"
fi

# ---------- 4. C# ----------
if ! skip csharp; then
    run_step "C# build (release)" \
        bash -c "cd csharp && dotnet build -c Release --nologo -v q"
    # Project files name the assembly `resh_test`; locate it under Release.
    csharp_bin="$(find csharp/bin/Release -name 'resh_test' -type f -executable 2>/dev/null | head -1)"
    if [[ -z "$csharp_bin" ]]; then
        # Fall back to dotnet-launching the DLL if the native-AOT binary isn't there.
        csharp_dll="$(find csharp/bin/Release -name 'resh_test.dll' 2>/dev/null | head -1)"
        if [[ -n "$csharp_dll" ]]; then
            run_step "C# runner" \
                dotnet "$csharp_dll" \
                    --dataset="$DATASET" --runs="$RUNS" --timeout="$TIMEOUT"
        else
            log "C# binary not found under csharp/bin/Release — skipping"
        fi
    else
        run_step "C# runner" \
            "$csharp_bin" --dataset="$DATASET" --runs="$RUNS" --timeout="$TIMEOUT"
    fi
fi

# ---------- 5. Aggregate ----------
run_step "Aggregate + plot" \
    uv run --project python python misc-scripts/aggregate_results.py

log "All done"
