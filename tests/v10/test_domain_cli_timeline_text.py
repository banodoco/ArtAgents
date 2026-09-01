"""Frozen ``timelines text`` grammar and one-call routing tests."""

from __future__ import annotations

import inspect
from pathlib import Path

from astrid.core.cli.domain_product import run_product_family
from astrid.sdk.contracts import DomainResult


class _Shots:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def _ok(self, name: str, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return DomainResult.success({"called": name})

    def list_text_bindings(self, *args, **kwargs):
        return self._ok("list", *args, **kwargs)

    def checkout_text_bindings(self, *args, **kwargs):
        return self._ok("checkout", *args, **kwargs)

    def status_text_checkout(self, *args, **kwargs):
        return self._ok("status", *args, **kwargs)

    def diff_text_checkout(self, *args, **kwargs):
        return self._ok("diff", *args, **kwargs)

    def apply_text_checkout(self, *args, **kwargs):
        return self._ok("apply", *args, **kwargs)

    def set_text_binding(self, *args, **kwargs):
        return self._ok("set", *args, **kwargs)

    def rebind_text_binding(self, *args, **kwargs):
        return self._ok("rebind", *args, **kwargs)


class _Client:
    def __init__(self) -> None:
        self.shots = _Shots()


def _run(client: _Client, argv: list[str]) -> _Shots:
    assert run_product_family("timelines", ["text", *argv], client=client) == 0
    return client.shots


def test_text_mount_has_exactly_seven_verbs_and_timeline_diff_is_preserved() -> None:
    from astrid.packs.shots.text_cli import COMMANDS
    from astrid.packs.timeline import cli

    assert tuple(spec.name for spec in COMMANDS) == (
        "list", "checkout", "status", "diff", "apply", "set", "rebind"
    )
    # The timeline module delegates mounting to shots.cli, so the old
    # ``timelines diff`` route remains distinct from ``timelines text diff``.
    assert "text_cli" not in inspect.getsource(cli)
    assert "shots_cli" in inspect.getsource(cli)


def test_list_exact_shot_and_project_modes_are_one_call(capsys) -> None:
    client = _Client()
    _run(client, ["list", "--project", "p", "--binding", "b1", "--binding", "b2"])
    assert client.shots.calls == [("list", ("p",), {
        "all_project": False, "binding_ids": ["b1", "b2"], "kind": None,
        "shot_ref": None, "slot": None,
    })]

    client = _Client()
    _run(client, ["list", "--project", "p", "--shot", "Opening",
                  "--kind", "prompt", "--slot", "regen-glitch"])
    assert client.shots.calls == [("list", ("p",), {
        "all_project": False, "binding_ids": None, "kind": "prompt",
        "shot_ref": "Opening", "slot": "regen-glitch",
    })]

    client = _Client()
    _run(client, ["list", "--project", "p", "--all-project", "--kind", "transcript"])
    assert client.shots.calls == [("list", ("p",), {
        "all_project": True, "binding_ids": None, "kind": "transcript",
        "shot_ref": None, "slot": None,
    })]
    assert capsys.readouterr().out


def test_all_workflow_forms_route_once_and_file_bytes_are_raw(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    client = _Client()
    _run(client, ["checkout", "--project", "p", "--all-project", "--out", str(checkout)])
    assert client.shots.calls[0][0] == "checkout"
    assert client.shots.calls[0][2]["all_project"] is True

    for command in ("status", "diff"):
        client = _Client()
        _run(client, [command, str(checkout), "--binding", "b1"])
        assert client.shots.calls == [(command, (checkout,), {"binding_ids": ["b1"]})]

    client = _Client()
    _run(client, ["apply", str(checkout), "--idempotency-key", "k"])
    assert client.shots.calls == [("apply", (checkout,), {
        "binding_ids": None, "idempotency_key": "k"
    })]

    raw = b"\xff\x00raw"
    source = tmp_path / "raw.bin"
    source.write_bytes(raw)
    client = _Client()
    _run(client, ["set", "--project", "p", "--binding", "b1", "--expected-head", "2",
                  "--file", str(source)])
    assert client.shots.calls[0][2]["text"] == raw

    client = _Client()
    _run(client, ["set", "--project", "p", "--binding", "b1", "--expected-head", "2",
                  "--text", "café"])
    assert client.shots.calls[0][2]["text"] == "café".encode("utf-8")

    client = _Client()
    _run(client, ["rebind", "--project", "p", "--binding", "b1", "--expected-head", "2",
                  "--media", "m1"])
    assert client.shots.calls == [("rebind", ("p",), {
        "binding_id": "b1", "expected_head": 2, "idempotency_key": None,
        "kind": None, "media_id": "m1", "shot_ref": None,
        "slot": None,
    })]


def test_timeline_diff_does_not_route_to_text_service() -> None:
    class Timeline:
        def __init__(self): self.calls = []
        def diff(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return DomainResult.success({"timeline": True})
    class Client:
        def __init__(self):
            self.timelines = Timeline()
            self.shots = _Shots()
    client = Client()
    assert run_product_family("timelines", ["diff", "--project", "p", "main"], client=client) == 0
    assert client.timelines.calls == [(('p', 'main'), {})]
    assert client.shots.calls == []
