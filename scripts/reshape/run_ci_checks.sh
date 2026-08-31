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
  tests/stage1/test_zero_shim_execution_pack_deletion.py
  tests/core/test_orchestrator_runner_errors.py::test_command_orchestrator_preserves_declared_passthrough_env
  tests/core/test_orchestrator_runner_errors.py::test_command_orchestrator_does_not_spread_undeclared_host_env
  tests/packs/test_composition_elements.py
  tests/test_schema_contract.py
  tests/core/rendering
  tests/packs/rendering/test_builtin_registration.py
)

RENDERER_PARITY_TESTS=(
  tests/packs/test_renderer_parity.py
)

_validate_lane_manifest() {
  local _path _file_path
  for _path in "${TARGETED_BLOCKING_TESTS[@]}" "${RENDERER_PARITY_TESTS[@]}"; do
    _file_path="${_path%%::*}"
    if [ ! -e "$_file_path" ]; then
      echo "CI lane manifest references missing path: $_path" >&2
      return 4
    fi
  done
}

_validate_lane_manifest

QUARANTINE_TESTS=(
)

run_quarantine_lane() {
  local path="$1"
  local owner="$2"
  local reason="$3"
  local expiry="$4"

  echo "QUARANTINE owner=${owner} expiry=${expiry} path=${path}"
  echo "  reason: ${reason}"
  if [ ! -f "$path" ]; then
    echo "  status: invalid (test path does not exist)"
    return 2
  fi
  if [[ ! "$expiry" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "  status: invalid (expiry must be YYYY-MM-DD)"
    return 2
  fi
  if [[ "$expiry" < "$(date -u +%F)" ]]; then
    echo "  status: invalid (quarantine expired)"
    return 2
  fi
  # Select by marker so the lane remains run-but-allowed-to-fail even if the
  # file gains non-opt_in tests in the future.
  if "$PYTHON_BIN" -m pytest "$path" -m opt_in -q; then
    echo "  status: pass"
    return 0
  else
    echo "  status: fail (non-blocking)"
    return 1
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
#                            grok_iter is ALSO excluded explicitly: the grok-driven
#                            UX iteration loop invokes the grok CLI and can mutate
#                            sources, so it must never run in default CI even if
#                            its opt_in marker is ever dropped.
BROAD_PYTEST_ARGS=(
  --tb=short
  -q
  --no-header
  -m "not integration and not opt_in and not live and not grok_iter"
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
      # Rule 1: select Python tests directly. Non-Python files under tests/
      # are fixtures or data and must never be handed to pytest as targets.
      # Keep explicit ownership mappings for fixtures whose owning test is
      # part of the changed-file fast lane.
      if [[ "$path" == *.py ]]; then
        SELECTED_TESTS+=("$path")
      else
        case "$path" in
          tests/fixtures/remotion-local-font-probe.json)
            if [ -f tests/test_remotion_local_fonts.py ]; then
              SELECTED_TESTS+=(tests/test_remotion_local_fonts.py)
            fi
            ;;
        esac
      fi

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
    echo "Selected tests: ${SELECTED_TESTS[*]}" >&2
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
  PYTHON_BIN="$PYTHON_BIN" bash tests/verify_docs_commands.sh

  "$PYTHON_BIN" -m pytest tests/reshape -q
  "$PYTHON_BIN" -m pytest tests/reshape/test_hype_regression_fixture.py -q
  "$PYTHON_BIN" -m pytest "${TARGETED_BLOCKING_TESTS[@]}" -q
  # Provision and validate the authoritative npm closure before the parity
  # lane; subsequent gate calls reuse the cryptographically checked closure.
  "$PYTHON_BIN" scripts/reshape/remotion_gate.py install
  "$PYTHON_BIN" scripts/reshape/remotion_gate.py parity --reuse-installed
  "$PYTHON_BIN" -m pytest "${BROAD_PYTEST_ARGS[@]}" $COV_ARGS

  # m1 S1 gate (plan step 23): the twelve focused m1 lanes via the SAME make
  # target GitHub Actions runs, so the local mirror and CI stay in lockstep.
  # Summary + per-lane logs are retained in out/s1-gate/latest on pass AND
  # failure (CI uploads them with `if: always()`). ASTRID_CI_SKIP_GATE=1 opts
  # out — GitHub Actions runs the gate in its own dedicated step, so the
  # mirror lane does not re-run it there.
  if [ "${ASTRID_CI_SKIP_GATE:-}" = "1" ]; then
    echo "LANE s1-gate: SKIP (ASTRID_CI_SKIP_GATE=1)"
  else
    echo "LANE s1-gate: running (make s1-gate; 12 focused lanes, evidence in out/s1-gate/latest)"
    make s1-gate PY="$PYTHON_BIN"
  fi

  # Named Remotion typecheck lane. The gate provisions the exact lockfile
  # closure when needed and exports the validated absolute Node executable.
  echo "LANE remotion-typecheck: running (pinned Node/npm + npm ci + generated types)"
  "$PYTHON_BIN" scripts/reshape/remotion_gate.py typecheck --reuse-installed

  for entry in ${QUARANTINE_TESTS[@]+"${QUARANTINE_TESTS[@]}"}; do
    IFS='|' read -r path owner reason expiry <<<"$entry"
    _quarantine_rc=0
    run_quarantine_lane "$path" "$owner" "$reason" "$expiry" || _quarantine_rc=$?
    if [ "$_quarantine_rc" -eq 2 ]; then
      echo "ERROR: invalid quarantine metadata must be fixed before CI can pass" >&2
      exit 1
    fi
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
  local _p_var="_LP_${_lane}" _f_var="_LF_${_lane}" _s_var="_LS_${_lane}"
  local _current_p=0 _current_f=0 _current_s=0
  eval "_current_p=\${${_p_var}:-0}"
  eval "_current_f=\${${_f_var}:-0}"
  eval "_current_s=\${${_s_var}:-0}"
  eval "${_p_var}=\$((_current_p + _p))"
  eval "${_f_var}=\$((_current_f + _f))"
  eval "${_s_var}=\$((_current_s + _s))"
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
_run_plain docs env "PYTHON_BIN=$PYTHON_BIN" bash tests/verify_docs_commands.sh

echo "--- reshape ---" >&2
_run_pytest reshape tests/reshape -q
_run_pytest reshape tests/reshape/test_hype_regression_fixture.py -q
echo "--- blocking ---" >&2
_run_pytest blocking "${TARGETED_BLOCKING_TESTS[@]}" -q
_run_plain blocking "$PYTHON_BIN" scripts/reshape/remotion_gate.py install
_run_plain blocking "$PYTHON_BIN" scripts/reshape/remotion_gate.py parity --reuse-installed

echo "--- broad ---" >&2
if [ "${ASTRID_CI_SKIP_BROAD:-}" = "1" ]; then
  echo "LANE broad: SKIP (ASTRID_CI_SKIP_BROAD=1)" >&2
  _accum broad 0 0 1
else
  _run_pytest broad "${BROAD_PYTEST_ARGS[@]}" $COV_ARGS
fi

echo "--- remotion_typecheck ---" >&2
echo "LANE remotion-typecheck: running (pinned Node/npm + npm ci + generated types)" >&2
_rc=0
{ "$PYTHON_BIN" scripts/reshape/remotion_gate.py typecheck --reuse-installed; } >&2 2>&1 || _rc=$?
if [ "$_rc" -eq 0 ]; then _accum remotion_typecheck 1 0 0; else _accum remotion_typecheck 0 1 0; fi
[ "$_rc" -eq 0 ] || _OVERALL_EXIT=1

echo "--- quarantine ---" >&2
# SD-003: capture stdout of run_quarantine_lane, reroute to stderr.
# Test failures remain non-blocking until their declared expiry. Missing test
# paths, malformed dates, and expired entries are stale CI configuration and
# therefore fail the gate.
for entry in ${QUARANTINE_TESTS[@]+"${QUARANTINE_TESTS[@]}"}; do
  IFS='|' read -r path owner reason expiry <<<"$entry"
  _rc=0
  run_quarantine_lane "$path" "$owner" "$reason" "$expiry" >&2 2>&1 || _rc=$?
  if [ "$_rc" -eq 0 ]; then
    _accum quarantine 1 0 0
  else
    _accum quarantine 0 1 0
    [ "$_rc" -eq 2 ] && _OVERALL_EXIT=1
  fi
done
if [ -z "${QUARANTINE_TESTS[0]+set}" ]; then
  echo "LANE quarantine: SKIP (no quarantined tests)" >&2
  _accum quarantine 0 0 1
fi

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
