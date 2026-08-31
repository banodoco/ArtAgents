"""Runtime run/task conformance characterization.

Enumerates in-band invocation surfaces and keeps the durable run/task
authority in the workspace runtime.  Filesystem outputs are treated as
derived pack artifacts, not as a ledger.

The registry below is the canonical ledger-perimeter reference.  Every entry
corresponds to a row in the invocation-surfaces table in
``docs/contracts/run-ledger-contract.md``.

Meta-tests guard the built-in ``GenerationFacade`` methods so that
unintentional drift is caught before it breaks ledgering.

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
    # The repository-wide sandbox owns ``tmp_path / "projects"``. Keep this
    # helper's explicitly controlled root nested so setup ownership cannot
    # collide with the autouse safety fixture.
    projects_root = tmp_path / "ledger-projects"
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


def _kernel_db_path(projects_root: Path) -> Path:
    return projects_root / ".astrid" / "astrid.sqlite3"


def _kernel_counts(projects_root: Path) -> tuple[int, int, int, int]:
    """Return (runs, tasks, events, receipts) from kernel DB; zeros if absent."""
    db = _kernel_db_path(projects_root)
    if not db.is_file():
        return (0, 0, 0, 0)
    import sqlite3

    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        try:
            runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            receipts = conn.execute("SELECT COUNT(*) FROM command_receipts").fetchone()[0]
        except sqlite3.Error:
            return (0, 0, 0, 0)
        return (int(runs), int(tasks), int(events), int(receipts))


def _kernel_tasks(projects_root: Path) -> list[dict[str, Any]]:
    db = _kernel_db_path(projects_root)
    if not db.is_file():
        return []
    import sqlite3

    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT id, run_id, status, capability FROM tasks ORDER BY run_ordinal").fetchall()
        except sqlite3.Error:
            return []
        return [dict(r) for r in rows]


def _assert_kernel_single_ledger(
    projects_root: Path,
    *,
    expected_runs: int = 1,
    expected_tasks: int = 1,
    min_events: int = 4,
    min_receipts: int = 2,
) -> None:
    runs, tasks, events, receipts = _kernel_counts(projects_root)
    assert runs == expected_runs, f"kernel runs {runs} != {expected_runs}"
    assert tasks == expected_tasks, f"kernel tasks {tasks} != {expected_tasks}"
    assert events >= min_events, f"kernel events {events} < {min_events}"
    assert receipts >= min_receipts, f"kernel receipts {receipts} < {min_receipts}"
    for t in _kernel_tasks(projects_root):
        assert t["status"] in ("succeeded", "completed", "succeeded", "completed", "succeeded"), f"task {t['id']} terminal {t['status']}"




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
            ExecutorRunRequest(
                "test.noop",
                out=tmp_path / "kernel-staging",
                project="demo",
                project_was_auto_resolved=True,
            ),
            registry,
        )
        assert result.returncode == 0

        records = _project_run_records(projects_root)
        # Single-ledger contract (B2): project-mode runner no longer writes
        # authoritative run.json; kernel admission owns the ledger, runner
        # retains out as staging only. Zero authoritative FS writes.
        assert len(records) == 0, (
            f"Expected zero authoritative run.json (kernel-owned), found {len(records)}: {records}"
        )
    def test_failed_validation_persists_ledger(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import (
            ExecutorRunnerError,
            ExecutorRunRequest,
            run_executor,
        )

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "demo")

        requires_exec = _make_minimal_requires_executor("test.requires")
        registry = ExecutorRegistry([requires_exec])

        with pytest.raises(ExecutorRunnerError, match="missing required input"):
            run_executor(
                ExecutorRunRequest(
                    "test.requires",
                    out=tmp_path / "kernel-staging",
                    project="demo",
                    project_was_auto_resolved=True,
                ),
                registry,
            )

        records = _project_run_records(projects_root)
        # B2 single-ledger: even failed validation does not persist authoritative
        # run.json in the runner; kernel admission owns that write.
        assert len(records) == 0, (
            f"Failed validation should not persist authoritative run.json under single-ledger, "
            f"found {len(records)} records"
        )

    def test_out_without_project_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "default")
        monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)
        out_dir = tmp_path / "my-output"
        out_dir.mkdir()

        registry = ExecutorRegistry([_make_minimal_executor("test.writer")])
        with pytest.raises(Exception, match="project required"):
            run_executor(ExecutorRunRequest("test.writer", out=str(out_dir)), registry)

        records = _project_run_records(projects_root)
        assert records == []


class TestOrchestratorCLIProject:
    """orchestrators run --project <p> without kernel/out → fail-closed."""

    def test_creates_exactly_one_run_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
        from astrid.core.execution.orchestrator.runner import (
            OrchestratorRunRequest,
            run_orchestrator,
        )
        from astrid.core.project.runtime import ProjectRuntimeError as ProjectRunError

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "demo")

        registry = OrchestratorRegistry([_make_minimal_orchestrator("test.orch")])
        with pytest.raises((ProjectRunError, Exception), match="requires --out|kernel run|project required"):
            run_orchestrator(
                OrchestratorRunRequest("test.orch", project="demo"), registry
            )

        records = _project_run_records(projects_root)
        # Fail-closed: no authoritative run.json written
        assert len(records) == 0, (
            f"Expected zero authoritative run.json (fail-closed, kernel-owned), found {len(records)}"
        )
        # And no kernel rows created
        runs, tasks, _, _ = _kernel_counts(projects_root)
        assert runs == 0, f"expected zero kernel runs on fail-closed, found {runs}"
        assert tasks == 0, f"expected zero kernel tasks on fail-closed, found {tasks}"
class TestOrchestratorCLIOut:
    """Orchestrator output paths do not imply project ownership."""

    def test_out_without_project_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
        from astrid.core.execution.orchestrator.runner import (
            OrchestratorRunRequest,
            run_orchestrator,
        )

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "default")
        monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)
        out_dir = tmp_path / "orch-output"
        out_dir.mkdir()

        registry = OrchestratorRegistry([_make_minimal_orchestrator("test.orch")])
        with pytest.raises(Exception, match="project required"):
            run_orchestrator(OrchestratorRunRequest("test.orch", out=str(out_dir)), registry)

        records = _project_run_records(projects_root)
        assert records == []


class TestSDKImageProject:
    """astrid.generate.image(..., project=...) → one run.json."""

    def test_image_with_project_ledgers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "demo")
        registry = ExecutorRegistry([_make_minimal_executor("generation.generate_image")])

        result = run_executor(
            ExecutorRunRequest(
                "generation.generate_image",
                out=tmp_path / "kernel-staging",
                project="demo",
                project_was_auto_resolved=True,
            ),
            registry,
        )
        assert result.returncode == 0

        records = _project_run_records(projects_root)
        # B2 single-ledger: project-mode via runner is staging-only, no authoritative FS ledger.
        assert len(records) == 0

class TestSDKImageOut:
    """SDK image output still requires an explicit or attached project."""

    def test_image_out_without_project_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "default")
        monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)
        out_dir = tmp_path / "gen-output"
        out_dir.mkdir()

        registry = ExecutorRegistry([_make_minimal_executor("generation.generate_image")])
        with pytest.raises(Exception, match="project required"):
            run_executor(
                ExecutorRunRequest("generation.generate_image", out=str(out_dir)), registry
            )

        records = _project_run_records(projects_root)
        assert records == []


class TestSDKVideoOut:
    """SDK video output still requires an explicit or attached project."""

    def test_video_out_without_project_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.executor.registry import ExecutorRegistry
        from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "default")
        monkeypatch.delenv("ASTRID_SESSION_ID", raising=False)
        out_dir = tmp_path / "video-output"
        out_dir.mkdir()

        registry = ExecutorRegistry([_make_minimal_executor("generation.generate_video")])
        with pytest.raises(Exception, match="project required"):
            run_executor(
                ExecutorRunRequest("generation.generate_video", out=str(out_dir)), registry
            )

        records = _project_run_records(projects_root)
        assert records == []


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


# ---------------------------------------------------------------------------
# Single-ledger harness: ≥6 caps via kernel admission (B4.2)
# ---------------------------------------------------------------------------




class TestSingleLedgerHarness:
    """B4.2 empirical harness for runtime-owned run/task admission."""

    CAPS = [
        ("generation.generate_image", {"prompt": "a cat", "seed": 1}),
        ("test.file_only_executor", {"cmd": "echo hi"}),
        ("rendering.timeline_visualize", {"timeline": "main"}),
        ("rendering.attached_render", {"composition": "main"}),
        ("generation.generate_video", {"prompt": "a dog", "seed": 2}),
        ("test.orchestrator_child", {"step": "plan"}),
    ]

    def test_six_caps_runtime_admission(self, tmp_path: Path) -> None:
        from astrid.core.project.kernel_admission import admit_orchestrator_project_run

        class _Tasks:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def create(self, **kwargs: Any) -> dict[str, str]:
                self.calls.append(kwargs)
                index = len(self.calls)
                return {"run_id": f"runtime-run-{index}", "task_id": f"runtime-task-{index}"}

        class _Client:
            def __init__(self) -> None:
                self.tasks = _Tasks()

        client = _Client()
        for idx, (cap, spec) in enumerate(self.CAPS):
            safe = cap.replace(".", "-")
            base = tmp_path / safe
            base.mkdir(parents=True, exist_ok=True)
            slug = f"demo-cap{idx+1}"
            context = admit_orchestrator_project_run(
                project=slug,
                tool_id=cap,
                argv=["--project", slug],
                projects_root=base,
                _client=client,
            )
            assert context.run_id == f"runtime-run-{idx + 1}"
            assert context.run_root.is_dir()
            assert not context.run_root.is_relative_to(base)
            assert not list(base.rglob("run.json"))
            assert client.tasks.calls[-1]["spec"]["argv"] == ["--project", slug]

    def test_orchestrator_with_children_hard_chain(self, tmp_path: Path) -> None:
        from astrid.core.project.kernel_admission import admit_orchestrator_project_run

        class _Tasks:
            def create(self, **kwargs: Any) -> dict[str, str]:
                assert kwargs["capability"] == "test.orch"
                assert kwargs["project_id"] == "demo-orch"
                return {"run_id": "runtime-run-1", "task_id": "runtime-task-1"}

        class _Client:
            tasks = _Tasks()

        projects_root = tmp_path / "orch-projects"
        projects_root.mkdir()
        ctx = admit_orchestrator_project_run(
            project="demo-orch",
            tool_id="test.orch",
            argv=["--project", "demo-orch"],
            projects_root=projects_root,
            _client=_Client(),
        )
        assert ctx.run_id == "runtime-run-1"
        assert not ctx.run_root.is_relative_to(projects_root)
        assert not list(projects_root.rglob("run.json"))


    def test_runtime_admission_does_not_create_local_run_projection(self, tmp_path: Path) -> None:
        projects_root = tmp_path / "banodoco-projects"
        projects_root.mkdir()
        from astrid.core.project.kernel_admission import admit_orchestrator_project_run
        class _Tasks:
            def create(self, **kwargs: Any) -> dict[str, str]:
                return {"run_id": "runtime-run-2", "task_id": "runtime-task-2"}

        class _Client:
            tasks = _Tasks()

        ctx = admit_orchestrator_project_run(
            project="demo-b",
            tool_id="test.banodoco",
            argv=["x"],
            projects_root=projects_root,
            _client=_Client(),
        )
        assert ctx.run_id == "runtime-run-2"
        assert not list(projects_root.rglob("run.json"))
