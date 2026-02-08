#!/usr/bin/env bash
set -euo pipefail

INPUT_LENGTH=100
TIMEOUTS=(1 10 100)
LOG_FILE="timeout_matrix_run.log"

run_and_log() {
  local lang="$1"
  local timeout="$2"
  shift 2

  local start_epoch_ns
  local end_epoch_ns
  local elapsed_ms
  local status
  local started_at
  local ended_at

  started_at="$(date -Is)"
  start_epoch_ns="$(date +%s%N)"
  set +e
  "$@"
  status=$?
  set -e
  end_epoch_ns="$(date +%s%N)"
  ended_at="$(date -Is)"
  elapsed_ms=$(( (end_epoch_ns - start_epoch_ns) / 1000000 ))

  printf "%s | lang=%s timeout=%ss input_length=%s status=%s elapsed_ms=%s ended_at=%s\n" \
    "$started_at" "$lang" "$timeout" "$INPUT_LENGTH" "$status" "$elapsed_ms" "$ended_at" >> "$LOG_FILE"

  return "$status"
}

printf "\n=== Matrix run started at %s (input_length=%s) ===\n" "$(date -Is)" "$INPUT_LENGTH" >> "$LOG_FILE"

run_python() {
  local timeout="$1"
  uv run --project python python/main.py --timeout="${timeout}" --input-length="${INPUT_LENGTH}"
}

run_typescript() {
  local timeout="$1"
  bun run typescript/index.ts --timeout="${timeout}" --input-length="${INPUT_LENGTH}"
}

run_csharp() {
  local timeout="$1"
  dotnet run --project csharp/resh_test.csproj -- --timeout="${timeout}" --input-length="${INPUT_LENGTH}"
}

for timeout in "${TIMEOUTS[@]}"; do
  echo "=== Running timeout=${timeout}s ==="
  run_and_log "python" "${timeout}" run_python "${timeout}"
  run_and_log "typescript" "${timeout}" run_typescript "${timeout}"
  run_and_log "csharp" "${timeout}" run_csharp "${timeout}"
  echo "=== Completed timeout=${timeout}s ==="
  echo
done

echo "Expected output files:"
echo "  py_redos_test_results_timeout-1.json"
echo "  py_redos_test_results_timeout-10.json"
echo "  py_redos_test_results_timeout-100.json"
echo "  ts_redos_test_results_timeout-1.json"
echo "  ts_redos_test_results_timeout-10.json"
echo "  ts_redos_test_results_timeout-100.json"
echo "  csharp_redos_test_results_timeout-1.json"
echo "  csharp_redos_test_results_timeout-10.json"
echo "  csharp_redos_test_results_timeout-100.json"
