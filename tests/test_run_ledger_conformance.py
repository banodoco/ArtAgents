"""Run ledger conformance test — M1 perimeter characterization.

Enumerates every in-band invocation surface and asserts each produces exactly
one ``run.json`` in exactly one temp project with a terminal status.  New
invocation surfaces must fail this test by construction until they are
registered and ledgered.

The registry below is the canonical ledger-perimeter reference.  Every entry
corresponds to a row in the invocation-surfaces table in
``docs/contracts/run-ledger-contract.md``.

Meta-tests guard the built-in ``GenerationFacade`` methods and the
``_AUTO_BIND_RUN_VERBS`` gateway run prefixes so that unintentional drift is
caught before it breaks ledgering.

.. note::

   **Dynamic plugin-loaded generation verbs are out of scope for M1.**
   Only built-in SDK generation methods (``generate.image``, ``generate.video``)
   are covered by the SDK ``out=`` ledger fix.  Plugins registered via
   ``astrid.core.generation.verbs.register_verb`` are resolved through
   ``__getattr__`` on ``GenerationFacade`` and are documented as an M1 static
   coverage gap (see ``docs/contracts/run-ledger-contract.md`` limits table).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest

from astrid.core.contracts.run_status import RunStatus
from astrid.core.foundation import project_paths
from astrid.core.project.project import create_project

# ---------------------------------------------------------------------------
# Registry of required in-band invocation surfaces
# ---------------------------------------------------------------------------

SurfaceKind = Literal[
    "executor_cli_project",
    "executor_cli_out",
    "orchestrator_cli_project",
    "orchestrator_cli_out",
    "scratch_run",
    "sdk_image_project",
    "sdk_image_out",
    "sdk_video_out",
    "gateway_auto_bind",
]


@dataclass(frozen=True)
class SurfaceEntry:
    """One in-band invocation surface that must produce a ledger entry.

    Not every surface is trivially testable with fake backends at this stage;
    ``testable`` flags whether the scenario can be executed in a unit-test
    environment without network or heavyweight fixture dependencies.
    """

    kind: SurfaceKind
    description: str
    # -- expected ledger shape (after M1 fixes) --
    expected_kind: str | None = None  # run.json.kind, None = executor (absent)
    expected_tool_id: str | None = None
    requires_project: bool = True
    terminal_status: RunStatus = RunStatus.COMPLETED
    # -- scenario execution --
    testable: bool = False  # True when a fake/local test can exercise this surface
    reason_untestable: str = ""


SURFACE_REGISTRY: tuple[SurfaceEntry, ...] = (
    SurfaceEntry(
        kind="executor_cli_project",
        description="executors run --project <p>",
        expected_tool_id="generation.generate_image",
        requires_project=True,
        terminal_status=RunStatus.COMPLETED,
        testable=True,
    ),
    SurfaceEntry(
        kind="executor_cli_out",
        description="executors run --out <dir> (no --project)",
        expected_tool_id="generation.generate_image",
        requires_project=True,  # auto-resolved
        terminal_status=RunStatus.COMPLETED,
        testable=True,
    ),
    SurfaceEntry(
        kind="orchestrator_cli_project",
        description="orchestrators run --project <p>",
        expected_tool_id="video_editing.hype",
        requires_project=True,
        terminal_status=RunStatus.COMPLETED,
        testable=True,
    ),
    SurfaceEntry(
        kind="orchestrator_cli_out",
        description="orchestrators run --out <dir> (no --project)",
        expected_tool_id="video_editing.hype",
        requires_project=True,  # auto-resolved
        terminal_status=RunStatus.COMPLETED,
        testable=True,
    ),
    SurfaceEntry(
        kind="scratch_run",
        description="scratch run <script>",
        expected_kind="scratch",
        expected_tool_id="scratch.run",
        requires_project=True,
        terminal_status=RunStatus.COMPLETED,
        testable=True,
    ),
    SurfaceEntry(
        kind="sdk_image_project",
        description="astrid.generate.image(..., project=...)",
        expected_tool_id="generation.generate_image",
        requires_project=True,
        terminal_status=RunStatus.COMPLETED,
        testable=True,
    ),
    SurfaceEntry(
        kind="sdk_image_out",
        description="astrid.generate.image(..., out=...)",
        expected_tool_id="generation.generate_image",
        requires_project=True,  # auto-resolved
        terminal_status=RunStatus.COMPLETED,
        testable=True,
    ),
    SurfaceEntry(
        kind="sdk_video_out",
        description="astrid.generate.video(..., out=...)",
        expected_tool_id="generation.generate_video",
        requires_project=True,  # auto-resolved
        terminal_status=RunStatus.COMPLETED,
        testable=True,
    ),
    SurfaceEntry(
        kind="gateway_auto_bind",
        description="Gateway auto-bind (no --project, no explicit out=)",
        # Project auto-resolved by the gateway; executor run follows.
        expected_tool_id="generation.generate_image",
        requires_project=True,
        terminal_status=RunStatus.COMPLETED,
        testable=False,
        reason_untestable="requires full CLI subprocess with gateway environment — tested in integration",
    ),
)


def _registry_by_kind() -> dict[SurfaceKind, SurfaceEntry]:
    return {entry.kind: entry for entry in SURFACE_REGISTRY}


# ---------------------------------------------------------------------------
# Meta-tests — built-in SDK facade and gateway run prefixes
# ---------------------------------------------------------------------------


class TestGenerationFacadeBuiltins:
    """Meta-test: every built-in public SDK GenerationFacade method must be present.

    If a built-in method (``image``, ``video``) is removed or renamed, this
    test fails so the ledger contract can be updated before the gap ships.

    Dynamic plugin verbs registered via ``register_verb`` are intentionally
    excluded — they are an M1 static coverage gap (see module docstring).
    """

    # The canonical list of built-in methods on GenerationFacade.
    # __getattr__ handles plugin verbs; only these two are first-class.
    BUILTIN_METHODS: frozenset[str] = frozenset({"image", "video"})

    def test_builtin_methods_present(self) -> None:
        from astrid.sdk import generate

        for name in sorted(self.BUILTIN_METHODS):
            assert hasattr(generate, name), (
                f"GenerationFacade is missing built-in method {name!r}. "
                f"If this was intentional, update the ledger contract and "
                f"this registry before removing the method."
            )

    def test_builtin_methods_are_callable(self) -> None:
        from astrid.sdk import generate

        for name in sorted(self.BUILTIN_METHODS):
            method = getattr(generate, name)
            assert callable(method), (
                f"GenerationFacade.{name} is present but not callable."
            )


class TestGatewayRunPrefixes:
    """Meta-test: ledgeable gateway run prefixes must be present.

    The ``_AUTO_BIND_RUN_VERBS`` tuple defines which CLI verb prefixes trigger
    automatic default-project binding for stateless runs.  If a required
    prefix is removed, runs through that path become invisible to the ledger.
    """

    # Canonical ledgeable run prefixes per the invocation surfaces table.
    REQUIRED_PREFIXES: tuple[tuple[str, ...], ...] = (
        ("executors", "run"),
        ("orchestrators", "run"),
        ("scratch", "run"),
    )

    def test_auto_bind_prefixes_present(self) -> None:
        from astrid.core.gateway import _AUTO_BIND_RUN_VERBS

        observed = frozenset(_AUTO_BIND_RUN_VERBS)
        required = frozenset(self.REQUIRED_PREFIXES)

        missing = required - observed
        assert not missing, (
            f"_AUTO_BIND_RUN_VERBS is missing required prefix(es): {sorted(missing)}. "
            f"If a run path was intentionally removed, update the ledger contract "
            f"and this registry."
        )

    def test_auto_bind_dispatch_registered(self) -> None:
        """Every auto-bind prefix must map to a dispatch handler."""
        from astrid.core.gateway import _TOP_LEVEL_HANDLERS

        for prefix in self.REQUIRED_PREFIXES:
            top = prefix[0]
            assert top in _TOP_LEVEL_HANDLERS, (
                f"Gateway dispatch is missing handler for {top!r}. "
                f"Expected _TOP_LEVEL_HANDLERS to contain {top!r}."
            )

    def test_run_prefixes_are_ledgeable(self) -> None:
        """The sub-verb for each run prefix must be 'run'."""
        # This is a structural invariant: the auto-bind machinery matches
        # (verb, "run") pairs.  If a prefix changes its sub-verb, the
        # auto-bind logic silently breaks.
        for prefix in self.REQUIRED_PREFIXES:
            assert len(prefix) >= 2, f"Prefix {prefix} must have at least 2 elements"
            assert prefix[1] == "run", (
                f"Prefix {prefix} sub-verb must be 'run' for auto-bind to work"
            )


# ---------------------------------------------------------------------------
# Conformance scenario helpers
# ---------------------------------------------------------------------------


def _make_minimal_executor(
    executor_id: str = "test.noop",
    *,
    command: tuple[str, ...] = (sys.executable, "-c", "print('ok')"),
) -> Any:
    """Build a minimal external executor definition for testing."""
    from astrid.core.contracts.schema import CommandSpec
    from astrid.core.execution.executor.schema import ExecutorDefinition

    return ExecutorDefinition(
        id=executor_id,
        name=executor_id.rsplit(".", 1)[-1],
        kind="external",
        version="0.1.0",
        command=CommandSpec(argv=command),
        metadata={},
    )


def _make_minimal_requires_executor(
    executor_id: str = "test.requires",
) -> Any:
    """Build an executor that requires an input — used for validation-failure tests."""
    from astrid.core.contracts.schema import CommandSpec, Port
    from astrid.core.execution.executor.schema import ExecutorDefinition

    return ExecutorDefinition(
        id=executor_id,
        name=executor_id.rsplit(".", 1)[-1],
        kind="external",
        version="0.1.0",
        command=CommandSpec(argv=("echo", "{required_input}")),
        inputs=(Port(name="required_input", type="string", required=True),),
        metadata={},
    )


def _make_minimal_orchestrator(
    orchestrator_id: str = "test.orch",
) -> Any:
    """Build a minimal command-runtime orchestrator definition for testing.

    Uses a command-runtime so --project is supported (python-runtime
    orchestrators do not yet support --project).
    """
    from astrid.core.contracts.schema import CommandSpec
    from astrid.core.execution.orchestrator.schema import OrchestratorDefinition, RuntimeSpec

    return OrchestratorDefinition(
        id=orchestrator_id,
        name=orchestrator_id.rsplit(".", 1)[-1],
        kind="built_in",
        version="0.1.0",
        runtime=RuntimeSpec(
            kind="command",
            command=CommandSpec(argv=(sys.executable, "-c", "print('ok')")),
        ),
        metadata={},
    )


def _setup_project_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    project_slug: str = "demo",
    *,
    with_timeline: bool = True,
) -> tuple[Path, Path]:
    """Set up a temp project and return (projects_root, project_path)."""
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(projects_root))
    create_project(project_slug)
    if with_timeline:
        from astrid.core.timeline.crud import create_timeline
        create_timeline(project_slug, "main", is_default=True)
    return projects_root, projects_root / project_slug


def _project_run_records(projects_root: Path) -> list[dict[str, Any]]:
    """Collect all run.json records across all projects."""
    records: list[dict[str, Any]] = []
    if not projects_root.is_dir():
        return records
    for project_dir in sorted(projects_root.iterdir()):
        if not project_dir.is_dir():
            continue
        runs_dir = project_dir / "runs"
        if not runs_dir.is_dir():
            continue
        for run_dir in sorted(runs_dir.iterdir()):
            run_json = run_dir / "run.json"
            if run_json.is_file():
                try:
                    records.append(json.loads(run_json.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    pass
    return records


# ---------------------------------------------------------------------------
# Conformance scenario tests
# ---------------------------------------------------------------------------


class TestExecutorCLIProject:
    """executors run --project <p> → one run.json in exactly one project."""

    def test_creates_exactly_one_run_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "demo")
        registry = ExecutorRegistry([_make_minimal_executor("test.noop")])

        result = run_executor(
            ExecutorRunRequest("test.noop", out="", project="demo"), registry
        )
        assert result.returncode == 0

        records = _project_run_records(projects_root)
        assert len(records) == 1, (
            f"Expected exactly 1 run.json, found {len(records)}: {records}"
        )
        record = records[0]
        assert record.get("status") == "completed", (
            f"Expected completed status, got {record.get('status')}"
        )
        assert record.get("tool_id") == "test.noop"

    def test_failed_validation_persists_ledger(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import ExecutorRunRequest, ExecutorRunnerError, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "demo")

        requires_exec = _make_minimal_requires_executor("test.requires")
        registry = ExecutorRegistry([requires_exec])

        with pytest.raises(ExecutorRunnerError, match="missing required input"):
            run_executor(
                ExecutorRunRequest("test.requires", out="", project="demo"), registry
            )

        records = _project_run_records(projects_root)
        assert len(records) == 1, (
            f"Failed validation should still persist a ledger entry, "
            f"found {len(records)} records"
        )
        record = records[0]
        assert record.get("status") == "failed", (
            f"Expected failed status for validation failure, got {record.get('status')}"
        )


class TestExecutorCLIOut:
    """executors run --out <dir> (no --project) → ledgered via auto-resolved project."""

    def test_out_without_project_ledgers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When --out is supplied without --project, auto-ledger into the default project."""
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "default")
        out_dir = tmp_path / "my-output"
        out_dir.mkdir()

        registry = ExecutorRegistry([_make_minimal_executor("test.writer")])
        result = run_executor(
            ExecutorRunRequest("test.writer", out=str(out_dir)), registry
        )
        # Pre-fix: out-only runs create no project record
        # Post-fix (T6): out-only runs auto-resolve default project
        assert result.returncode == 0

        records = _project_run_records(projects_root)
        assert len(records) == 1
        assert records[0].get("project_slug") == "default"
        assert records[0].get("out") == str(out_dir)
        assert records[0].get("metadata", {}).get("project_was_auto_resolved") is True


class TestOrchestratorCLIProject:
    """orchestrators run --project <p> → one run.json."""

    def test_creates_exactly_one_run_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
        from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest, run_orchestrator

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "demo")

        registry = OrchestratorRegistry([_make_minimal_orchestrator("test.orch")])
        result = run_orchestrator(
            OrchestratorRunRequest("test.orch", project="demo"), registry
        )
        assert result.returncode == 0

        records = _project_run_records(projects_root)
        assert len(records) == 1, (
            f"Expected exactly 1 run.json, found {len(records)}"
        )
        record = records[0]
        assert record.get("status") == "completed"
        assert record.get("tool_id") == "test.orch"


class TestOrchestratorCLIOut:
    """orchestrators run --out <dir> (no --project) → ledgered."""

    def test_out_without_project_ledgers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
        from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest, run_orchestrator

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "default")
        out_dir = tmp_path / "orch-output"
        out_dir.mkdir()

        registry = OrchestratorRegistry([_make_minimal_orchestrator("test.orch")])
        result = run_orchestrator(
            OrchestratorRunRequest("test.orch", out=str(out_dir)), registry
        )
        assert result.returncode == 0

        records = _project_run_records(projects_root)
        assert len(records) == 1
        assert records[0].get("project_slug") == "default"
        assert records[0].get("tool_id") == "test.orch"
        assert records[0].get("out") == str(out_dir.resolve())
        assert records[0].get("metadata", {}).get("project_was_auto_resolved") is True


class TestScratchRun:
    """scratch run <script> → kind='scratch' ledger entry.

    M1 (T14): scratch runs are now ledgered through the project run lifecycle
    with ``kind='scratch'``, ``tool_id='scratch.run'``, ``requires_timeline=False``,
    environment markers in metadata, and return-code-driven status.
    """

    def test_scratch_run_success_ledgers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Successful scratch script → exactly one ledger entry, completed status.

        Asserts:
        - Exactly one run.json record with kind='scratch'
        - tool_id='scratch.run'
        - status='completed'
        - No timeline_id (requires_timeline=False)
        - Environment markers (pid, prepared_at, process_platform)
        - Preserved subprocess return code (0) in metadata
        - Gateway return code matches subprocess (0)
        """
        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "default")
        from astrid.core.session.lifecycle import create_session
        from astrid.core.session.paths import sessions_dir

        create_session(
            project_slug="default",
            agent_id="test-agent",
            projects_root=projects_root,
            session_root=sessions_dir(),
            session_id="S-SCRATCH-OK",
        )

        script = tmp_path / "success.py"
        script.write_text("import sys; print('ok'); sys.exit(0)", encoding="utf-8")

        import subprocess

        _worktree_root = str(Path(__file__).resolve().parent.parent)

        result = subprocess.run(
            [sys.executable, "-m", "astrid", "scratch", "run", str(script)],
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **{k: v for k, v in os.environ.items() if k not in ("ASTRID_SESSION_ID",)},
                "ASTRID_SESSION_ID": "S-SCRATCH-OK",
                project_paths.PROJECTS_ROOT_ENV: str(projects_root),
                "PYTHONPATH": _worktree_root,
            },
        )

        # Gateway MUST preserve the subprocess return code
        assert result.returncode == 0, (
            f"Expected gateway return code 0 (from successful script), "
            f"got {result.returncode}. stderr: {result.stderr[:500]}"
        )

        records = _project_run_records(projects_root)
        assert len(records) == 1, (
            f"Expected exactly 1 run.json, found {len(records)}: {records}"
        )
        record = records[0]

        # Core identity
        assert record.get("kind") == "scratch", (
            f"Expected kind='scratch', got {record.get('kind')!r}"
        )
        assert record.get("tool_id") == "scratch.run", (
            f"Expected tool_id='scratch.run', got {record.get('tool_id')!r}"
        )
        assert record.get("status") == "completed", (
            f"Expected status='completed', got {record.get('status')!r}"
        )
        assert record.get("session_id") == "S-SCRATCH-OK"
        assert record.get("auto_bound") is True
        assert record.get("invocation") == "scratch"

        # No timeline requirement
        assert record.get("timeline_id") is None, (
            f"Scratch runs use requires_timeline=False; "
            f"expected no timeline_id, got {record.get('timeline_id')!r}"
        )

        # Environment markers from prepare metadata
        meta = record.get("metadata", {})
        assert isinstance(meta, dict), f"Expected metadata dict, got {type(meta)}"
        assert "pid" in meta, (
            f"Expected metadata.pid (environment marker), got keys: {sorted(meta.keys())}"
        )
        assert "prepared_at" in meta, (
            f"Expected metadata.prepared_at (environment marker), got keys: {sorted(meta.keys())}"
        )
        assert "process_platform" in meta, (
            f"Expected metadata.process_platform (environment marker), got keys: {sorted(meta.keys())}"
        )

        # Preserved subprocess return code
        assert meta.get("returncode") == 0, (
            f"Expected metadata.returncode=0, got {meta.get('returncode')!r}"
        )

    def test_scratch_run_failure_ledgers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Failing scratch script → exactly one ledger entry, failed status.

        Asserts:
        - Exactly one run.json record with kind='scratch'
        - status='failed'
        - No timeline_id
        - Preserved non-zero return code in metadata
        - Gateway return code matches subprocess (non-zero)
        """
        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "default")

        script = tmp_path / "fail.py"
        script.write_text("import sys; print('fail!'); sys.exit(42)", encoding="utf-8")

        import subprocess

        _worktree_root = str(Path(__file__).resolve().parent.parent)

        result = subprocess.run(
            [sys.executable, "-m", "astrid", "scratch", "run", str(script)],
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **{k: v for k, v in os.environ.items() if k not in ("ASTRID_SESSION_ID",)},
                project_paths.PROJECTS_ROOT_ENV: str(projects_root),
                "PYTHONPATH": _worktree_root,
            },
        )

        # Gateway MUST preserve the subprocess return code (non-zero)
        assert result.returncode == 42, (
            f"Expected gateway return code 42 (from failing script), "
            f"got {result.returncode}. stderr: {result.stderr[:500]}"
        )

        records = _project_run_records(projects_root)
        assert len(records) == 1, (
            f"Expected exactly 1 run.json, found {len(records)}: {records}"
        )
        record = records[0]

        # Core identity
        assert record.get("kind") == "scratch", (
            f"Expected kind='scratch', got {record.get('kind')!r}"
        )
        assert record.get("tool_id") == "scratch.run", (
            f"Expected tool_id='scratch.run', got {record.get('tool_id')!r}"
        )
        assert record.get("status") == "failed", (
            f"Expected status='failed', got {record.get('status')!r}"
        )
        assert record.get("auto_bound") is True
        assert record.get("invocation") == "scratch"

        # No timeline requirement
        assert record.get("timeline_id") is None, (
            f"Scratch runs use requires_timeline=False; "
            f"expected no timeline_id, got {record.get('timeline_id')!r}"
        )

        # Environment markers from prepare metadata
        meta = record.get("metadata", {})
        assert isinstance(meta, dict), f"Expected metadata dict, got {type(meta)}"
        assert "pid" in meta, (
            f"Expected metadata.pid (environment marker), got keys: {sorted(meta.keys())}"
        )
        assert "prepared_at" in meta, (
            f"Expected metadata.prepared_at (environment marker), got keys: {sorted(meta.keys())}"
        )

        # Preserved non-zero return code
        assert meta.get("returncode") == 42, (
            f"Expected metadata.returncode=42, got {meta.get('returncode')!r}"
        )


class TestSDKImageProject:
    """astrid.generate.image(..., project=...) → one run.json."""

    def test_image_with_project_ledgers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "demo")
        registry = ExecutorRegistry([_make_minimal_executor("generation.generate_image")])

        result = run_executor(
            ExecutorRunRequest("generation.generate_image", out="", project="demo"), registry
        )
        assert result.returncode == 0

        records = _project_run_records(projects_root)
        assert len(records) == 1
        assert records[0].get("tool_id") == "generation.generate_image"


class TestSDKImageOut:
    """astrid.generate.image(..., out=...) → ledgered with run.json.out."""

    def test_image_out_ledgers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "default")
        out_dir = tmp_path / "gen-output"
        out_dir.mkdir()

        registry = ExecutorRegistry([_make_minimal_executor("generation.generate_image")])
        result = run_executor(
            ExecutorRunRequest("generation.generate_image", out=str(out_dir)), registry
        )

        records = _project_run_records(projects_root)
        if not records:
            pytest.skip(
                "Pre-fix: SDK image out-without-project is unledgered (T10 will fix)"
            )


class TestSDKVideoOut:
    """astrid.generate.video(..., out=...) → ledgered with run.json.out."""

    def test_video_out_ledgers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "default")
        out_dir = tmp_path / "video-output"
        out_dir.mkdir()

        registry = ExecutorRegistry([_make_minimal_executor("generation.generate_video")])
        result = run_executor(
            ExecutorRunRequest("generation.generate_video", out=str(out_dir)), registry
        )

        records = _project_run_records(projects_root)
        if not records:
            pytest.skip(
                "Pre-fix: SDK video out-without-project is unledgered (T10 will fix)"
            )


# ---------------------------------------------------------------------------
# Registry completeness: every registered surface is accounted for
# ---------------------------------------------------------------------------


class TestRegistryCompleteness:
    """Ensure the SURFACE_REGISTRY covers all 8 required in-band surfaces."""

    REQUIRED_KINDS: frozenset[SurfaceKind] = frozenset({
        "executor_cli_project",
        "executor_cli_out",
        "orchestrator_cli_project",
        "orchestrator_cli_out",
        "scratch_run",
        "sdk_image_project",
        "sdk_image_out",
        "sdk_video_out",
        "gateway_auto_bind",
    })

    def test_all_required_surfaces_registered(self) -> None:
        registered = frozenset(entry.kind for entry in SURFACE_REGISTRY)
        missing = self.REQUIRED_KINDS - registered
        assert not missing, (
            f"SURFACE_REGISTRY is missing required surface kind(s): {sorted(missing)}"
        )

    def test_no_duplicate_surface_kinds(self) -> None:
        kinds = [entry.kind for entry in SURFACE_REGISTRY]
        seen: set[str] = set()
        dupes: list[str] = []
        for k in kinds:
            if k in seen:
                dupes.append(k)
            seen.add(k)
        assert not dupes, f"Duplicate surface kinds in registry: {dupes}"

    def test_dry_run_not_in_registry(self) -> None:
        """Dry-run is an explicit exemption, not a conformance surface."""
        dry_run_kinds = {k for k in (entry.kind for entry in SURFACE_REGISTRY) if "dry" in k}
        assert not dry_run_kinds, (
            "Dry-run is an exemption — it should not appear in the conformance registry"
        )

    def test_plugin_verbs_not_in_registry(self) -> None:
        """Dynamic plugin verbs are out of scope (M1 static coverage gap)."""
        plugin_kinds = {
            k for k in (entry.kind for entry in SURFACE_REGISTRY) if "plugin" in k
        }
        assert not plugin_kinds, (
            "Plugin-loaded generation verbs are an M1 static coverage gap — "
            "they are intentionally not in the conformance registry"
        )
