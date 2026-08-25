"""Regression checks for the blocking targets in the local CI mirror."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_SCRIPT = REPO_ROOT / "scripts" / "reshape" / "run_ci_checks.sh"


def test_ci_lane_manifest_targets_current_release_tests() -> None:
    source = CI_SCRIPT.read_text(encoding="utf-8")
    expected = (
        "tests/core/test_executor_runner_errors.py::test_external_executor_env_includes_definition_env",
        "tests/core/test_executor_runner_errors.py::test_external_executor_env_inherits_os_environ",
        "tests/core/test_executor_runner_errors.py::test_external_executor_does_not_inherit_undeclared_host_env",
        "tests/core/test_orchestrator_runner_errors.py::test_command_orchestrator_preserves_declared_passthrough_env",
        "tests/core/test_orchestrator_runner_errors.py::test_command_orchestrator_does_not_spread_undeclared_host_env",
        "tests/packs/test_renderer_parity.py",
    )

    for target in expected:
        assert target in source
        assert (REPO_ROOT / target.split("::", 1)[0]).exists(), target

    # These selectors were deleted with the retired legacy task/concurrency
    # runtime and must not silently return to the release lane.
    assert "tests/test_for_each_autoclose.py" not in source
    assert "tests/spikes/test_env_inheritance.py" not in source
    assert "tests/concurrency/test_two_tab_harness_smoke.py" not in source


def test_ci_json_attributes_renderer_parity_to_blocking_lane() -> None:
    source = CI_SCRIPT.read_text(encoding="utf-8")

    # Remotion install/parity are blocking release gates. Their failures must
    # be visible in the stable blocking lane, rather than only in top-level
    # ``ok``/``exit`` or an unreported dynamic lane.
    assert '_run_plain blocking "$PYTHON_BIN" scripts/reshape/remotion_gate.py install' in source
    assert (
        '_run_plain blocking "$PYTHON_BIN" scripts/reshape/remotion_gate.py '
        "parity --reuse-installed"
        in source
    )
    assert "_run_plain renderer_parity" not in source
