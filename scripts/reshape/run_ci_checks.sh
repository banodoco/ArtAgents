#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

# Self-sandbox: create hermetic temp home and projects root so concurrent/
# isolated CI invocations never touch the developer's real ASTRID_HOME or
# ASTRID_PROJECTS_ROOT.
ASTRID_HOME="$(mktemp -d)"
export ASTRID_HOME
ASTRID_PROJECTS_ROOT="$(mktemp -d)"
export ASTRID_PROJECTS_ROOT
# Pre-seed a default agent identity into the temp home so first-run
# bootstrap does not fire. ASTRID_HOME must be exported before the
# Python one-liner because identity_path() reads os.environ.
"$PYTHON_BIN" -c 'from astrid.core.session.identity import Identity, write_identity; write_identity(Identity(agent_id="ci", created_at="2026-01-01T00:00:00Z"))'
trap 'rm -rf "$ASTRID_HOME" "$ASTRID_PROJECTS_ROOT"' EXIT

# Generate the remotion TS types before tests: remotion/src/types.generated.ts
# is deliberately gitignored (generated artifact), but the schema-contract
# tests require it to exist on clean CI checkouts.
"$PYTHON_BIN" scripts/gen_remotion_types.py


# Argument parsing: recognise --json and --changed.
JSON_MODE=false
CHANGED_MODE=false
for _arg in "$@"; do
  case "$_arg" in
    --json) JSON_MODE=true ;;
    --changed) CHANGED_MODE=true ;;
  esac
done

# Coverage flags are omitted on the --changed fast path and may be disabled by
# CI lanes that need the full suite to fit within their job timeout. A plain
# local invocation keeps coverage by default (SD-004).
COV_ARGS="--cov=astrid --cov-report=term --cov-report=xml --cov-fail-under=72"
if $CHANGED_MODE || [ "${ASTRID_CI_SKIP_COVERAGE:-}" = "1" ]; then
  COV_ARGS=""
fi

TARGETED_BLOCKING_TESTS=(
  tests/spikes/test_env_inheritance.py
  tests/packs/test_composition_elements.py
  tests/test_for_each_autoclose.py
  tests/test_schema_contract.py
  tests/core/rendering
  tests/packs/rendering/test_builtin_registration.py
)

RENDERER_PARITY_TESTS=(
  tests/packs/test_renderer_parity.py
)

QUARANTINE_TESTS=(
  "tests/agentic/test_agent_probe_regression.py|author-test|builtin.agent_probe negative-revert coverage still depends on the legacy compiled author-test start path.|2026-06-11"
  "tests/orchestrate/test_author_test_drift.py|author-test|dynamic orchestrator author-test compile for video_editing.hype still fails before the diff behavior is exercised.|2026-06-11"
  "tests/orchestrate/test_author_test_pass.py|author-test|dynamic orchestrator author-test compile for video_editing.hype still fails before the golden replay can run.|2026-06-11"
  "tests/orchestrate/test_author_test_regenerate.py|author-test|dynamic orchestrator author-test compile for video_editing.hype still fails before the regenerate flow can run.|2026-06-11"
)

run_quarantine_lane() {
  local path="$1"
  local owner="$2"
  local reason="$3"
  local expiry="$4"

  echo "QUARANTINE owner=${owner} expiry=${expiry} path=${path}"
  echo "  reason: ${reason}"
  # Select by marker so the lane remains run-but-allowed-to-fail even if the
  # file gains non-opt_in tests in the future.
  if "$PYTHON_BIN" -m pytest "$path" -m opt_in -q; then
    echo "  status: pass"
  else
    echo "  status: fail (non-blocking)"
  fi
}

# SD-CI-LANES: three distinct mechanisms, kept separate.
#
# TARGETED_BLOCKING_TESTS  — by-path blocking pre-checks, including rendering contracts.
# RENDERER_PARITY_TESTS    — marked semantic parity suite, explicitly selected below.
# QUARANTINE_TESTS         — opt_in-marked, allowed-to-fail lane (below).
# BROAD_PYTEST_ARGS        — broad default run; opt_in/integration excluded by
#                            marker (-m "not integration and not opt_in and not live")
#                            so no --ignore= entries are needed for quarantine files,
#                            and R23 live/VLM gate tests can never be selected.
BROAD_PYTEST_ARGS=(
  --tb=no
  -q
  --no-header
  -m "not integration and not opt_in and not live"
)

# ============================================================================
# --changed fast lane: replaces the ENTIRE script execution.
# Skips baselines, docs, reshape, blocking, remotion, and quarantine lanes.
# Runs only the tests selected by the changed-file→test-path heuristic below.
# Target: <~90 s (the only way to hit that budget is by skipping everything
# except the selected tests).  Composes with --json.
#
# Heuristic limitations (best-effort, documented per plan requirement):
#   1. Merge-base detection depends on 'origin/main' or 'main' existing; if
#      neither is available we diff against HEAD~1.  This is a reasonable
#      default but misses changes in very young repos or detached-HEAD CI.
#   2. git diff --name-only splits on newlines — filenames containing
#      whitespace will be mis-parsed.  The repo convention is space-free.
#   3. The astrid/→tests/ mapping is pattern-based, not import-graph-based.
#      A changed astrid/ module whose test lives at a non-standard path (or
#      has no test at all) will be missed, and the overall selection may fall
#      back to TARGETED_BLOCKING_TESTS.
#   4. Deleted files are filtered out by [ -f ]; we do not attempt to select
#      the tests that used to cover them.
#   5. Directory selections (e.g. tests/session/) hand the entire directory
#      to pytest discovery, which is fast but may run more tests than
#      strictly necessary.
# ============================================================================
if $CHANGED_MODE; then
  # (a) Compute merge-base with 3-tier fallback.
  BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || echo "")
  if [ -z "$BASE" ]; then
    CHANGED_FILES=$(git diff --name-only HEAD~1..HEAD 2>/dev/null || echo "")
  else
    CHANGED_FILES=$(git diff --name-only "$BASE"...HEAD 2>/dev/null || echo "")
  fi

  # (b) Filter to existing files only (exclude deletions).
  # (c) Map each changed path to test paths via the ordered heuristic.
  SELECTED_TESTS=()

  for path in $CHANGED_FILES; do
    # Exclude deletions and files that vanished between diff and now.
    [ -f "$path" ] || continue

    if [[ "$path" == tests/* ]]; then
      # Rule 1: under tests/ → select directly.
      SELECTED_TESTS+=("$path")

    elif [[ "$path" == astrid/*.py && "$path" != astrid/*/*.py ]]; then
      # Rule 2: astrid/<mod>.py top-level → tests/test_<mod>.py if it
      # exists; else fall through (NEVER fall back to whole tests/).
      mod="${path#astrid/}"
      mod="${mod%.py}"
      test_file="tests/test_${mod}.py"
      if [ -f "$test_file" ]; then
        SELECTED_TESTS+=("$test_file")
      fi

    elif [[ "$path" == astrid/*/*.py ]]; then
      # Rule 3: nested astrid/<sub>/.../<mod>.py
      mod="${path##*/}"
      mod="${mod%.py}"

      # 3a. Try tests/test_<mod>.py directly.
      test_file="tests/test_${mod}.py"
      if [ -f "$test_file" ]; then
        SELECTED_TESTS+=("$test_file")
        continue
      fi

      # 3b. Walk the full mirrored directory path.
      #     astrid/core/session/foo.py → dir_part=core/session → tests/core/session/
      dir_part="${path#astrid/}"
      dir_part="${dir_part%/*}"
      if [ -d "tests/${dir_part}" ]; then
        SELECTED_TESTS+=("tests/${dir_part}/")
        continue
      fi

      # 3c. Drop leading components one at a time; select the first existing
      #     directory.  e.g. astrid/core/session/foo.py → try tests/session/
      IFS='/' read -ra COMPONENTS <<< "$dir_part"
      for ((i=1; i<${#COMPONENTS[@]}; i++)); do
        partial=""
        for ((j=i; j<${#COMPONENTS[@]}; j++)); do
          if [ -z "$partial" ]; then
            partial="${COMPONENTS[$j]}"
          else
            partial="${partial}/${COMPONENTS[$j]}"
          fi
        done
        if [ -d "tests/${partial}" ]; then
          SELECTED_TESTS+=("tests/${partial}/")
          break
        fi
      done
      # If nothing matched, fall through — this path contributes nothing
      # and the global empty-check below catches it.
    fi
  done

  # (d) De-duplicate selections.
  if [ ${#SELECTED_TESTS[@]} -gt 0 ]; then
    SELECTED_TESTS=($(printf '%s\n' "${SELECTED_TESTS[@]}" | sort -u))
  fi

  # (e) Fall back to TARGETED_BLOCKING_TESTS if selection is empty.
  if [ ${#SELECTED_TESTS[@]} -eq 0 ]; then
    SELECTED_TESTS=("${TARGETED_BLOCKING_TESTS[@]}")
    echo "--- changed: no files matched → falling back to TARGETED_BLOCKING_TESTS ---" >&2
  fi

  # (f) Run selection with -q and NO --cov.
  # (g) Compose cleanly with --json.
  if $JSON_MODE; then
    _JSON_TMPDIR="$(mktemp -d)"
    trap 'rm -rf "$ASTRID_HOME" "$ASTRID_PROJECTS_ROOT" "$_JSON_TMPDIR"' EXIT
    _xml="$_JSON_TMPDIR/junit_changed.xml"
    _rc=0
    echo "--- changed (fast lane) ---" >&2
    "$PYTHON_BIN" -m pytest "${SELECTED_TESTS[@]}" -q --junit-xml="$_xml" >&2 2>&1 || _rc=$?

    # Parse junit XML (SD1: passed = tests - failures - errors - skipped).
    _counts=$("$PYTHON_BIN" -c "
import xml.etree.ElementTree as ET, sys
tree = ET.parse('$_xml')
root = tree.getroot()
suite = root if root.tag == 'testsuite' else root.find('testsuite')
if suite is None:
    print('0 0 0'); sys.exit(0)
t = int(suite.get('tests', 0))
f = int(suite.get('failures', 0))
e = int(suite.get('errors', 0))
s = int(suite.get('skipped', 0))
print(t - f - e - s, f + e, s)
")
    read -r _p _f _s <<< "$_counts"

    if [ "$_rc" -eq 0 ]; then
      _status="pass"
      _ok="true"
    else
      _status="fail"
      _ok="false"
    fi

    # Emit exactly one JSON object on stdout (SD-002).
    printf '{"lanes":{"changed":{"passed":%d,"failed":%d,"skipped":%d,"status":"%s"}},"ok":%s,"exit":%d}\n' \
      "$_p" "$_f" "$_s" "$_status" "$_ok" "$_rc"

    exit "$_rc"
  else
    echo "--- changed (fast lane) ---"
    echo "Selected tests: ${SELECTED_TESTS[*]}"
    "$PYTHON_BIN" -m pytest "${SELECTED_TESTS[@]}" -q
    exit $?
  fi
fi

if ! $JSON_MODE; then
  # Default mode: keep current human stdout behaviour unchanged.
  "$PYTHON_BIN" scripts/reshape/compare_ruff_baseline.py
  "$PYTHON_BIN" scripts/reshape/compare_mypy_baseline.py
  "$PYTHON_BIN" scripts/reshape/check_repo_hygiene.py
  bash tests/verify_docs_commands.sh

  "$PYTHON_BIN" -m pytest tests/reshape -q
  "$PYTHON_BIN" -m pytest tests/reshape/test_hype_regression_fixture.py -q
  "$PYTHON_BIN" -m pytest tests/concurrency/test_two_tab_harness_smoke.py -q
  "$PYTHON_BIN" -m pytest "${TARGETED_BLOCKING_TESTS[@]}" -q
  "$PYTHON_BIN" -m pytest -q -m renderer_parity "${RENDERER_PARITY_TESTS[@]}"
  "$PYTHON_BIN" -m pytest "${BROAD_PYTEST_ARGS[@]}" $COV_ARGS

  # Named Remotion typecheck lane.
  if [ ! -d remotion/node_modules ]; then
    echo "LANE remotion-typecheck: SKIP (remotion/node_modules absent; run 'cd remotion && npm ci' to enable)"
  elif [ ! -f remotion/src/types.augmentations.d.ts ]; then
    echo "LANE remotion-typecheck: SKIP (remotion/src/types.augmentations.d.ts absent; generated augmentation surface not provisioned)"
  else
    echo "LANE remotion-typecheck: running (remotion/node_modules + generated surface present)"
    (cd remotion && npm run typecheck)
  fi

  for entry in "${QUARANTINE_TESTS[@]}"; do
    IFS='|' read -r path owner reason expiry <<<"$entry"
    run_quarantine_lane "$path" "$owner" "$reason" "$expiry"
  done
  exit 0
fi

# ---------------------------------------------------------------------------
# --json mode: emit exactly one JSON object on stdout; all human text → stderr
# ---------------------------------------------------------------------------

_JSON_TMPDIR="$(mktemp -d)"
trap 'rm -rf "$ASTRID_HOME" "$ASTRID_PROJECTS_ROOT" "$_JSON_TMPDIR"' EXIT

# Per-lane accumulators. Encoded as individual variables (_LP_<lane>, etc.)
# to stay compatible with bash 3.2 (macOS default).
_LP_baselines=0; _LF_baselines=0; _LS_baselines=0
_LP_docs=0;      _LF_docs=0;      _LS_docs=0
_LP_reshape=0;   _LF_reshape=0;   _LS_reshape=0
_LP_blocking=0;  _LF_blocking=0;  _LS_blocking=0
_LP_broad=0;     _LF_broad=0;     _LS_broad=0
_LP_remotion_typecheck=0; _LF_remotion_typecheck=0; _LS_remotion_typecheck=0
_LP_quarantine=0; _LF_quarantine=0; _LS_quarantine=0
_OVERALL_EXIT=0

_accum() {
  local _lane="$1" _p="$2" _f="$3" _s="$4"
  eval "_LP_${_lane}=\$((_LP_${_lane} + _p))"
  eval "_LF_${_lane}=\$((_LF_${_lane} + _f))"
  eval "_LS_${_lane}=\$((_LS_${_lane} + _s))"
}

# Parse a junit XML file; print "<passed> <failed> <skipped>" to stdout.
_parse_junit() {
  "$PYTHON_BIN" -c "
import xml.etree.ElementTree as ET, sys
tree = ET.parse(sys.argv[1])
root = tree.getroot()
suite = root if root.tag == 'testsuite' else root.find('testsuite')
if suite is None:
    print('0 0 0'); sys.exit(0)
t = int(suite.get('tests', 0))
f = int(suite.get('failures', 0))
e = int(suite.get('errors', 0))
s = int(suite.get('skipped', 0))
print(t - f - e - s, f + e, s)
" "$1"
}

# Run a pytest invocation, capture junit XML counts, accumulate into lane.
# Both stdout and stderr of pytest are rerouted to stderr (SD-002).
_run_pytest() {
  local _lane="$1"; shift
  local _xml="$_JSON_TMPDIR/junit_$$.xml"
  local _rc=0
  "$PYTHON_BIN" -m pytest "$@" --junit-xml="$_xml" >&2 2>&1 || _rc=$?
  local _p _f _s
  if [ -f "$_xml" ]; then
    read -r _p _f _s < <(_parse_junit "$_xml")
    rm -f "$_xml"
  else
    if [ "$_rc" -eq 0 ]; then _p=1; _f=0; _s=0; else _p=0; _f=1; _s=0; fi
  fi
  _accum "$_lane" "$_p" "$_f" "$_s"
  [ "$_rc" -eq 0 ] || _OVERALL_EXIT=1
}

# Run a non-pytest command; use exit code 0→pass, non-zero→fail.
# stdout and stderr are both rerouted to stderr (SD-002).
_run_plain() {
  local _lane="$1"; shift
  local _rc=0
  "$@" >&2 2>&1 || _rc=$?
  if [ "$_rc" -eq 0 ]; then _accum "$_lane" 1 0 0; else _accum "$_lane" 0 1 0; fi
  [ "$_rc" -eq 0 ] || _OVERALL_EXIT=1
}

echo "--- baselines ---" >&2
_run_plain baselines "$PYTHON_BIN" scripts/reshape/compare_ruff_baseline.py
_run_plain baselines "$PYTHON_BIN" scripts/reshape/compare_mypy_baseline.py
_run_plain baselines "$PYTHON_BIN" scripts/reshape/check_repo_hygiene.py

echo "--- docs ---" >&2
_run_plain docs bash tests/verify_docs_commands.sh

echo "--- reshape ---" >&2
_run_pytest reshape tests/reshape -q
_run_pytest reshape tests/reshape/test_hype_regression_fixture.py -q
_run_pytest reshape tests/concurrency/test_two_tab_harness_smoke.py -q

echo "--- blocking ---" >&2
_run_pytest blocking "${TARGETED_BLOCKING_TESTS[@]}" -q
_run_pytest blocking -q -m renderer_parity "${RENDERER_PARITY_TESTS[@]}"

echo "--- broad ---" >&2
if [ "${ASTRID_CI_SKIP_BROAD:-}" = "1" ]; then
  echo "LANE broad: SKIP (ASTRID_CI_SKIP_BROAD=1)" >&2
  _accum broad 0 0 1
else
  _run_pytest broad "${BROAD_PYTEST_ARGS[@]}" $COV_ARGS
fi

echo "--- remotion_typecheck ---" >&2
if [ ! -d remotion/node_modules ]; then
  echo "LANE remotion-typecheck: SKIP (remotion/node_modules absent; run 'cd remotion && npm ci' to enable)" >&2
  _accum remotion_typecheck 0 0 1
elif [ ! -f remotion/src/types.augmentations.d.ts ]; then
  echo "LANE remotion-typecheck: SKIP (remotion/src/types.augmentations.d.ts absent; generated augmentation surface not provisioned)" >&2
  _accum remotion_typecheck 0 0 1
else
  echo "LANE remotion-typecheck: running (remotion/node_modules + generated surface present)" >&2
  _rc=0
  # SD-003: capture stdout of this stdout-leaking lane, reroute to stderr.
  { (cd remotion && npm run typecheck); } >&2 2>&1 || _rc=$?
  if [ "$_rc" -eq 0 ]; then _accum remotion_typecheck 1 0 0; else _accum remotion_typecheck 0 1 0; fi
  [ "$_rc" -eq 0 ] || _OVERALL_EXIT=1
fi

echo "--- quarantine ---" >&2
# SD-003: capture stdout of run_quarantine_lane, reroute to stderr.
# Quarantine is non-blocking; the loop always exits 0.
for entry in "${QUARANTINE_TESTS[@]}"; do
  IFS='|' read -r path owner reason expiry <<<"$entry"
  run_quarantine_lane "$path" "$owner" "$reason" "$expiry" >&2 2>&1 || true
done
# Non-blocking: report as pass regardless of individual test outcomes.
_accum quarantine 1 0 0

# Determine per-lane status and emit JSON.
_lane_json() {
  local _lane="$1"
  local _p _f _s
  eval "_p=\$_LP_${_lane}"
  eval "_f=\$_LF_${_lane}"
  eval "_s=\$_LS_${_lane}"
  local _status
  if [ "$_f" -gt 0 ]; then
    _status="fail"
  elif [ "$_p" -eq 0 ] && [ "$_s" -gt 0 ]; then
    _status="skip"
  else
    _status="pass"
  fi
  printf '"%s":{"passed":%d,"failed":%d,"skipped":%d,"status":"%s"}' \
    "$_lane" "$_p" "$_f" "$_s" "$_status"
}

_OK_STR="true"
[ "$_OVERALL_EXIT" -eq 0 ] || _OK_STR="false"

printf '{"lanes":{%s,%s,%s,%s,%s,%s,%s},"ok":%s,"exit":%d}\n' \
  "$(_lane_json baselines)" \
  "$(_lane_json docs)" \
  "$(_lane_json reshape)" \
  "$(_lane_json blocking)" \
  "$(_lane_json broad)" \
  "$(_lane_json remotion_typecheck)" \
  "$(_lane_json quarantine)" \
  "$_OK_STR" \
  "$_OVERALL_EXIT"

exit "$_OVERALL_EXIT"
