# Astrid local gate — run before pushing to catch CI/deploy failures locally.
#
#   make check   fast pre-deploy gates (structure, doctor, ruff, mypy, cycles) — seconds
#   make ci      full mirror of the CI deploy job (adds wheel-install + pytest+coverage) — minutes
#
# `make check` green ≈ the CI "Python quality gates" deploy job will pass its fast gates.
# These run the SAME scripts CI runs (see .github/workflows/ci.yml), so they stay in lockstep.

PY ?= python3

.PHONY: help check ci structure doctor ruff mypy cycles wheel ci-mirror editable

help:
	@echo "make check   - fast pre-deploy gates: structure, doctor, ruff, mypy, cycles (seconds)"
	@echo "make ci      - full CI deploy mirror: check + editable + wheel-install + pytest/coverage (minutes)"
	@echo "make <gate>  - run one gate: structure | doctor | ruff | mypy | cycles | wheel | ci-mirror | editable"

# --- Fast gates: catch the common deploy blockers in seconds. Run before every push. ---
check: structure doctor ruff mypy cycles
	@echo "✅ make check: fast pre-deploy gates passed"

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

# --- Full mirror of the CI deploy job (slow). Run before a release / when in doubt. ---
ci: check editable wheel ci-mirror
	@echo "✅ make ci: full CI deploy mirror passed — deploy should be green"

editable:
	@$(PY) -c "import astrid; print('✓ editable install imports')"

wheel:
	bash scripts/smoke_wheel_install.sh

ci-mirror:
	bash scripts/reshape/run_ci_checks.sh
