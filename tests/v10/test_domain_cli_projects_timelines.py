"""Product CLI family tests: projects and timelines (m4 plan steps 25–26).

Task T27 (plan step 25) proves the ``projects`` product family
(``astrid/core/cli/domain_projects.py``): every verb makes **exactly one
SDK call**, returns exact envelopes and keys, persists ``select`` as the
non-authoritative preference, and provides executable help.

Task T28 (plan step 26) proves the ``timelines`` product family
(``astrid/packs/timeline/cli.py``): exactly the seven planned m4 verbs
(plus the S1 cutover verb ``backfill``) are reachable through one-call SDK
adapters, legacy aliases and migration/push/pull/sync/audit/erase/repair
are absent, ``copy`` is absent (deferred past m6), all help is executable,
and the gateway
dispatch routes every timelines verb through the product boundary
(m6 teardown removed the legacy timeline CLI and its fallback).

Task T29 (plan step 26 nested shots) proves the manifest-declared nested
``shots`` mount (``astrid/packs/shots/cli.py``): shot
``list/create/add/remove/reorder`` are executable **only** beneath
``timelines`` (``astrid timelines shots <verb>``), each verb is one SDK
call routed through the shot service, there is **no top-level shots
family**, and the canonical entrypoint behavior is retained (the product
parser installs no entrypoint guard; see ``tests/test_canonical_entrypoint.py``).
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import pytest

from astrid.core.cli.domain_product import run_product_family
from astrid.sdk.contracts import CommandReceipt, DomainResult, ErrorObject

ENVELOPE_KEYS = {"ok", "data", "error", "receipt", "idempotency_key"}


def _receipt(command_kind: str, key: str) -> CommandReceipt:
    return CommandReceipt(
        receipt_id=f"R-{command_kind}",
        command_kind=command_kind,
        idempotency_key=key,
        request_hash="hash",
        project_id="P-1",
        project_seq=(1, 1),
        event_ids=("E-1",),
        result={"ok": True},
        created_at="2026-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Recording fake client (one call per service method, canned envelopes)
# ---------------------------------------------------------------------------


class _RecordingProjects:
    def __init__(self, owner: "_FakeClient") -> None:
        self._owner = owner

    def create(self, *, slug, name, settings=None, idempotency_key=None):
        self._owner.calls.append(
            (
                "projects.create",
                {
                    "slug": slug,
                    "name": name,
                    "settings": settings,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"slug": slug, "name": name, "project_id": "P-1"},
            receipt=_receipt("project.create", key),
            idempotency_key=key,
        )

    def list(self):
        self._owner.calls.append(("projects.list", {}))
        return DomainResult.success([{"slug": "demo", "name": "Demo"}])

    def show(self, ref):
        self._owner.calls.append(("projects.show", {"ref": ref}))
        return DomainResult.success({"slug": ref, "name": "Demo", "project_id": "P-1"})

    def update(self, ref, *, name=None, settings=None, idempotency_key=None):
        self._owner.calls.append(
            (
                "projects.update",
                {
                    "ref": ref,
                    "name": name,
                    "settings": settings,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"slug": ref, "name": name or "Demo"},
            receipt=_receipt("project.update", key),
            idempotency_key=key,
        )

    def select(self, ref, *, scope="workspace", cwd=None):
        self._owner.calls.append(
            ("projects.select", {"ref": ref, "scope": scope, "cwd": cwd})
        )
        return DomainResult.success({"slug": ref, "name": "Demo", "project_id": "P-1"})


class _RecordingTimelines:
    def __init__(self, owner: "_FakeClient") -> None:
        self._owner = owner

    def create(
        self,
        *,
        project,
        slug,
        name,
        config=None,
        registry=None,
        set_default=False,
        idempotency_key=None,
    ):
        self._owner.calls.append(
            (
                "timelines.create",
                {
                    "project": project,
                    "slug": slug,
                    "name": name,
                    "config": config,
                    "registry": registry,
                    "set_default": set_default,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"slug": slug, "name": name, "timeline_id": "T-1"},
            receipt=_receipt("timeline.create", key),
            idempotency_key=key,
        )

    def list(self, project):
        self._owner.calls.append(("timelines.list", {"project": project}))
        return DomainResult.success([{"slug": "main", "name": "Main"}])

    def show(self, project, ref):
        self._owner.calls.append(("timelines.show", {"project": project, "ref": ref}))
        return DomainResult.success(
            {"slug": ref, "name": "Main", "timeline_id": "T-1"}
        )

    def save(
        self,
        project,
        ref,
        *,
        config,
        registry,
        expected_version,
        idempotency_key=None,
    ):
        self._owner.calls.append(
            (
                "timelines.save",
                {
                    "project": project,
                    "ref": ref,
                    "config": config,
                    "registry": registry,
                    "expected_version": expected_version,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"slug": ref, "timeline_id": "T-1", "version": expected_version + 1},
            receipt=_receipt("timeline.save", key),
            idempotency_key=key,
        )

    def archive(self, project, ref, *, idempotency_key=None):
        self._owner.calls.append(
            (
                "timelines.archive",
                {"project": project, "ref": ref, "idempotency_key": idempotency_key},
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"slug": ref, "timeline_id": "T-1", "archived": True},
            receipt=_receipt("timeline.archive", key),
            idempotency_key=key,
        )

    def history(self, project, ref):
        self._owner.calls.append(("timelines.history", {"project": project, "ref": ref}))
        return DomainResult.success([{"event": "timeline.created", "version": 1}])

    def diff(self, project, ref):
        self._owner.calls.append(("timelines.diff", {"project": project, "ref": ref}))
        return DomainResult.success([{"version": 1, "changes": {}}])


class _RecordingShots:
    def __init__(self, owner: "_FakeClient") -> None:
        self._owner = owner

    def list(self, project):
        self._owner.calls.append(("shots.list", {"project": project}))
        return DomainResult.success([{"id": "S-1", "name": "Opening"}])

    def create(self, *, project, name, metadata=None, idempotency_key=None):
        self._owner.calls.append(
            (
                "shots.create",
                {
                    "project": project,
                    "name": name,
                    "metadata": metadata,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"id": "S-1", "project_id": "P-1", "name": name},
            receipt=_receipt("shot.create", key),
            idempotency_key=key,
        )

    def add_item(
        self,
        project,
        shot_id,
        *,
        media_id,
        position=None,
        source_frame=None,
        metadata=None,
        idempotency_key=None,
    ):
        self._owner.calls.append(
            (
                "shots.add_item",
                {
                    "project": project,
                    "shot_id": shot_id,
                    "media_id": media_id,
                    "position": position,
                    "source_frame": source_frame,
                    "metadata": metadata,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"id": "S-1", "items": [{"item_id": "I-1", "media_id": media_id}]},
            receipt=_receipt("shot.add_item", key),
            idempotency_key=key,
        )

    def remove_item(self, project, shot_id, item_id, *, idempotency_key=None):
        self._owner.calls.append(
            (
                "shots.remove_item",
                {
                    "project": project,
                    "shot_id": shot_id,
                    "item_id": item_id,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"id": "S-1", "items": []},
            receipt=_receipt("shot.remove_item", key),
            idempotency_key=key,
        )

    def reorder(self, project, shot_id, item_ids, *, idempotency_key=None):
        self._owner.calls.append(
            (
                "shots.reorder",
                {
                    "project": project,
                    "shot_id": shot_id,
                    "item_ids": list(item_ids),
                    "idempotency_key": idempotency_key,
                },
            )
        )
        key = idempotency_key or "generated-key"
        return DomainResult.success(
            {"id": "S-1", "items": [{"item_id": i} for i in item_ids]},
            receipt=_receipt("shot.reorder", key),
            idempotency_key=key,
        )


class _FakeClient:
    """Minimal AstridClient stand-in: records every SDK call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.projects = _RecordingProjects(self)
        self.timelines = _RecordingTimelines(self)
        self.shots = _RecordingShots(self)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _run(family: str, args: list[str], client: _FakeClient | None = None) -> int:
    return run_product_family(family, args, client=client or _FakeClient())


def _subparser_choices(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("parser has no subparsers")


# ---------------------------------------------------------------------------
# T27 — projects family
# ---------------------------------------------------------------------------


def test_projects_parser_has_exactly_five_verbs() -> None:
    from astrid.core.cli.domain_projects import COMMANDS, build_parser

    assert tuple(spec.name for spec in COMMANDS) == (
        "create",
        "list",
        "show",
        "update",
        "select",
    )
    assert _subparser_choices(build_parser(_FakeClient())) == {
        "create",
        "list",
        "show",
        "update",
        "select",
    }


def test_projects_create_is_one_sdk_call_with_exact_envelope(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "projects",
        ["create", "demo", "--name", "Demo", "--json"],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        (
            "projects.create",
            {
                "slug": "demo",
                "name": "Demo",
                "settings": None,
                "idempotency_key": None,
            },
        )
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["ok"] is True
    assert envelope["data"]["slug"] == "demo"
    assert envelope["receipt"]["command_kind"] == "project.create"
    assert envelope["idempotency_key"] == "generated-key"


def test_projects_create_forwards_caller_key_and_settings(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "projects",
        [
            "create",
            "demo",
            "--name",
            "Demo",
            "--settings",
            '{"owner": "team"}',
            "--idempotency-key",
            "caller-key",
            "--json",
        ],
        client=client,
    )
    assert rc == 0
    (verb, kwargs) = client.calls[0]
    assert verb == "projects.create"
    assert kwargs["settings"] == {"owner": "team"}
    assert kwargs["idempotency_key"] == "caller-key"
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["idempotency_key"] == "caller-key"


def test_projects_list_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run("projects", ["list", "--json"], client=client)
    assert rc == 0
    assert client.calls == [("projects.list", {})]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["data"] == [{"slug": "demo", "name": "Demo"}]
    assert envelope["receipt"] is None
    assert envelope["idempotency_key"] == ""


def test_projects_show_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run("projects", ["show", "demo"], client=client)
    assert rc == 0
    assert client.calls == [("projects.show", {"ref": "demo"})]
    out = capsys.readouterr().out
    assert out == "slug: demo\n"


def test_projects_update_is_one_sdk_call_with_delta_and_key(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "projects",
        [
            "update",
            "demo",
            "--name",
            "Renamed",
            "--idempotency-key",
            "upd-key",
            "--json",
        ],
        client=client,
    )
    assert rc == 0
    (verb, kwargs) = client.calls[0]
    assert verb == "projects.update"
    assert kwargs == {
        "ref": "demo",
        "name": "Renamed",
        "settings": None,
        "idempotency_key": "upd-key",
    }
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["idempotency_key"] == "upd-key"


def test_projects_select_is_one_sdk_call_persisting_preference() -> None:
    client = _FakeClient()
    rc = _run("projects", ["select", "demo"], client=client)
    assert rc == 0
    assert client.calls == [
        ("projects.select", {"ref": "demo", "scope": "workspace", "cwd": None})
    ]


def test_projects_select_scope_user_is_forwarded() -> None:
    client = _FakeClient()
    rc = _run(
        "projects", ["select", "demo", "--scope", "user", "--json"], client=client
    )
    assert rc == 0
    assert client.calls == [
        ("projects.select", {"ref": "demo", "scope": "user", "cwd": None})
    ]


def test_projects_failure_envelope_exits_one(capsys) -> None:
    class _FailingProjects(_RecordingProjects):
        def show(self, ref):
            self._owner.calls.append(("projects.show", {"ref": ref}))
            return DomainResult.failure(
                ErrorObject(code="not_found", message="missing", details={})
            )

    class _FailingClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.projects = _FailingProjects(self)

    client = _FailingClient()
    rc = _run("projects", ["show", "nope"], client=client)
    assert rc == 1
    assert len(client.calls) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error not_found: missing\n"


def test_projects_unknown_verb_is_a_usage_error() -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("projects", ["export", "demo"], client=client)
    assert excinfo.value.code == 2
    assert client.calls == []


def test_projects_malformed_settings_is_a_usage_error() -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run(
            "projects",
            ["create", "demo", "--name", "Demo", "--settings", "not-json"],
            client=client,
        )
    assert excinfo.value.code == 2
    assert client.calls == []


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["create", "--help"],
        ["list", "--help"],
        ["show", "--help"],
        ["update", "--help"],
        ["select", "--help"],
    ],
)
def test_projects_help_is_executable(argv: list[str]) -> None:
    from astrid.core.cli.domain_projects import build_parser

    parser = build_parser(_FakeClient())
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(argv)
    assert excinfo.value.code == 0


# ---------------------------------------------------------------------------
# T28 — timelines family
# ---------------------------------------------------------------------------


def test_timelines_parser_has_exactly_eight_verbs_and_no_aliases() -> None:
    from astrid.packs.timeline.cli import COMMANDS, build_parser

    # S1 added the cutover verb ``backfill`` (SQLite backfill of JSONL /
    # Supabase-export timelines) to the seven m4 product verbs; it is the
    # one NEW product verb for the recorded cutover, deliberately distinct
    # from the retired legacy migration/push/pull/sync verbs.
    assert tuple(spec.name for spec in COMMANDS) == (
        "create",
        "list",
        "show",
        "save",
        "archive",
        "history",
        "diff",
        "backfill",
    )
    assert all(spec.aliases == () for spec in COMMANDS)
    # The parser registers exactly the eight timeline verbs plus the
    # manifest-declared nested ``shots`` mount (task T29).
    assert _subparser_choices(build_parser(_FakeClient())) == {
        "create",
        "list",
        "show",
        "save",
        "archive",
        "history",
        "diff",
        "backfill",
        "shots",
    }


@pytest.mark.parametrize(
    "forbidden",
    [
        "copy",
        "migrate",
        "migration",
        "push",
        "pull",
        "sync",
        "audit",
        "erase",
        "repair",
        "ls",
        "visualize",
    ],
)
def test_timelines_forbidden_and_legacy_verbs_are_absent(forbidden: str) -> None:
    from astrid.packs.timeline.cli import build_parser

    parser = build_parser(_FakeClient())
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args([forbidden])
    assert excinfo.value.code == 2


def test_timelines_create_is_one_sdk_call_with_exact_envelope(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "timelines",
        [
            "create",
            "--project",
            "demo",
            "main",
            "--name",
            "Main",
            "--config",
            '{"fps": 24}',
            "--registry",
            '{"assets": []}',
            "--default",
            "--json",
        ],
        client=client,
    )
    assert rc == 0
    (verb, kwargs) = client.calls[0]
    assert verb == "timelines.create"
    assert kwargs == {
        "project": "demo",
        "slug": "main",
        "name": "Main",
        "config": {"fps": 24},
        "registry": {"assets": []},
        "set_default": True,
        "idempotency_key": None,
    }
    envelope = json.loads(capsys.readouterr().out)
    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["ok"] is True
    assert envelope["receipt"]["command_kind"] == "timeline.create"
    assert envelope["idempotency_key"] == "generated-key"


def test_timelines_create_forwards_caller_key() -> None:
    client = _FakeClient()
    rc = _run(
        "timelines",
        [
            "create",
            "--project",
            "demo",
            "main",
            "--name",
            "Main",
            "--idempotency-key",
            "tl-key",
        ],
        client=client,
    )
    assert rc == 0
    assert client.calls[0][1]["idempotency_key"] == "tl-key"


def test_timelines_list_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run("timelines", ["list", "--project", "demo", "--json"], client=client)
    assert rc == 0
    assert client.calls == [("timelines.list", {"project": "demo"})]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["data"] == [{"slug": "main", "name": "Main"}]


def test_timelines_show_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run("timelines", ["show", "--project", "demo", "main"], client=client)
    assert rc == 0
    assert client.calls == [
        ("timelines.show", {"project": "demo", "ref": "main"})
    ]
    assert capsys.readouterr().out == "slug: main\n"


def test_timelines_save_is_one_sdk_call_with_cas_args(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "timelines",
        [
            "save",
            "--project",
            "demo",
            "main",
            "--config",
            '{"fps": 30}',
            "--registry",
            '{"assets": ["A1"]}',
            "--expected-version",
            "2",
            "--idempotency-key",
            "save-key",
            "--json",
        ],
        client=client,
    )
    assert rc == 0
    (verb, kwargs) = client.calls[0]
    assert verb == "timelines.save"
    assert kwargs == {
        "project": "demo",
        "ref": "main",
        "config": {"fps": 30},
        "registry": {"assets": ["A1"]},
        "expected_version": 2,
        "idempotency_key": "save-key",
    }
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["data"]["version"] == 3
    assert envelope["idempotency_key"] == "save-key"


def test_timelines_archive_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "timelines",
        ["archive", "--project", "demo", "main", "--json"],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        (
            "timelines.archive",
            {"project": "demo", "ref": "main", "idempotency_key": None},
        )
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["data"]["archived"] is True


def test_timelines_history_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run("timelines", ["history", "--project", "demo", "main"], client=client)
    assert rc == 0
    assert client.calls == [
        ("timelines.history", {"project": "demo", "ref": "main"})
    ]
    assert capsys.readouterr().out == "1 result(s)\n"


def test_timelines_diff_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run("timelines", ["diff", "--project", "demo", "main"], client=client)
    assert rc == 0
    assert client.calls == [
        ("timelines.diff", {"project": "demo", "ref": "main"})
    ]
    assert capsys.readouterr().out == "1 result(s)\n"


def test_timelines_save_stale_version_failure_exits_one(capsys) -> None:
    class _StaleTimelines(_RecordingTimelines):
        def save(
            self,
            project,
            ref,
            *,
            config,
            registry,
            expected_version,
            idempotency_key=None,
        ):
            self._owner.calls.append(("timelines.save", {"ref": ref}))
            return DomainResult.failure(
                ErrorObject(
                    code="stale_version",
                    message="expected head 2 but head is 3",
                    details={"expected_version": expected_version},
                ),
                idempotency_key=idempotency_key or "generated-key",
            )

    class _StaleClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.timelines = _StaleTimelines(self)

    client = _StaleClient()
    rc = _run(
        "timelines",
        [
            "save",
            "--project",
            "demo",
            "main",
            "--config",
            "{}",
            "--registry",
            "{}",
            "--expected-version",
            "2",
            "--json",
        ],
        client=client,
    )
    assert rc == 1
    assert len(client.calls) == 1
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "stale_version"
    assert captured.err == ""


def test_timelines_save_missing_required_cas_args_is_a_usage_error() -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run(
            "timelines",
            ["save", "--project", "demo", "main"],
            client=client,
        )
    assert excinfo.value.code == 2
    assert client.calls == []


@pytest.mark.parametrize(
    "argv",
    [
        ["--help"],
        ["create", "--help"],
        ["list", "--help"],
        ["show", "--help"],
        ["save", "--help"],
        ["archive", "--help"],
        ["history", "--help"],
        ["diff", "--help"],
    ],
)
def test_timelines_help_is_executable(argv: list[str]) -> None:
    from astrid.packs.timeline.cli import build_parser

    parser = build_parser(_FakeClient())
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(argv)
    assert excinfo.value.code == 0


# ---------------------------------------------------------------------------
# T28 — gateway dispatch cutover for the timelines family
# ---------------------------------------------------------------------------


def test_dispatch_timelines_routes_product_verbs_through_product_dispatch(
    monkeypatch,
) -> None:
    from astrid.core.gateway import dispatch

    seen: dict[str, object] = {}

    def _fake_product(args):  # noqa: ANN001
        seen["args"] = list(args)
        return 7

    monkeypatch.setattr(dispatch, "_dispatch_product", _fake_product)
    assert dispatch._dispatch_timelines(["create", "--project", "demo", "main"]) == 7
    assert seen["args"] == ["timelines", "create", "--project", "demo", "main"]


def test_dispatch_timelines_has_no_legacy_cli_fallback(monkeypatch) -> None:
    """m6 teardown: every timelines route goes through the product boundary.

    ``astrid.core.cli.timeline`` is deleted, so there is no legacy CLI to
    fall back to — even a formerly-legacy verb (e.g. ``visualize``) is
    forwarded to ``_dispatch_product`` (the family parser rejects it).
    """
    from astrid.core.gateway import dispatch

    seen: dict[str, object] = {}

    def _fake_product(args):  # noqa: ANN001
        seen["args"] = list(args)
        return 3

    monkeypatch.setattr(dispatch, "_dispatch_product", _fake_product)
    assert dispatch._dispatch_timelines(["visualize", "--project", "demo"]) == 3
    assert seen["args"] == ["timelines", "visualize", "--project", "demo"]

    # The legacy timeline CLI module no longer exists anywhere in the tree.
    import importlib

    with pytest.raises(ImportError):
        importlib.import_module("astrid.core.cli.timeline")


# ---------------------------------------------------------------------------
# T29 — nested shots family beneath timelines
# ---------------------------------------------------------------------------


def test_shots_parser_has_exactly_five_verbs_beneath_timelines() -> None:
    from astrid.packs.shots.cli import COMMANDS, build_parser

    assert tuple(spec.name for spec in COMMANDS) == (
        "list",
        "create",
        "add",
        "remove",
        "reorder",
    )
    assert all(spec.aliases == () for spec in COMMANDS)
    parser = build_parser(_FakeClient())
    assert parser.prog == "astrid timelines shots"
    assert _subparser_choices(parser) == {
        "list",
        "create",
        "add",
        "remove",
        "reorder",
    }


def test_no_top_level_shots_family() -> None:
    """shots is not a product family: product dispatch rejects it."""
    from astrid.core.cli.domain_product import (
        PRODUCT_FAMILY_SET,
        ProductRegistryError,
        is_product_family,
    )
    from astrid.core.gateway import dispatch

    assert "shots" not in PRODUCT_FAMILY_SET
    assert not is_product_family("shots")
    assert "shots" not in dispatch._top_level_commands()
    client = _FakeClient()
    with pytest.raises(ProductRegistryError, match="not a product family"):
        _run("shots", ["list", "--project", "demo"], client=client)
    assert client.calls == []


def test_timelines_shots_routes_beneath_timelines_parser(capsys) -> None:
    """``timelines shots`` is reachable only through the timelines parser."""
    client = _FakeClient()
    rc = _run(
        "timelines",
        ["shots", "list", "--project", "demo", "--json"],
        client=client,
    )
    assert rc == 0
    assert client.calls == [("shots.list", {"project": "demo"})]
    envelope = json.loads(capsys.readouterr().out)
    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["ok"] is True


def test_shots_create_is_one_sdk_call_with_exact_envelope(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "timelines",
        [
            "shots",
            "create",
            "--project",
            "demo",
            "--name",
            "Opening",
            "--metadata",
            '{"take": 1}',
            "--json",
        ],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        (
            "shots.create",
            {
                "project": "demo",
                "name": "Opening",
                "metadata": {"take": 1},
                "idempotency_key": None,
            },
        )
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["ok"] is True
    assert envelope["data"]["id"] == "S-1"
    assert envelope["receipt"]["command_kind"] == "shot.create"
    assert envelope["idempotency_key"] == "generated-key"


def test_shots_create_forwards_caller_key() -> None:
    client = _FakeClient()
    rc = _run(
        "timelines",
        [
            "shots",
            "create",
            "--project",
            "demo",
            "--name",
            "Opening",
            "--idempotency-key",
            "shot-key",
        ],
        client=client,
    )
    assert rc == 0
    assert client.calls[0][1]["idempotency_key"] == "shot-key"


def test_shots_add_is_one_sdk_call_with_media_position_and_key(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "timelines",
        [
            "shots",
            "add",
            "--project",
            "demo",
            "S-1",
            "--media",
            "M-1",
            "--position",
            "0",
            "--source-frame",
            "12",
            "--idempotency-key",
            "add-key",
            "--json",
        ],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        (
            "shots.add_item",
            {
                "project": "demo",
                "shot_id": "S-1",
                "media_id": "M-1",
                "position": 0,
                "source_frame": 12,
                "metadata": None,
                "idempotency_key": "add-key",
            },
        )
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["receipt"]["command_kind"] == "shot.add_item"
    assert envelope["idempotency_key"] == "add-key"


def test_shots_add_requires_media() -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("timelines", ["shots", "add", "--project", "demo", "S-1"], client=client)
    assert excinfo.value.code == 2
    assert client.calls == []


def test_shots_remove_is_one_sdk_call(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "timelines",
        ["shots", "remove", "--project", "demo", "S-1", "I-1", "--json"],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        (
            "shots.remove_item",
            {
                "project": "demo",
                "shot_id": "S-1",
                "item_id": "I-1",
                "idempotency_key": None,
            },
        )
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["receipt"]["command_kind"] == "shot.remove_item"


def test_shots_reorder_is_one_sdk_call_with_item_permutation(capsys) -> None:
    client = _FakeClient()
    rc = _run(
        "timelines",
        [
            "shots",
            "reorder",
            "--project",
            "demo",
            "S-1",
            "--items",
            "I-2,I-1",
            "--items",
            "I-3",
            "--json",
        ],
        client=client,
    )
    assert rc == 0
    assert client.calls == [
        (
            "shots.reorder",
            {
                "project": "demo",
                "shot_id": "S-1",
                "item_ids": ["I-2", "I-1", "I-3"],
                "idempotency_key": None,
            },
        )
    ]
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["receipt"]["command_kind"] == "shot.reorder"


def test_shots_reorder_requires_items() -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("timelines", ["shots", "reorder", "--project", "demo", "S-1"], client=client)
    assert excinfo.value.code == 2
    assert client.calls == []


def test_shots_failure_envelope_exits_one(capsys) -> None:
    class _FailingShots(_RecordingShots):
        def list(self, project):
            self._owner.calls.append(("shots.list", {"project": project}))
            return DomainResult.failure(
                ErrorObject(code="not_found", message="missing", details={})
            )

    class _FailingClient(_FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.shots = _FailingShots(self)

    client = _FailingClient()
    rc = _run("timelines", ["shots", "list", "--project", "demo"], client=client)
    assert rc == 1
    assert len(client.calls) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error not_found: missing\n"


def test_shots_unknown_verb_is_a_usage_error() -> None:
    client = _FakeClient()
    with pytest.raises(SystemExit) as excinfo:
        _run("timelines", ["shots", "export", "--project", "demo"], client=client)
    assert excinfo.value.code == 2
    assert client.calls == []


@pytest.mark.parametrize(
    "argv",
    [
        ["shots", "--help"],
        ["shots", "list", "--help"],
        ["shots", "create", "--help"],
        ["shots", "add", "--help"],
        ["shots", "remove", "--help"],
        ["shots", "reorder", "--help"],
    ],
)
def test_timelines_shots_help_is_executable(argv: list[str]) -> None:
    from astrid.packs.timeline.cli import build_parser

    parser = build_parser(_FakeClient())
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(argv)
    assert excinfo.value.code == 0


def test_dispatch_timelines_shots_routes_through_product_dispatch(
    monkeypatch,
) -> None:
    from astrid.core.gateway import dispatch

    seen: dict[str, object] = {}

    def _fake_product(args):  # noqa: ANN001
        seen["args"] = list(args)
        return 9

    monkeypatch.setattr(dispatch, "_dispatch_product", _fake_product)
    assert dispatch._dispatch_timelines(["shots", "list", "--project", "demo"]) == 9
    assert seen["args"] == ["timelines", "shots", "list", "--project", "demo"]
