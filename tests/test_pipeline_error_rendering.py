from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import textwrap
from unittest import mock

from astrid import pipeline
from astrid.contracts.errors import AstridError
from astrid.core.project.project import ProjectError
from astrid.core.project.schema import ProjectValidationError
from astrid.core.session.binding import SessionBindingError
from astrid.core.task.gate_base import TaskRunGateError
from astrid.core.timeline._edit_helpers import TimelineEditError


def _capture(argv: list[str]) -> tuple[int, str]:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        rc = pipeline.main(argv)
    return rc, stderr.getvalue()


def test_main_renders_astrid_error_without_traceback() -> None:
    err = AstridError(
        "bad transition kind",
        valid_options=("cross-fade", "wipe"),
        recovery_command="astrid timelines transition set --kind cross-fade",
        state_snapshot={"project": "demo"},
    )

    with mock.patch.object(pipeline, "_dispatch", side_effect=err):
        rc, stderr = _capture(["doctor"])

    assert rc == 2
    assert "bad transition kind" in stderr
    assert "valid options: cross-fade, wipe" in stderr
    assert "recovery: astrid timelines transition set --kind cross-fade" in stderr
    assert 'state snapshot: {"project": "demo"}' in stderr
    assert "Traceback" not in stderr


def test_main_wraps_generic_exception_as_degraded_bug_envelope() -> None:
    with mock.patch.object(pipeline, "_dispatch", side_effect=ValueError("boom")):
        rc, stderr = _capture(["doctor"])

    assert rc == 1
    assert stderr.splitlines()[0] == "unstructured - this is a bug."
    assert "boom" in stderr
    assert '"entrypoint": "astrid.pipeline.main"' in stderr
    assert "Traceback" not in stderr


def test_unknown_top_level_command_renders_structured_recovery() -> None:
    rc, stderr = _capture(["definitely-not-a-command"])

    assert rc == 2
    assert "unknown command 'definitely-not-a-command'" in stderr
    assert "recovery: astrid --help" in stderr
    assert "valid options:" in stderr
    assert "Traceback" not in stderr


def test_models_registry_load_failure_flows_through_renderer() -> None:
    with mock.patch(
        "astrid.core.model_catalog.registry.ModelRegistry.load_default",
        side_effect=RuntimeError("catalog exploded"),
    ):
        rc, stderr = _capture(["models", "list"])

    assert rc == 2
    assert "failed to load model registry: catalog exploded" in stderr
    assert "recovery: astrid models list" in stderr
    assert '"command": "models list"' in stderr
    assert "Traceback" not in stderr


def test_task_gate_rejection_flows_through_universal_renderer() -> None:
    with (
        mock.patch(
            "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
            return_value=object(),
        ),
        mock.patch(
            "astrid.core.task.gate.gate_command",
            side_effect=TaskRunGateError(
                reason="step is blocked",
                recovery="astrid next --project demo",
                code="gate_rejected",
            ),
        ),
    ):
        rc, stderr = _capture(["executors", "list", "--project", "demo"])

    assert rc == 2
    assert "step is blocked" in stderr
    assert "recovery: astrid next --project demo" in stderr
    assert '"gate": "task-mode"' in stderr
    assert "task-mode gate rejected:" not in stderr
    assert "Traceback" not in stderr


# ---------------------------------------------------------------------------
# T17: pipeline renderer edge cases and module-entry proof
# ---------------------------------------------------------------------------


def test_module_entry_delegates_to_pipeline_main() -> None:
    """``python -m astrid`` reaches the same ``pipeline.main()`` renderer."""
    from astrid.__main__ import main as module_main
    from astrid.pipeline import main as pipeline_main

    assert module_main is pipeline_main


def test_renderer_degraded_minimal_no_valid_options_or_recovery() -> None:
    """Degraded envelope with only a cause still emits the bug flag and exits 1."""
    err = AstridError("something broke", degraded=True)
    with mock.patch.object(pipeline, "_dispatch", side_effect=err):
        rc, stderr = _capture(["doctor"])

    assert rc == 1
    lines = stderr.strip().splitlines()
    assert lines[0] == "unstructured - this is a bug."
    assert "something broke" in lines[1]


def test_renderer_non_degraded_minimal_no_valid_options_or_recovery() -> None:
    """Non-degraded envelope with only a cause prints cause only and exits 2."""
    err = AstridError("simple failure")
    with mock.patch.object(pipeline, "_dispatch", side_effect=err):
        rc, stderr = _capture(["doctor"])

    assert rc == 2
    lines = stderr.strip().splitlines()
    assert lines[0] == "simple failure"
    assert "valid options:" not in stderr
    assert "recovery:" not in stderr
    assert "state snapshot:" not in stderr


def test_subprocess_module_entry_to_renderer_no_traceback() -> None:
    """``python -m astrid`` error path reaches the renderer: no traceback."""

    code = textwrap.dedent("""\
        import sys
        from unittest import mock
        from astrid.pipeline import main

        from astrid.contracts.errors import AstridError

        err = AstridError(
            "bad transition kind",
            valid_options=("cross-fade", "wipe"),
            recovery_command="astrid timelines transition set --kind cross-fade",
            state_snapshot={"project": "demo"},
        )
        with mock.patch("astrid.pipeline._dispatch", side_effect=err):
            sys.exit(main(["doctor"]))
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "bad transition kind" in result.stderr
    assert "valid options: cross-fade, wipe" in result.stderr
    assert "recovery: astrid timelines transition set --kind cross-fade" in result.stderr
    assert 'state snapshot: {"project": "demo"}' in result.stderr
    assert "Traceback" not in result.stderr


def test_subprocess_degraded_bug_envelope_no_traceback() -> None:
    """Generic exception through ``pipeline.main()`` → degraded envelope, no traceback."""

    code = textwrap.dedent("""\
        import sys
        from unittest import mock
        from astrid.pipeline import main

        with mock.patch("astrid.pipeline._dispatch", side_effect=ValueError("boom")):
            sys.exit(main(["doctor"]))
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert result.stderr.splitlines()[0] == "unstructured - this is a bug."
    assert "boom" in result.stderr
    assert '"entrypoint": "astrid.pipeline.main"' in result.stderr
    assert "Traceback" not in result.stderr


# ============================================================================
# T19: migrated core errors flowing through the universal renderer
# ============================================================================


def test_session_binding_error_renders_via_envelope() -> None:
    """SessionBindingError routed through pipeline.main() → envelope, no bespoke prefix."""
    err = SessionBindingError("no session file at /tmp/X.json")
    with mock.patch.object(pipeline, "_dispatch", side_effect=err):
        rc, stderr = _capture(["executors", "list"])
    assert rc == 2
    assert "no session file at /tmp/X.json" in stderr
    assert "session:" not in stderr  # no bespoke prefix
    assert "Traceback" not in stderr


def test_timeline_edit_error_renders_via_envelope() -> None:
    """TimelineEditError routed through pipeline.main() → envelope, no 'timelines:' prefix."""
    err = TimelineEditError("clip 'X' not found")
    with mock.patch.object(pipeline, "_dispatch", side_effect=err):
        rc, stderr = _capture(["timelines", "ls"])
    assert rc == 2
    assert "clip 'X' not found" in stderr
    assert "timelines:" not in stderr  # no bespoke prefix when routed through envelope
    assert "Traceback" not in stderr


def test_project_error_renders_via_envelope() -> None:
    """ProjectError routed through pipeline.main() → envelope, no bespoke prefix."""
    err = ProjectError("project 'demo' already exists")
    with mock.patch.object(pipeline, "_dispatch", side_effect=err):
        rc, stderr = _capture(["projects", "create", "demo"])
    assert rc == 2
    assert "project 'demo' already exists" in stderr
    assert "Traceback" not in stderr


def test_project_validation_error_renders_via_envelope() -> None:
    """ProjectValidationError routed through pipeline.main() → envelope."""
    err = ProjectValidationError("source.kind must be one of {...}")
    with mock.patch.object(pipeline, "_dispatch", side_effect=err):
        rc, stderr = _capture(["projects", "show"])
    assert rc == 2
    assert "source.kind must be one of {...}" in stderr
    assert "Traceback" not in stderr


def test_timeline_edit_error_envelope_has_no_stderr_prefix() -> None:
    """Legacy 'timelines:' stderr prefix must NOT appear in envelope-rendered error."""
    err = TimelineEditError("track 'A' not found")
    assert "timelines:" not in err.cause
    assert "timelines:" not in err.message
    with mock.patch.object(pipeline, "_dispatch", side_effect=err):
        rc, stderr = _capture(["timelines", "show", "demo"])
    assert rc == 2
    assert "track 'A' not found" in stderr
    assert "timelines:" not in stderr.lower()
    # But the universal renderer env should still say "recovery:" / "valid options:"
    # if those fields happen to be set — TimelineEditError has none of them, so
    # just ensure no prepended prefix leaked.
    assert "Traceback" not in stderr
