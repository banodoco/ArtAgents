#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

BROAD_PYTEST_ARGS=(
  --tb=no
  -q
  --no-header
  --ignore=tests/core/model_catalog/test_registry.py
  --ignore=tests/packs/builtin/dataset_build/test_offline_fixtures.py
  --ignore=tests/packs/builtin/generate_image/test_demo_orchestrator.py
  --ignore=tests/packs/builtin/generate_image/test_manifest_and_validation.py
  --ignore=tests/spikes/test_env_inheritance.py
  --ignore=tests/test_agent_probe_regression.py
  --ignore=tests/test_audio_understand.py
  --ignore=tests/test_author_test_drift.py
  --ignore=tests/test_author_test_pass.py
  --ignore=tests/test_author_test_regenerate.py
  --ignore=tests/test_composition_elements.py
  --ignore=tests/test_for_each_autoclose.py
  --ignore=tests/test_pure_generative_pipeline.py
  --ignore=tests/test_schema_contract.py
)

"$PYTHON_BIN" -m ruff check .
"$PYTHON_BIN" -m mypy scripts/reshape
"$PYTHON_BIN" scripts/reshape/check_repo_hygiene.py

"$PYTHON_BIN" -m pytest tests/reshape -q
"$PYTHON_BIN" -m pytest tests/reshape/test_hype_regression_fixture.py -q
"$PYTHON_BIN" -m pytest tests/concurrency/test_two_tab_harness_smoke.py -q
"$PYTHON_BIN" -m pytest "${BROAD_PYTEST_ARGS[@]}"
