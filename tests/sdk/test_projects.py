"""Executable project SDK service tests (m4 plan step 5, task T6).

Proves ``astrid.sdk.projects.ProjectsService`` exposes repository-backed,
envelope-shaped ``create``/``list``/``show``/``update`` over the kernel
:class:`~astrid.core.repositories.projects.ProjectRepository`:

- the five-key envelope shape with the committed nine-key receipt on
  mutations and a null receipt on pure reads;
- caller keys preserved, generated keys returned and fresh, empty keys
  rejected as ``validation_error``;
- deterministic project ids derived from the idempotency key, so an
  identical retry replays the committed result with zero new rows and a
  changed request under the same key returns ``idempotency_mismatch``
  before any mutation;
- id/slug resolution for ``show``/``update``, typed ``not_found`` for a
  missing project, ``validation_error`` for a malformed address, and
  ``conflict`` for a duplicate slug;
- no filesystem project writes (the read model lives only in the kernel
  database).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core import preferences
from astrid.core.events.registry import core_only_registry
from astrid.core.events.service import EventAppendService
from astrid.core.receipts.service import ReceiptService
from astrid.core.repositories.projects import (
    CORE_PROJECT_CREATE_COMMAND_KIND,
    ProjectRepository,
)
from astrid.core.session import paths
from astrid.core.store.writer import DatabaseWriter
from astrid.sdk.contracts import derive_stable_id
from astrid.sdk.projects import ProjectsService

ENVELOPE_KEYS = {"ok", "data", "error", "receipt", "idempotency_key"}
RECEIPT_KEYS = {
    "receipt_id",
    "command_kind",
    "idempotency_key",
    "request_hash",
    "project_id",
    "project_seq",
    "event_ids",
    "result",
    "created_at",
}


@pytest.fixture
def env(tmp_path: Path):
    """A fresh kernel writer, project repository, and project service."""
    registry = core_only_registry()
    writer = DatabaseWriter(tmp_path / "projects.sqlite3", registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        yield SimpleNamespace(
            service=ProjectsService(writer, projects, receipts),
            writer=writer,
            root=tmp_path,
        )
    finally:
        writer.close()


def _project_count(env: SimpleNamespace) -> int:
    return env.writer.submit(
        lambda s: s.query_one("SELECT COUNT(*) FROM projects")[0]
    )


# ---------------------------------------------------------------------------
# Envelope and receipt shape
# ---------------------------------------------------------------------------


def test_create_envelope_has_exactly_five_keys(env: SimpleNamespace) -> None:
    result = env.service.create(slug="demo", name="Demo")
    assert result.ok is True
    assert set(result.as_dict().keys()) == ENVELOPE_KEYS
    assert result.error is None
    assert result.receipt is not None
    assert set(result.receipt.as_dict().keys()) == RECEIPT_KEYS
    assert result.receipt.command_kind == CORE_PROJECT_CREATE_COMMAND_KIND


def test_read_envelopes_carry_null_receipt_and_empty_key(
    env: SimpleNamespace,
) -> None:
    env.service.create(slug="demo", name="Demo")
    listed = env.service.list()
    shown = env.service.show("demo")
    for result in (listed, shown):
        assert result.ok is True
        assert result.receipt is None
        assert result.idempotency_key == ""


# ---------------------------------------------------------------------------
# Idempotency keys and deterministic ids
# ---------------------------------------------------------------------------


def test_caller_key_is_preserved_and_generated_key_is_fresh(
    env: SimpleNamespace,
) -> None:
    first = env.service.create(slug="one", name="One", idempotency_key="caller-1")
    second = env.service.create(slug="two", name="Two")
    assert first.idempotency_key == "caller-1"
    assert second.ok is True
    assert second.idempotency_key
    assert second.idempotency_key != first.idempotency_key


def test_empty_key_returns_validation_error_before_mutation(
    env: SimpleNamespace,
) -> None:
    result = env.service.create(slug="demo", name="Demo", idempotency_key="")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "validation_error"
    assert _project_count(env) == 0


def test_create_derives_deterministic_id_from_key(env: SimpleNamespace) -> None:
    expected = derive_stable_id(
        command_kind=CORE_PROJECT_CREATE_COMMAND_KIND,
        scope="global",
        idempotency_key="k-deterministic",
        ordinal=0,
    )
    result = env.service.create(
        slug="det", name="Det", idempotency_key="k-deterministic"
    )
    assert result.ok is True
    assert result.data["id"] == expected


# ---------------------------------------------------------------------------
# Replay and mismatch-before-mutation
# ---------------------------------------------------------------------------


def test_identical_retry_replays_with_zero_new_rows(env: SimpleNamespace) -> None:
    first = env.service.create(slug="demo", name="Demo", idempotency_key="k1")
    assert first.ok is True
    first_receipt_id = first.receipt.receipt_id
    assert _project_count(env) == 1

    second = env.service.create(slug="demo", name="Demo", idempotency_key="k1")
    assert second.ok is True
    assert second.data["id"] == first.data["id"]
    assert second.receipt.receipt_id == first_receipt_id
    assert second.receipt == first.receipt
    assert _project_count(env) == 1


def test_mismatch_returns_idempotency_mismatch_before_mutation(
    env: SimpleNamespace,
) -> None:
    first = env.service.create(slug="demo", name="Demo", idempotency_key="k1")
    assert first.ok is True

    changed = env.service.create(
        slug="demo", name="Different", idempotency_key="k1"
    )
    assert changed.ok is False
    assert changed.error is not None
    assert changed.error.code == "idempotency_mismatch"
    assert changed.idempotency_key == "k1"
    # No mutation happened: still exactly one project, name unchanged.
    assert _project_count(env) == 1
    shown = env.service.show("demo")
    assert shown.data["name"] == "Demo"


# ---------------------------------------------------------------------------
# List and show with id/slug resolution
# ---------------------------------------------------------------------------


def test_list_returns_slug_sorted_rows(env: SimpleNamespace) -> None:
    env.service.create(slug="zeta", name="Zeta")
    env.service.create(slug="alpha", name="Alpha")
    env.service.create(slug="beta", name="Beta")
    result = env.service.list()
    assert result.ok is True
    assert result.data == [
        {"slug": "alpha", "name": "Alpha"},
        {"slug": "beta", "name": "Beta"},
        {"slug": "zeta", "name": "Zeta"},
    ]


def test_show_resolves_by_id_and_by_slug(env: SimpleNamespace) -> None:
    created = env.service.create(slug="demo", name="Demo")
    project_id = created.data["id"]
    by_id = env.service.show(project_id)
    by_slug = env.service.show("demo")
    assert by_id.ok is True
    assert by_slug.ok is True
    assert by_id.data == by_slug.data == created.data


def test_show_missing_returns_not_found(env: SimpleNamespace) -> None:
    result = env.service.show("missing-project")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


def test_show_malformed_address_returns_validation_error(
    env: SimpleNamespace,
) -> None:
    result = env.service.show("Invalid Slug!")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "validation_error"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_merges_settings_and_returns_receipt(env: SimpleNamespace) -> None:
    created = env.service.create(slug="demo", name="Demo", settings={"a": 1})
    project_id = created.data["id"]

    updated = env.service.update(project_id, name="Demo 2", settings={"b": 2})
    assert updated.ok is True
    assert updated.receipt is not None
    assert updated.data["name"] == "Demo 2"
    assert updated.data["settings"]["a"] == 1
    assert updated.data["settings"]["b"] == 2

    shown = env.service.show("demo")
    assert shown.data["name"] == "Demo 2"
    assert shown.data["settings"] == {"a": 1, "b": 2}


def test_update_missing_returns_not_found(env: SimpleNamespace) -> None:
    result = env.service.update("missing", name="X")
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"


def test_update_by_slug_resolves_and_mutates(env: SimpleNamespace) -> None:
    env.service.create(slug="demo", name="Demo")
    updated = env.service.update("demo", name="Renamed", idempotency_key="u1")
    assert updated.ok is True
    assert updated.data["name"] == "Renamed"
    # Replay under the same key returns the same receipt with zero new rows.
    replay = env.service.update("demo", name="Renamed", idempotency_key="u1")
    assert replay.ok is True
    assert replay.receipt.receipt_id == updated.receipt.receipt_id


# ---------------------------------------------------------------------------
# Conflict and no-filesystem-write guarantees
# ---------------------------------------------------------------------------


def test_duplicate_slug_returns_conflict(env: SimpleNamespace) -> None:
    first = env.service.create(slug="demo", name="Demo")
    assert first.ok is True
    second = env.service.create(slug="demo", name="Another")
    assert second.ok is False
    assert second.error is not None
    assert second.error.code == "conflict"
    assert _project_count(env) == 1


def test_create_performs_no_filesystem_project_writes(
    env: SimpleNamespace,
) -> None:
    result = env.service.create(slug="demo", name="Demo")
    assert result.ok is True
    project_id = result.data["id"]
    # The project lives only in the kernel database: no project directory
    # and no project.json authority appear under the projects root.
    assert not (env.root / "demo").exists()
    assert not (env.root / project_id).exists()
    assert list(env.root.rglob("project.json")) == []


# ---------------------------------------------------------------------------
# Select: non-authoritative preference (m4 plan step 5, task T6B)
# ---------------------------------------------------------------------------


@pytest.fixture
def sandboxed_home(env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sandbox ASTRID_HOME so select's preference writes never leave tmp."""
    monkeypatch.setenv(paths.ASTRID_HOME_ENV, str(env.root / "home"))
    monkeypatch.delenv(paths.ASTRID_WORKSPACE_CONFIG_DIR_ENV, raising=False)
    return env.root / "ws"


def _receipt_and_event_counts(env: SimpleNamespace) -> tuple[int, int]:
    return env.writer.submit(
        lambda s: (
            s.query_one("SELECT COUNT(*) FROM command_receipts")[0],
            s.query_one("SELECT COUNT(*) FROM events")[0],
        )
    )


def test_select_resolves_by_slug_and_persists_default_project(
    env: SimpleNamespace, sandboxed_home: Path
) -> None:
    created = env.service.create(slug="demo", name="Demo")
    assert created.ok is True

    result = env.service.select("demo", cwd=sandboxed_home)
    assert result.ok is True
    # The resolved project is returned in the exact read-model envelope.
    assert result.data == created.data
    # Non-authoritative: no receipt and no idempotency key.
    assert result.receipt is None
    assert result.idempotency_key == ""

    # Only default_project was persisted, to the workspace scope, restart-
    # durable, and consumed by the same resolution helper a later
    # invocation uses (explicit > workspace > user).
    assert preferences.resolve_default_project(sandboxed_home) == "demo"


def test_select_resolves_by_id(env: SimpleNamespace, sandboxed_home: Path) -> None:
    created = env.service.create(slug="demo", name="Demo")
    result = env.service.select(created.data["id"], cwd=sandboxed_home)
    assert result.ok is True
    assert result.data["slug"] == "demo"
    assert preferences.resolve_default_project(sandboxed_home) == "demo"


def test_select_missing_returns_not_found_without_mutation(
    env: SimpleNamespace, sandboxed_home: Path
) -> None:
    before = _project_count(env)
    result = env.service.select("missing-project", cwd=sandboxed_home)
    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "not_found"
    assert _project_count(env) == before
    assert preferences.resolve_default_project(sandboxed_home) is None


def test_select_does_not_mutate_database(env: SimpleNamespace, sandboxed_home: Path) -> None:
    env.service.create(slug="demo", name="Demo")
    before_receipts, before_events = _receipt_and_event_counts(env)

    result = env.service.select("demo", cwd=sandboxed_home)
    assert result.ok is True

    # Selection is context resolution, not a receipted database mutation:
    # no receipt, no event, and the project row count is unchanged.
    assert _receipt_and_event_counts(env) == (before_receipts, before_events)
    assert _project_count(env) == 1


def test_select_persists_to_user_scope(env: SimpleNamespace, sandboxed_home: Path) -> None:
    env.service.create(slug="demo", name="Demo")
    result = env.service.select("demo", scope="user", cwd=sandboxed_home)
    assert result.ok is True
    # The workspace stays untouched; the user scope carries the default.
    assert preferences.resolve_default_project(sandboxed_home) == "demo"
    assert preferences.load_workspace_config(sandboxed_home) == {}
    assert preferences.load_user_config()["default_project"] == "demo"


def test_select_explicit_flag_wins_over_persisted_default(
    env: SimpleNamespace, sandboxed_home: Path
) -> None:
    env.service.create(slug="demo", name="Demo")
    env.service.create(slug="other", name="Other")
    env.service.select("demo", cwd=sandboxed_home)

    # A later invocation with an explicit option resolves that option even
    # though a workspace default was persisted by a prior select.
    assert preferences.resolve_default_project(sandboxed_home) == "demo"
    assert (
        preferences.resolve_default_project(sandboxed_home, explicit="other")
        == "other"
    )
