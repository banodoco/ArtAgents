from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.project.current_run import write_current_run
from astrid.core.session import binding
from astrid.core.session import lifecycle
from astrid.core.session.lease import (
    LeaseError,
    read_lease,
    release_writer_lease,
    write_lease_init,
)
from astrid.core.session.model import (
    Session,
    SessionRecordMalformedError,
    SessionRecordNotFoundError,
    SessionStore,
)
from astrid.core.task.events import ZERO_HASH, append_event_locked, read_events


def _forbid_hidden_session_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    *,
    astrid_home: Path,
) -> None:
    def _fail_print(*args: object, **kwargs: object) -> None:
        raise AssertionError("explicit-root lifecycle helpers must not print")

    def _fail_input(prompt: str = "") -> str:
        raise AssertionError("explicit-root lifecycle helpers must not prompt")

    def _fail_astrid_home() -> Path:
        raise AssertionError("explicit-root lifecycle helpers must not consult ASTRID_HOME")

    def _fail_path_home() -> Path:
        raise AssertionError("explicit-root lifecycle helpers must not consult Path.home()")

    monkeypatch.setenv("ASTRID_HOME", str(astrid_home))
    monkeypatch.setattr("builtins.print", _fail_print)
    monkeypatch.setattr("builtins.input", _fail_input)
    monkeypatch.setattr("astrid.core.session.paths.astrid_home", _fail_astrid_home)
    monkeypatch.setattr("pathlib.Path.home", _fail_path_home)


def test_session_store_uses_explicit_root_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_root = tmp_path / "sdk-sessions"
    astrid_home = tmp_path / "astrid-home"
    monkeypatch.setenv("ASTRID_HOME", str(astrid_home))

    def _fail_astrid_home() -> Path:
        raise AssertionError("explicit-root storage must not consult ASTRID_HOME")

    def _fail_path_home() -> Path:
        raise AssertionError("explicit-root storage must not consult Path.home()")

    def _fail_input(prompt: str = "") -> str:
        raise AssertionError("explicit-root storage must not prompt")

    monkeypatch.setattr("astrid.core.session.paths.astrid_home", _fail_astrid_home)
    monkeypatch.setattr(
        "pathlib.Path.home",
        _fail_path_home,
    )
    monkeypatch.setattr("builtins.input", _fail_input)

    session = Session(
        id="S-ROOT",
        project="demo",
        agent_id="claude-1",
        attached_at="2026-06-01T00:00:00Z",
        last_used_at="2026-06-01T00:00:00Z",
        role="writer",
        timeline="primary",
        timeline_id="01TL",
        run_id="01RUN",
    )

    path = SessionStore(session_root=session_root).save(session)
    assert path == session_root / "S-ROOT.json"
    assert path.is_file()
    assert not astrid_home.exists()

    loaded = SessionStore(session_root=session_root).load("S-ROOT")
    assert loaded == session


def test_session_store_load_missing_raises_typed_error(tmp_path: Path) -> None:
    store = SessionStore(session_root=tmp_path / "sdk-sessions")
    with pytest.raises(SessionRecordNotFoundError, match="session record not found"):
        store.load("S-MISSING")


def test_session_store_load_malformed_raises_typed_error(tmp_path: Path) -> None:
    session_root = tmp_path / "sdk-sessions"
    session_root.mkdir(parents=True)
    (session_root / "S-BAD.json").write_text("{not-json}\n", encoding="utf-8")

    store = SessionStore(session_root=session_root)
    with pytest.raises(SessionRecordMalformedError, match="session record is malformed"):
        store.load("S-BAD")


def test_lifecycle_create_load_and_open_are_explicit_root_and_print_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_root = tmp_path / "sdk-sessions"

    def _fail_print(*args: object, **kwargs: object) -> None:
        raise AssertionError("explicit-root lifecycle helpers must not print")

    def _fail_input(prompt: str = "") -> str:
        raise AssertionError("explicit-root lifecycle helpers must not prompt")

    monkeypatch.setattr("builtins.print", _fail_print)
    monkeypatch.setattr("builtins.input", _fail_input)

    created = lifecycle.create_session(
        project_slug="demo",
        agent_id="claude-1",
        projects_root=tmp_path / "projects",
        session_root=session_root,
        session_id="S-LIFE",
        timeline="primary",
        timeline_id="01TL",
        attached_at="2026-06-01T00:00:00Z",
        last_used_at="2026-06-01T00:00:00Z",
    )
    assert created.id == "S-LIFE"
    assert created.role == "writer"
    assert created.run_id is None

    loaded = lifecycle.load_session("S-LIFE", session_root=session_root)
    assert loaded == created

    opened = lifecycle.open_session(
        "S-LIFE",
        project_slug="demo",
        agent_id="claude-1",
        projects_root=tmp_path / "projects",
        session_root=session_root,
        opened_at="2026-06-01T01:00:00Z",
    )
    assert opened.last_used_at == "2026-06-01T01:00:00Z"

    on_disk = json.loads((session_root / "S-LIFE.json").read_text(encoding="utf-8"))
    assert on_disk["last_used_at"] == "2026-06-01T01:00:00Z"


def test_lifecycle_derives_role_from_current_run_and_lease(
    tmp_path: Path,
) -> None:
    projects_root = tmp_path / "projects"
    session_root = tmp_path / "sessions"
    project_root = projects_root / "demo"
    run_dir = project_root / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    write_lease_init(run_dir, session_id="S-WRITER", plan_hash="")
    write_current_run("demo", "01RUN", root=projects_root)

    reader = lifecycle.create_session(
        project_slug="demo",
        agent_id="claude-1",
        projects_root=projects_root,
        session_root=session_root,
        session_id="S-READER",
        attached_at="2026-06-01T00:00:00Z",
    )
    assert reader.role == "reader"
    assert reader.run_id == "01RUN"

    writer = lifecycle.create_session(
        project_slug="demo",
        agent_id="claude-1",
        projects_root=projects_root,
        session_root=session_root,
        session_id="S-WRITER",
        attached_at="2026-06-01T00:00:00Z",
    )
    assert writer.role == "writer"
    assert writer.run_id == "01RUN"

    release_writer_lease(run_dir)
    orphan_pending = lifecycle.open_session(
        "S-READER",
        project_slug="demo",
        agent_id="claude-1",
        projects_root=projects_root,
        session_root=session_root,
        opened_at="2026-06-01T01:00:00Z",
    )
    assert orphan_pending.role == "orphan-pending"
    assert orphan_pending.run_id == "01RUN"


def test_lifecycle_missing_lease_behind_current_run_is_hard_error_without_session_write(
    tmp_path: Path,
) -> None:
    projects_root = tmp_path / "projects"
    session_root = tmp_path / "sessions"
    run_dir = projects_root / "demo" / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    write_current_run("demo", "01RUN", root=projects_root)

    with pytest.raises(LeaseError, match="missing lease"):
        lifecycle.create_session(
            project_slug="demo",
            agent_id="claude-1",
            projects_root=projects_root,
            session_root=session_root,
            session_id="S-NO-LEASE",
        )

    assert not (session_root / "S-NO-LEASE.json").exists()


def test_lifecycle_project_pointer_write_is_opt_in(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    session_root = tmp_path / "sessions"

    session = lifecycle.create_session(
        project_slug="demo",
        agent_id="claude-1",
        projects_root=projects_root,
        session_root=session_root,
        session_id="S-NO-POINTER",
    )
    pointer = projects_root / "demo" / binding.SESSION_FILE_NAME
    assert session.id == "S-NO-POINTER"
    assert not pointer.exists()

    opened = lifecycle.open_session(
        "S-NO-POINTER",
        project_slug="demo",
        agent_id="claude-1",
        projects_root=projects_root,
        session_root=session_root,
        write_project_pointer=True,
    )
    assert opened.id == "S-NO-POINTER"
    assert pointer.read_text(encoding="utf-8") == "ASTRID_SESSION_ID=S-NO-POINTER\n"


def test_binding_attach_session_is_prompt_free_and_returns_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projects_root = tmp_path / "projects"
    session_root = tmp_path / "sessions"

    def _fail_print(*args: object, **kwargs: object) -> None:
        raise AssertionError("attach_session must not print")

    def _fail_input(prompt: str = "") -> str:
        raise AssertionError("attach_session must not prompt")

    def _fail_path_home() -> Path:
        raise AssertionError("attach_session must not consult Path.home()")

    monkeypatch.setattr("builtins.print", _fail_print)
    monkeypatch.setattr("builtins.input", _fail_input)
    monkeypatch.setattr("pathlib.Path.home", _fail_path_home)

    attached = binding.attach_session(
        project_slug="demo",
        agent_id="claude-1",
        projects_root=projects_root,
        session_root=session_root,
        timeline="primary",
        timeline_id="01TL",
        attached_at="2026-06-01T00:00:00Z",
    )
    assert attached.mode == "created"
    session = attached.session
    assert session.timeline == "primary"
    assert session.timeline_id == "01TL"
    assert not (projects_root / "demo" / binding.SESSION_FILE_NAME).exists()

    reattached = binding.attach_session(
        project_slug="demo",
        agent_id="claude-1",
        projects_root=projects_root,
        session_root=session_root,
        session_id=session.id,
        opened_at="2026-06-01T01:00:00Z",
        write_project_pointer=True,
    )
    assert reattached.mode == "opened"
    reopened = reattached.session
    assert reopened.last_used_at == "2026-06-01T01:00:00Z"
    assert (
        projects_root / "demo" / binding.SESSION_FILE_NAME
    ).read_text(encoding="utf-8") == f"ASTRID_SESSION_ID={session.id}\n"


def test_lifecycle_takeover_live_target_is_prompt_free_and_force_controls_warmth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projects_root = tmp_path / "projects"
    session_root = tmp_path / "sessions"
    run_dir = projects_root / "demo" / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    write_lease_init(run_dir, session_id="S-OLD", plan_hash="plan-hash")
    write_current_run("demo", "01RUN", root=projects_root)
    append_event_locked(
        run_dir,
        {"kind": "seed", "i": 0},
        expected_writer_epoch=0,
        expected_prev_hash=ZERO_HASH,
    )
    caller = Session(
        id="S-NEW",
        project="demo",
        agent_id="claude-1",
        attached_at="2026-06-01T00:00:00Z",
        last_used_at="2026-06-01T00:00:00Z",
        role="reader",
        run_id="01RUN",
    )
    SessionStore(session_root=session_root).save(caller)
    before_lease = (run_dir / "lease.json").read_bytes()
    before_events = (run_dir / "events.jsonl").read_bytes()
    before_session = (session_root / "S-NEW.json").read_bytes()

    astrid_home = tmp_path / "astrid-home"
    _forbid_hidden_session_side_effects(monkeypatch, astrid_home=astrid_home)

    with pytest.raises(LeaseError, match="--force"):
        lifecycle.takeover_session(
            caller_session=caller,
            target="01RUN",
            projects_root=projects_root,
            session_root=session_root,
            force=False,
        )
    assert (run_dir / "lease.json").read_bytes() == before_lease
    assert (run_dir / "events.jsonl").read_bytes() == before_events
    assert (session_root / "S-NEW.json").read_bytes() == before_session

    result = lifecycle.takeover_session(
        caller_session=caller,
        target="01RUN",
        projects_root=projects_root,
        session_root=session_root,
        force=True,
        reason="test-force",
        taken_over_at="2026-06-01T01:00:00Z",
    )

    assert result.operation == "takeover"
    assert result.target.run_dir == run_dir
    assert result.lease["attached_session_id"] == "S-NEW"
    assert result.lease["writer_epoch"] == 1
    assert not (projects_root / "demo" / binding.SESSION_FILE_NAME).exists()
    assert not astrid_home.exists()
    promoted = lifecycle.load_session("S-NEW", session_root=session_root)
    assert promoted.role == "writer"
    assert promoted.run_id == "01RUN"
    assert promoted.last_used_at == "2026-06-01T01:00:00Z"
    takeover = read_events(run_dir / "events.jsonl")[-1]
    assert takeover["kind"] == "takeover"
    assert takeover["prev_session"] == "S-OLD"
    assert takeover["new_session"] == "S-NEW"
    assert takeover["reason"] == "test-force"


def test_lifecycle_recover_claims_current_run_orphan_lease_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projects_root = tmp_path / "projects"
    session_root = tmp_path / "sessions"
    run_dir = projects_root / "demo" / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    write_lease_init(run_dir, session_id="S-OLD", plan_hash="plan-hash")
    release_writer_lease(run_dir)
    write_current_run("demo", "01RUN", root=projects_root)
    caller = Session(
        id="S-CLAIM",
        project="demo",
        agent_id="claude-1",
        attached_at="2026-06-01T00:00:00Z",
        last_used_at="2026-06-01T00:00:00Z",
        role="orphan-pending",
        run_id="01RUN",
    )

    original_save = lifecycle.SessionStore.save
    lease_was_mutated_before_session_save: list[bool] = []
    astrid_home = tmp_path / "astrid-home"

    _forbid_hidden_session_side_effects(monkeypatch, astrid_home=astrid_home)

    def _save_spy(self: SessionStore, session: Session) -> Path:
        lease_was_mutated_before_session_save.append(
            read_lease(run_dir)["attached_session_id"] == session.id
        )
        return original_save(self, session)

    monkeypatch.setattr(lifecycle.SessionStore, "save", _save_spy)
    result = lifecycle.recover_session(
        caller_session=caller,
        projects_root=projects_root,
        session_root=session_root,
        recovered_at="2026-06-01T01:00:00Z",
        write_project_pointer=True,
    )

    assert result.operation == "orphan-claim"
    assert result.lease["attached_session_id"] == "S-CLAIM"
    assert result.lease["writer_epoch"] == 1
    assert lease_was_mutated_before_session_save == [True]
    assert (
        projects_root / "demo" / binding.SESSION_FILE_NAME
    ).read_text(encoding="utf-8") == "ASTRID_SESSION_ID=S-CLAIM\n"
    assert not astrid_home.exists()
    takeover = read_events(run_dir / "events.jsonl")[-1]
    assert takeover["kind"] == "takeover"
    assert takeover["prev_session"] is None
    assert takeover["new_session"] == "S-CLAIM"
    assert takeover["reason"] == "orphan-claim"


def test_lifecycle_recover_targets_current_run_pointer_over_stale_session_run_id(
    tmp_path: Path,
) -> None:
    projects_root = tmp_path / "projects"
    session_root = tmp_path / "sessions"
    stale_run_dir = projects_root / "demo" / "runs" / "01STALE"
    current_run_dir = projects_root / "demo" / "runs" / "01CURRENT"
    stale_run_dir.mkdir(parents=True)
    current_run_dir.mkdir(parents=True)
    write_lease_init(stale_run_dir, session_id="S-STALE-WRITER", plan_hash="stale")
    write_lease_init(current_run_dir, session_id="S-CURRENT-WRITER", plan_hash="current")
    release_writer_lease(current_run_dir)
    write_current_run("demo", "01CURRENT", root=projects_root)
    caller = Session(
        id="S-CLAIM",
        project="demo",
        agent_id="claude-1",
        attached_at="2026-06-01T00:00:00Z",
        last_used_at="2026-06-01T00:00:00Z",
        role="reader",
        run_id="01STALE",
    )

    result = lifecycle.recover_session(
        caller_session=caller,
        projects_root=projects_root,
        session_root=session_root,
        recovered_at="2026-06-01T01:00:00Z",
    )

    assert result.target.run_id == "01CURRENT"
    assert result.lease["attached_session_id"] == "S-CLAIM"
    assert read_lease(stale_run_dir)["attached_session_id"] == "S-STALE-WRITER"
    promoted = lifecycle.load_session("S-CLAIM", session_root=session_root)
    assert promoted.run_id == "01CURRENT"
    assert promoted.role == "writer"


def test_lifecycle_takeover_missing_target_fails_without_session_or_run_mutation(
    tmp_path: Path,
) -> None:
    projects_root = tmp_path / "projects"
    session_root = tmp_path / "sessions"
    run_dir = projects_root / "demo" / "runs" / "01RUN"
    run_dir.mkdir(parents=True)
    write_lease_init(run_dir, session_id="S-OLD", plan_hash="plan-hash")
    append_event_locked(
        run_dir,
        {"kind": "seed", "i": 0},
        expected_writer_epoch=0,
        expected_prev_hash=ZERO_HASH,
    )
    caller = Session(
        id="S-NEW",
        project="demo",
        agent_id="claude-1",
        attached_at="2026-06-01T00:00:00Z",
        last_used_at="2026-06-01T00:00:00Z",
        role="reader",
        run_id="01RUN",
    )
    SessionStore(session_root=session_root).save(caller)
    before_lease = (run_dir / "lease.json").read_bytes()
    before_events = (run_dir / "events.jsonl").read_bytes()
    before_session = (session_root / "S-NEW.json").read_bytes()

    with pytest.raises(lifecycle.SessionTakeoverTargetError, match="does not exist"):
        lifecycle.takeover_session(
            caller_session=caller,
            target="MISSING",
            projects_root=projects_root,
            session_root=session_root,
            force=True,
        )

    assert (run_dir / "lease.json").read_bytes() == before_lease
    assert (run_dir / "events.jsonl").read_bytes() == before_events
    assert (session_root / "S-NEW.json").read_bytes() == before_session
