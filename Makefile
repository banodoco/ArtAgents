# Astrid local gate — run before pushing to catch CI/deploy failures locally.
#
#   make check   blocking pre-deploy gates, including renderer parity + Remotion typecheck
#   make ci      full mirror of the CI deploy job (adds wheel-install + pytest+coverage) — minutes
#
# `make check` green ≈ the CI "Python quality gates" deploy job will pass its fast gates.
# These run the SAME scripts CI runs (see .github/workflows/ci.yml), so they stay in lockstep.

PY ?= python3

.PHONY: help check ci structure doctor ruff mypy cycles remotion-typecheck renderer-parity wheel ci-mirror editable s1-gate m4-baseline m4-gate m7-gate m8-gate

help:
	@echo "make check   - blocking gates: structure, doctor, ruff, mypy, cycles, Remotion, renderer parity"
	@echo "make ci      - full CI deploy mirror: check + editable + wheel-install + pytest/coverage (minutes)"
	@echo "make s1-gate - m1 S1 gate: 12 focused lanes + durable summary/logs in out/s1-gate/latest"
	@echo "make m4-baseline - m4 Step 1: run pre-change selectors and retain artifacts/m4/baseline.json (fails closed)"
	@echo "make m4-gate - m4 Step 33: 13 focused lanes + authority lint + drift rejection + feasibility admission (fails closed)"
	@echo "make m7-gate - m7 GA evidence: admitted selectors 1-10 + provisional/retained dispositions (fails closed)"
	@echo "make m8-gate - m8 packaged GA evidence: digest validation + atomic six-file release publication (set M8_EVIDENCE=... to publish a bundle)"
	@echo "make <gate>  - run one gate: structure | doctor | ruff | mypy | cycles | remotion-typecheck | renderer-parity | wheel | ci-mirror | editable | s1-gate | m4-baseline | m4-gate | m7-gate | m8-gate"

# --- Fast gates: catch the common deploy blockers in seconds. Run before every push. ---
check: structure doctor ruff mypy cycles remotion-typecheck renderer-parity
	@echo "✅ make check: blocking pre-deploy gates passed"

structure:
	@$(PY) -c "import sys; from astrid.core.structure import validate_repo_structure as v; r=v(); [print('STRUCTURE ERROR:', e) for e in r.errors]; sys.exit(1 if r.errors else 0)"
	@echo "✓ repo structure (canonical top-level dirs)"

doctor:
	@$(PY) -m astrid doctor --json >/dev/null
	@echo "✓ doctor (deploy health gate)"

ruff:
	@$(PY) scripts/reshape/compare_ruff_baseline.py
	@echo "✓ ruff baseline (no lint regression)"

mypy:
	@$(PY) scripts/reshape/compare_mypy_baseline.py
	@echo "✓ mypy baseline (no type regression)"

cycles:
	@$(PY) -m scripts.reshape.import_cycles --baseline scripts/reshape/baselines/import_cycles.json
	@echo "✓ import cycles (no new cross-package cycle)"

remotion-typecheck:
	@if [ -d remotion/node_modules ]; then \
		$(PY) scripts/gen_remotion_types.py && \
		cd remotion && npm run typecheck; \
	else \
		echo "LANE remotion-typecheck: SKIP (remotion/node_modules absent; run 'cd remotion && npm ci' to enable)"; \
	fi

renderer-parity:
	@$(PY) -m pytest -q -m renderer_parity tests/packs/test_renderer_parity.py

# --- Full mirror of the CI deploy job (slow). Run before a release / when in doubt. ---
ci: check editable wheel ci-mirror
	@echo "✅ make ci: full CI deploy mirror passed — deploy should be green"

editable:
	@$(PY) -c "import astrid; print('✓ editable install imports')"

wheel:
	bash scripts/smoke_wheel_install.sh

ci-mirror:
	bash scripts/reshape/run_ci_checks.sh

# --- m1 S1 gate (plan step 23): the twelve focused m1 lanes, one command ---
# Runs the complete fresh-database, conformance, crash, contention, lint,
# bridge, and provider lane hermetically (fresh ASTRID_PROJECTS_ROOT /
# ASTRID_HOME, scrubbed task env) and retains a machine-readable summary plus
# per-lane logs and JUnit XML under out/s1-gate/latest (gitignored). CI uploads
# that directory with `if: always()` so evidence survives failures. This is the
# SAME target the local CI mirror (run_ci_checks.sh) and GitHub Actions invoke,
# keeping both entry points in lockstep. PY overrides the interpreter (e.g. a
# runtime venv that provides banodoco_timeline_schema for the bridge lanes).
s1-gate:
	@rm -rf out/s1-gate/latest
	@$(PY) scripts/reshape/s1_gate.py --out-dir out/s1-gate/latest
	@echo "✓ s1-gate (12 focused lanes; summary + logs retained in out/s1-gate/latest)"

# --- m4 Step 1 baseline (plan step 1 / task T1) ---
# Runs the pre-change selectors (v10 contract, writer/UoW, timeline
# repository, media pipeline, bridge server) and retains schema-versioned
# evidence at artifacts/m4/baseline.json with the git SHA, tool versions,
# per-selector pass/fail, and timestamps. The script fails closed: a failed,
# absent, or malformed baseline exits non-zero, which blocks Step 2 onward.
# PY overrides the interpreter (same convention as the other gates).
m4-baseline:
	@$(PY) scripts/reshape/m4_baseline.py
	@echo "✓ m4-baseline (pre-change selectors green; evidence retained in artifacts/m4/baseline.json)"

# --- m4 Step 33 finalizer gate (plan step 33 / task T37) ---
# The final m4 admission boundary: 13 retained focused lanes (contracts,
# composition, owner lock, services, CLI, bridge, media/task/run/pack
# conformance, crash/contention, secrets, platform, authority lint), the
# live-tree authority lint, forbidden authority/schema/surface drift
# rejection, the Python 3.11/3.12 matrix, and the present-accepted
# feasibility admission. Fails closed on any missing/rejected admission,
# drift, or lane failure; the external Reigh editor lane stays
# reporting-only (SD1) and is never an input to success. Evidence: per-lane
# logs/JUnit in out/m4-gate/latest (gitignored) and the schema-versioned
# admission at artifacts/m4/finalizer-admission.json. PY overrides the
# interpreter (same convention as the other gates).
m4-gate:
	@$(PY) scripts/reshape/m4_gate.py
	@echo "✓ m4-gate (13 focused lanes + authority lint + drift + feasibility admission; admission retained in artifacts/m4/finalizer-admission.json)"

# --- m7 GA evidence gate (plan step 9 / task T12_impl) ---
# The script first validates the fresh Phase 0 admission, runs the explicit
# whole-file selectors for GA items 1–10, and revalidates admission immediately
# before atomically publishing acceptance.json and defects.md.  Item 11 is
# source/build provisional evidence; item 12 retains the M3 source/test proof
# pending the M8 installed-artifact rerun.
m7-gate:
	@$(PY) scripts/reshape/m7_gate.py --gate --artifact-dir artifacts/m7 --admission artifacts/m7/finalizer-admission.json
	@echo "✓ m7-gate (GA items 1–10 executed; items 11–12 honestly staged; evidence retained in artifacts/m7)"

# --- m8 packaged GA release gate (plan step 9 / task T11) ---
# With M8_EVIDENCE set, publish the supplied installed-lane bundle.  Without
# it, the script still builds exactly one installed wheel and retains the
# missing-evidence diagnostics under out/m8-gate; it never creates a ship file.
m8-gate:
	@if [ -n "$(M8_EVIDENCE)" ]; then \
		$(PY) scripts/reshape/m8_gate.py --gate --evidence "$(M8_EVIDENCE)" --artifact-dir artifacts/m8 --out-dir out/m8-gate; \
	else \
		$(PY) scripts/reshape/m8_gate.py --gate --artifact-dir artifacts/m8 --out-dir out/m8-gate; \
	fi
