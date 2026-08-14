#!/usr/bin/env bash
# ci-suites.sh — run every deterministic self-check suite the port ships.
# Usage: scripts/ci-suites.sh [python]   (default python3; CI passes a venv python
# with jsonschema installed, which closes the one jsonschema-gated fixture check)
set -u

PY="${1:-python3}"
# Absolutize the interpreter: each suite runs from its own directory, so a
# relative path (e.g. a venv python) would break after the first cd.
case "$PY" in
  */*) PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")" ;;
  *)   command -v "$PY" >/dev/null || { echo "error: interpreter not found: $PY" >&2; exit 2; } ;;
esac
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0
TOTAL=0

run_suite() {
  local skill="$1"; shift
  for t in "$@"; do
    TOTAL=$((TOTAL + 1))
    local dir="$HERE/preset/skills/$skill/infra/test"
    local out
    # Each suite runs from its OWN directory: the link-integrity checkers resolve
    # doc links against the project root by convention (upstream: the plugin root).
    if ! out=$(cd "$dir" && "$PY" "$t" 2>&1); then
      FAIL=$((FAIL + 1))
      echo "FAIL: $skill/$t"
      echo "$out" | tail -6 | sed 's/^/      /'
    else
      echo "PASS: $skill/$t"
    fi
  done
}

run_suite parallel-development \
  disconnect_check.py plugin_layout.py run_record.py run_record_schema.py \
  violation_log_schema.py adapter_shape_check.py arm_copy_config.py \
  arm_report_gates.py arm_revert.py hetero_review_wiring.py plan_queue_detect.py \
  plan_queue_loop_state_wiring.py scope_check.py smoke_gates.py drift_check.py

run_suite blueprint-crafting \
  plan_model_schema.py run_record_schema.py run_record.py produce_goldens.py \
  constraints_check_goldens.py freeze_goldens.py normalizer_goldens.py \
  end_to_end.py round_trip.py plan_reviewer_precision.py trigger_check.py \
  disconnect_check.py

run_suite cross-source-review \
  convergence_policy_check.py findings_shape_check.py disconnect_check.py \
  plugin_layout.py dogfood.py

run_suite primary-source-verification \
  coverage_policy_check.py fetched_quote_gate.py findings_shape_check.py \
  disconnect_check.py plugin_layout.py dogfood.py

run_suite prior-art-search \
  coverage_policy_check.py fetched_quote_gate.py findings_shape_check.py \
  disconnect_check.py plugin_layout.py dogfood.py

# the csr fixture verify (standalone script, not in infra/test/)
TOTAL=$((TOTAL + 1))
if ! out=$("$PY" "$HERE/preset/skills/cross-source-review/infra/scripts/converge_fixtures/verify.py" 2>&1); then
  FAIL=$((FAIL + 1)); echo "FAIL: cross-source-review/converge_fixtures/verify.py"
  echo "$out" | tail -6 | sed 's/^/      /'
else
  echo "PASS: cross-source-review/converge_fixtures/verify.py"
fi

echo
echo "suites: $TOTAL run, $FAIL failed"
[ "$FAIL" -eq 0 ]
