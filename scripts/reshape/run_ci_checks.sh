#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

TARGETED_BLOCKING_TESTS=(
  tests/spikes/test_env_inheritance.py
  tests/test_composition_elements.py
  tests/test_for_each_autoclose.py
  tests/test_schema_contract.py
)

QUARANTINE_TESTS=(
  "tests/test_agent_probe_regression.py|author-test|builtin.agent_probe negative-revert coverage still depends on the legacy compiled author-test start path.|2026-06-11"
  "tests/test_author_test_drift.py|author-test|dynamic orchestrator author-test compile for video_editing.hype still fails before the diff behavior is exercised.|2026-06-11"
  "tests/test_author_test_pass.py|author-test|dynamic orchestrator author-test compile for video_editing.hype still fails before the golden replay can run.|2026-06-11"
  "tests/test_author_test_regenerate.py|author-test|dynamic orchestrator author-test compile for video_editing.hype still fails before the regenerate flow can run.|2026-06-11"
)

run_quarantine_lane() {
  local path="$1"
  local owner="$2"
  local reason="$3"
  local expiry="$4"

  echo "QUARANTINE owner=${owner} expiry=${expiry} path=${path}"
  echo "  reason: ${reason}"
  if "$PYTHON_BIN" -m pytest "$path" -q; then
    echo "  status: pass"
  else
    echo "  status: fail (non-blocking)"
  fi
}

BROAD_PYTEST_ARGS=(
  --tb=no
  -q
  --no-header
  -m "not integration and not opt_in"
  --ignore=tests/test_agent_probe_regression.py
  --ignore=tests/test_author_test_drift.py
  --ignore=tests/test_author_test_pass.py
  --ignore=tests/test_author_test_regenerate.py
)

"$PYTHON_BIN" scripts/reshape/compare_ruff_baseline.py
"$PYTHON_BIN" scripts/reshape/compare_mypy_baseline.py
"$PYTHON_BIN" scripts/reshape/check_repo_hygiene.py
bash tests/verify_docs_commands.sh

"$PYTHON_BIN" -m pytest tests/reshape -q
"$PYTHON_BIN" -m pytest tests/reshape/test_hype_regression_fixture.py -q
"$PYTHON_BIN" -m pytest tests/concurrency/test_two_tab_harness_smoke.py -q
"$PYTHON_BIN" -m pytest "${TARGETED_BLOCKING_TESTS[@]}" -q
"$PYTHON_BIN" -m pytest "${BROAD_PYTEST_ARGS[@]}" --cov=astrid --cov-report=term --cov-report=xml --cov-fail-under=0

# Named Remotion typecheck lane. Blocking when the Remotion toolchain is present
# (mirrors the GitHub CI `npm run typecheck` lane); on a checkout without
# remotion/node_modules it documents the skip rather than failing, since the
# dependency provisioning is environmental, not a repo defect.
if [ -d remotion/node_modules ]; then
  echo "LANE remotion-typecheck: running (remotion/node_modules present)"
  (cd remotion && npm run typecheck)
else
  echo "LANE remotion-typecheck: SKIP (remotion/node_modules absent; run 'cd remotion && npm ci' to enable)"
fi

for entry in "${QUARANTINE_TESTS[@]}"; do
  IFS='|' read -r path owner reason expiry <<<"$entry"
  run_quarantine_lane "$path" "$owner" "$reason" "$expiry"
done
