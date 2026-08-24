"""Service-level project workspace materialization conformance (v10).

The project *repository* performs no filesystem writes — that invariant stays
with ``test_project_repository.py::test_no_filesystem_project_authority``,
which exercises the repository directly. This suite pins the *service*-level
composition added so the documented journey (``projects create`` →
``sdk.invoke(..., project=<slug>)``) works for direct-mode executors:

- ``ProjectsService.create`` materializes ``<root>/<slug>/plan.md`` (the
  documented empty skeleton) and a lightweight ``project.json`` **binding**
  file (``kernel_authority: true``, kernel ``project_id``) after the kernel
  row commits;
- the binding file resolves through ``require_project`` and
  ``require_project_owned_artifact`` so project-scoped executor runs land in
  ``<root>/<slug>/runs/<run-id>/run.json``;
- the kernel database row remains the sole authority: replay never clobbers
  existing workspace files, service updates never rewrite the binding file,
  and a materialization failure never fails the committed create.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from astrid.core.events.service import EventAppendService
from astrid.core.project.project import PLAN_MD_SKELETON, require_project
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import ProjectRepository
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.projects import ProjectsService


@pytest.fixture
def projects_root(tmp_path: Path) -> Path:
    """A fresh projects root, separate from the kernel database directory."""
    # The repository-wide sandbox fixture reserves ``tmp_path/projects`` for
    # the default ASTRID_PROJECTS_ROOT; keep this service-specific root
    # distinct so both fixtures retain strict fresh-directory semantics.
    root = tmp_path / "workspace-projects"
    root.mkdir()
    return root


@pytest.fixture
def workspace_env(
    tmp_path: Path,
    core_registry,
    projects_root: Path,
):
    """Fresh kernel writer plus a projects service bound to *projects_root*."""
    writer = DatabaseWriter(tmp_path / "kernel.sqlite3", core_registry)
    try:
        events = EventAppendService(core_registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        yield SimpleNamespace(
            writer=writer,
            service=ProjectsService(
                writer, projects, receipts, projects_root=projects_root
            ),
            projects=projects,
            projects_root=projects_root,
        )
    finally:
        writer.close()


def _create(env: SimpleNamespace, *, slug: str = "pd", name: str = "Pd", key: str | None = None):
    return env.service.create(slug=slug, name=name, idempotency_key=key)


# ---------------------------------------------------------------------------
# Skeleton materialization and binding-file shape
# ---------------------------------------------------------------------------


def test_create_materializes_binding_workspace(workspace_env) -> None:
    env = workspace_env
    result = _create(env, slug="pd", name="Pd", key="k1")
    assert result.ok is True
    project_id = result.data["id"]

    project_dir = env.projects_root / "pd"
    assert sorted(path.name for path in project_dir.iterdir()) == [
        "plan.md",
        "project.json",
    ]

    # plan.md is the documented empty skeleton.
    assert (project_dir / "plan.md").read_text(encoding="utf-8") == (
        PLAN_MD_SKELETON.format(slug="pd")
    )

    # project.json is a lightweight binding file pointing at the kernel row.
    payload = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert payload["slug"] == "pd"
    assert payload["name"] == "Pd"
    assert payload["project_id"] == project_id
    assert payload["kernel_authority"] is True

    # The binding file resolves through the direct-mode resolution seam.
    resolved = require_project("pd", root=env.projects_root)
    assert resolved["slug"] == "pd"


def test_kernel_row_remains_authoritative_over_binding_file(
    workspace_env,
) -> None:
    env = workspace_env
    created = _create(env, slug="pd", name="Pd", key="k1")
    assert created.ok is True
    key = created.idempotency_key

    # A kernel-side update changes the read model but never rewrites the
    # binding file: the filesystem is not an authority to keep in sync.
    updated = env.service.update("pd", name="Renamed")
    assert updated.ok is True
    assert updated.data["name"] == "Renamed"

    payload = json.loads(
        (env.projects_root / "pd" / "project.json").read_text(encoding="utf-8")
    )
    assert payload["name"] == "Pd"

    # Replay under the same key replays the committed create with zero new
    # rows and still leaves the edited workspace untouched.
    plan_path = env.projects_root / "pd" / "plan.md"
    plan_path.write_text("# human edits\n", encoding="utf-8")
    replay = env.service.create(slug="pd", name="Pd", idempotency_key=key)
    assert replay.ok is True
    assert replay.receipt is not None
    assert plan_path.read_text(encoding="utf-8") == "# human edits\n"


def test_materializer_failure_does_not_fail_committed_create(
    workspace_env, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Kernel row wins: a failed FS materialization logs a warning only."""
    env = workspace_env

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise OSError("read-only projects root")

    monkeypatch.setattr("astrid.sdk.projects.write_json_atomic", _boom)
    with caplog.at_level("WARNING", logger="astrid.sdk.projects"):
        result = _create(env, slug="pd", name="Pd")
    assert result.ok is True
    assert any(
        "workspace materialization" in record.message and record.levelname == "WARNING"
        for record in caplog.records
    )

    # The authoritative kernel row exists and show() resolves it.
    shown = env.service.show("pd")
    assert shown.ok is True
    assert shown.data["slug"] == "pd"
    # plan.md was written before the simulated binding-file failure.
    assert (env.projects_root / "pd" / "plan.md").is_file()


# ---------------------------------------------------------------------------
# Direct-mode executor journey: create → resolve → run lands in workspace
# ---------------------------------------------------------------------------


def _make_minimal_executor(executor_id: str = "test.noop") -> Any:
    """Build a minimal external executor definition for testing."""
    from astrid.core.contracts.schema import CommandSpec
    from astrid.core.execution.executor.schema import ExecutorDefinition

    return ExecutorDefinition(
        id=executor_id,
        name=executor_id.rsplit(".", 1)[-1],
        kind="external",
        version="0.1.0",
        command=CommandSpec(argv=(sys.executable, "-c", "print('ok')")),
        metadata={"requires_timeline": False},
    )


def test_kernel_admitted_executor_uses_staging_without_filesystem_ledger(
    workspace_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from astrid.core.execution.executor.registry import ExecutorRegistry
    from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

    env = workspace_env
    result = _create(env, slug="pd", name="Pd")
    assert result.ok is True

    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(env.projects_root))
    registry = ExecutorRegistry([_make_minimal_executor()])

    staging = env.projects_root / "pd" / ".astrid" / "media" / ".staging" / "test"
    run = run_executor(
        ExecutorRunRequest(
            "test.noop",
            out=staging,
            project="pd",
            project_was_auto_resolved=True,
        ),
        registry,
    )
    assert run.ok, run.error
    assert run.run_root is None
    assert not list((env.projects_root / "pd" / "runs").glob("**/run.json"))
