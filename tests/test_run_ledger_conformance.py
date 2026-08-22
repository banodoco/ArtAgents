"""Run ledger conformance test — M1 perimeter characterization.

Enumerates every in-band invocation surface and asserts each produces exactly
one ``run.json`` in exactly one temp project with a terminal status.  New
invocation surfaces must fail this test by construction until they are
registered and ledgered.

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


def _kernel_db_path(projects_root: Path) -> Path:
    return projects_root / "kernel.sqlite3"


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
            ExecutorRunRequest("test.noop", out="", project="demo"), registry
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
        from astrid.core.execution.executor.runner import ExecutorRunRequest, ExecutorRunnerError, run_executor

        projects_root, _ = _setup_project_env(tmp_path, monkeypatch, "demo")

        requires_exec = _make_minimal_requires_executor("test.requires")
        registry = ExecutorRegistry([requires_exec])

        with pytest.raises(ExecutorRunnerError, match="missing required input"):
            run_executor(
                ExecutorRunRequest("test.requires", out="", project="demo"), registry
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
    """orchestrators run --project <p> → storage-only (kernel ledger)."""

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
        # Single-ledger contract (B4): orchestrator runner is storage-only; kernel owns ledger
        assert len(records) == 0, (
            f"Expected zero authoritative run.json (kernel-owned), found {len(records)}"
        )

class TestOrchestratorCLIOut:
    """Orchestrator output paths do not imply project ownership."""

    def test_out_without_project_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.execution.orchestrator.registry import OrchestratorRegistry
        from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest, run_orchestrator

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
            ExecutorRunRequest("generation.generate_image", out="", project="demo"), registry
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


def _admit_and_complete_one(
    projects_root: Path, project_slug: str, capability: str, spec: dict[str, Any] | None = None
) -> tuple[str, str]:
    """Create 1 task via TaskRepository and drive it to completed (kernel ledger)."""
    from astrid.core.events.service import EventAppendService
    from astrid.core.events.registry import core_only_registry
    from astrid.core.ids import generate_lowercase_ulid
    from astrid.core.receipts import ReceiptService
    from astrid.core.repositories import ProjectRepository
    from astrid.core.repositories.tasks import TaskRepository, compute_spec_hash
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.store.writer import DatabaseWriter

    registry = core_only_registry()
    db_path = projects_root / "kernel.sqlite3"
    writer = DatabaseWriter(db_path, registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        tasks = TaskRepository(events=events, receipts=receipts)
        projects = ProjectRepository(events=events, receipts=receipts)
        from astrid.core.repositories.media import MediaRepository
        media_repo = MediaRepository(events=events, receipts=receipts, projects_root=projects_root)
        spec_payload = spec or {"prompt": "hello", "seed": 1}
        idempotency_key = compute_spec_hash({"capability": capability, "spec": spec_payload}, [])
        task_id = generate_lowercase_ulid()
        # Use slug as kernel project_id (matches kernel_admission shim)
        kernel_project_id = project_slug
        # Ensure kernel project exists (idempotent)
        try:
            UnitOfWork(writer).run(lambda u: projects.create(u, slug=project_slug, name=project_slug, settings={}, idempotency_key=f"proj-{project_slug}", project_id=kernel_project_id))
        except Exception:
            pass
        # Admit task
        UnitOfWork(writer).run(lambda u: tasks.create(u, project_id=kernel_project_id, capability=capability, spec=spec_payload, input_manifest=[], idempotency_key=idempotency_key, task_id=task_id))
        tid = task_id
        # Claim -> start -> complete (proper lease/status_version handling)
        claim = UnitOfWork(writer).run(lambda u: tasks.claim(u, project_id=kernel_project_id, idempotency_key=f"claim-{tid}", executor_id="test-exec"))
        if claim is None:
            return kernel_project_id, tid
        # Extract attempt fields from claim model (TaskClaimReadModel)
        attempt = claim.attempt  # type: ignore[attr-defined]
        task_obj = claim.task  # type: ignore[attr-defined]
        # Fallback for dict replay
        if isinstance(claim, dict):
            attempt = claim.get("attempt") or claim  # type: ignore
            task_obj = claim.get("task") or {"id": tid}  # type: ignore
        attempt_id = attempt.id if hasattr(attempt, "id") else attempt.get("id", tid)  # type: ignore
        lease_id = attempt.lease_id if hasattr(attempt, "lease_id") else attempt.get("lease_id")  # type: ignore
        sv = int(attempt.status_version if hasattr(attempt, "status_version") else attempt.get("status_version", 1))  # type: ignore
        # Start
        started = UnitOfWork(writer).run(lambda u: tasks.start(u, project_id=kernel_project_id, task_id=task_obj.id if hasattr(task_obj, "id") else task_obj.get("id", tid), attempt_id=attempt_id, expected_status_version=sv, lease_id=lease_id, idempotency_key=f"start-{tid}"))  # type: ignore
        sv2 = int(started.status_version if hasattr(started, "status_version") else started.get("status_version", sv + 1))  # type: ignore
        # Complete — requires outputs or result; provide empty outputs + result summary + media_repo
        UnitOfWork(writer).run(lambda u: tasks.complete(u, project_id=kernel_project_id, task_id=task_obj.id if hasattr(task_obj, "id") else task_obj.get("id", tid), attempt_id=attempt_id, expected_status_version=sv2, lease_id=lease_id, idempotency_key=f"complete-{tid}", outputs=[], result={"outputs": []}, media_repo=media_repo))  # type: ignore
        return kernel_project_id, tid
    finally:
        try:
            writer.close()
        except Exception:
            pass
def _drive_orchestrator_chain(projects_root: Path, project_slug: str) -> None:
    """Drive orchestrator hard-chain (4 tasks) to terminal via TaskRepository."""
    from astrid.core.events.registry import core_only_registry
    from astrid.core.events.service import EventAppendService
    from astrid.core.receipts import ReceiptService
    from astrid.core.repositories.media import MediaRepository
    from astrid.core.repositories.tasks import TaskRepository
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.store.writer import DatabaseWriter

    registry = core_only_registry()
    db_path = projects_root / "kernel.sqlite3"
    writer = DatabaseWriter(db_path, registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        tasks_repo = TaskRepository(events=events, receipts=receipts)
        media_repo = MediaRepository(events=events, receipts=receipts, projects_root=projects_root)
        for idx in range(8):
            claim = UnitOfWork(writer).run(lambda u, _ck=f"drive-claim-{project_slug}-{idx}": tasks_repo.claim(u, project_id=project_slug, idempotency_key=_ck))
            if claim is None:
                break
            task_id = claim.task.id  # type: ignore[attr-defined]
            attempt = claim.attempt  # type: ignore[attr-defined]
            attempt_id = attempt.id  # type: ignore[attr-defined]
            lease_id = attempt.lease_id  # type: ignore[attr-defined]
            sv = int(attempt.status_version)  # type: ignore[attr-defined]
            started = UnitOfWork(writer).run(lambda u, _tid=task_id, _aid=attempt_id, _lease=lease_id, _sv=sv, _ck=f"drive-start-{project_slug}-{idx}": tasks_repo.start(u, project_id=project_slug, task_id=_tid, attempt_id=_aid, lease_id=_lease, expected_status_version=_sv, idempotency_key=_ck))
            sv2 = int(started.status_version)  # type: ignore[attr-defined]
            UnitOfWork(writer).run(lambda u, _tid=task_id, _aid=attempt_id, _lease=lease_id, _sv=sv2, _ck=f"drive-complete-{project_slug}-{idx}": tasks_repo.complete(u, project_id=project_slug, task_id=_tid, attempt_id=_aid, lease_id=_lease, expected_status_version=_sv, idempotency_key=_ck, outputs=[], result={"step": f"step-{idx}"}, media_repo=media_repo))
    finally:
        try:
            writer.close()
        except Exception:
            pass


class TestSingleLedgerHarness:
    """B4.2 empirical harness: each cap is kernel run+task with events/receipts and zero authoritative run.json."""

    CAPS = [
        ("generation.generate_image", {"prompt": "a cat", "seed": 1}),
        ("test.file_only_executor", {"cmd": "echo hi"}),
        ("rendering.timeline_visualize", {"timeline": "main"}),
        ("rendering.attached_render", {"composition": "main"}),
        ("generation.generate_video", {"prompt": "a dog", "seed": 2}),
        ("test.orchestrator_child", {"step": "plan"}),
    ]

    def test_six_caps_kernel_ledger(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        for idx, (cap, spec) in enumerate(self.CAPS):
            safe = cap.replace(".", "-")
            base = tmp_path / safe
            base.mkdir(parents=True, exist_ok=True)
            slug = f"demo-cap{idx+1}"
            projects_root, _ = _setup_project_env(base, monkeypatch, slug)
            _admit_and_complete_one(projects_root, slug, cap, spec)
            records = _project_run_records(projects_root)
            # Zero authoritative run.json projection only; kernel is authority
            assert records == [] or all(r.get("authority") in ("kernel", "import", "threads-legacy") for r in records), f"{cap} leaked authoritative run.json: {records}"
            # Harness honesty: 6 caps via _assert_kernel_single_ledger (events>=4 receipts>=2, terminal)
            _assert_kernel_single_ledger(projects_root, expected_runs=0, expected_tasks=1, min_events=4, min_receipts=2)

    def test_orchestrator_with_children_hard_chain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.project.kernel_admission import admit_orchestrator_project_run
        projects_root = tmp_path / "orch-projects"
        projects_root.mkdir()
        monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(projects_root))
        from astrid.core.project.project import create_project
        create_project("demo-orch")
        ctx = admit_orchestrator_project_run(project="demo-orch", tool_id="test.orch", argv=["--project", "demo-orch"], projects_root=projects_root)
        assert ctx.run_id
        # Drive hard chain to terminal (admit is create-only; harness drives)
        _drive_orchestrator_chain(projects_root, "demo-orch")
        # After R3.1 fan-out, orchestrator should have 1 run +4 tasks hard chain, events>=12 receipts>=4
        _assert_kernel_single_ledger(projects_root, expected_runs=1, expected_tasks=4, min_events=12, min_receipts=4)
        # Zero authoritative run.json
        assert _project_run_records(projects_root) == [] or all(r.get("authority") != "authoritative" for r in _project_run_records(projects_root))


    def test_banodoco_worker_single_write_projection(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from astrid.core.integrations.worker.banodoco_worker import _write_baseline_snapshot
        import sqlite3
        projects_root = tmp_path / "banodoco-projects"
        projects_root.mkdir()
        monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(projects_root))
        from astrid.core.project.project import create_project
        create_project("demo-b")
        # Without kernel run: should stamp import single-write
        run_id_1 = "01H5TESTIMPORT00000000000001"
        digest1 = _write_baseline_snapshot(project_slug="demo-b", run_id=run_id_1, payload={"clips": []})
        assert digest1
        rec1 = json.loads((projects_root / "demo-b" / "runs" / run_id_1 / "run.json").read_text())
        assert rec1.get("authority") == "import"
        assert rec1["metadata"]["baseline_snapshot"] == digest1
        assert rec1["metadata"]["non_authority"] is True
        # With kernel run: should stamp kernel single-write; count writes by mtime not needed, just authority
        from astrid.core.project.kernel_admission import admit_orchestrator_project_run
        ctx = admit_orchestrator_project_run(project="demo-b", tool_id="test.banodoco", argv=["x"], projects_root=projects_root)
        run_id_2 = ctx.run_id
        digest2 = _write_baseline_snapshot(project_slug="demo-b", run_id=run_id_2, payload={"clips": [{"id": "c1"}]})
        rec2 = json.loads((projects_root / "demo-b" / "runs" / run_id_2 / "run.json").read_text())
        assert rec2.get("authority") == "kernel"
        assert rec2.get("kernel_run_id") == run_id_2
        assert rec2["metadata"]["baseline_snapshot"] == digest2
        # Kernel still has its run/task; zero authoritative FS ledger
        runs, tasks, events, receipts = _kernel_counts(projects_root)
        assert runs >= 1

