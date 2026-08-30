from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

RUNTIME = Path(__file__).parents[3] / "banodoco-workspace-runtime-convergence"
sys.path.insert(0, str(RUNTIME))

from runtime_protocol.daemon import RuntimeDaemon  # noqa: E402
from astrid.core.gateway import dispatch  # noqa: E402
from astrid.sdk.client import AstridClient  # noqa: E402


def test_product_client_requires_bootstrap_with_exact_next_action(tmp_path, monkeypatch):
    monkeypatch.setenv("BANODOCO_RUNTIME_DISCOVERY", str(tmp_path / "missing-discovery.json"))
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "missing-credential.json"))
    monkeypatch.delenv("BANODOCO_RUNTIME_ENDPOINT", raising=False)
    with pytest.raises(Exception, match=r"banodoco-local up --profile astrid"):
        AstridClient.open()


def test_product_client_crosses_real_daemon_and_returns_stable_envelopes(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        client = AstridClient.open()
        created = client.projects.create(slug="demo", name="Demo", idempotency_key="project-1")
        assert set(created.as_dict()) == {"ok", "data", "error", "receipt", "idempotency_key"}
        assert created.ok and created.data["name"] == "Demo"
        media_path = tmp_path / "clip.bin"
        media_path.write_bytes(b"hello")
        imported = client.media.import_file(project="demo", path=media_path, idempotency_key="media-1")
        assert imported.ok and imported.data["digest"].startswith("sha256:")
        task = client.tasks.create(project_id="demo", capability="render.basic", spec={}, idempotency_key="task-1")
        assert task.ok and task.data["capability_id"] == "render.basic"
        assert client.tasks.show(task.data["task_id"]).ok
        client.close()
    finally:
        daemon.stop()


def test_serve_is_not_a_public_dispatch_command(capsys):
    assert "serve" not in dispatch._top_level_commands()
    assert dispatch._top_level_commands() == frozenset({"projects", "timelines", "media", "tasks", "runs", "doctor", "backup"})


def test_remote_boundary_has_no_storage_or_runtime_imports():
    source = "\n".join((Path(__file__).parents[2] / "astrid" / "sdk" / name).read_text() for name in ("remote.py", "workspace_client.py"))
    assert "import sqlite" not in source and "import cas" not in source
    assert "runtime_protocol" not in source


def test_client_boundary_has_no_local_authority_escape_hatch():
    source = (Path(__file__).parents[2] / "astrid" / "sdk" / "client.py").read_text()
    assert "compose_standard_application" not in source
    assert "database_path" not in source
    assert "projects_root" not in source
    with pytest.raises(TypeError):
        AstridClient.open(projects_root="/tmp/should-not-open")


def test_retired_public_commands_are_absent():
    from astrid.core.pack.cli_parser import build_parser
    from astrid.core.cli.domain_media import build_parser as media_parser

    pack_commands = next(action for action in build_parser()._actions if isinstance(getattr(action, "choices", None), dict)).choices
    assert not {"install", "update", "rollback", "uninstall"} & set(pack_commands)
    media_commands = next(action for action in media_parser(None)._actions if isinstance(getattr(action, "choices", None), dict)).choices
    assert "relocate" not in media_commands


def test_doctor_and_backup_never_open_local_storage(capsys, monkeypatch, tmp_path):
    monkeypatch.delenv("BANODOCO_RUNTIME_ENDPOINT", raising=False)
    monkeypatch.setenv("BANODOCO_RUNTIME_DISCOVERY", str(tmp_path / "missing.json"))
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "missing.token"))

    assert dispatch._dispatch_doctor(["--json"]) == 1
    assert "banodoco-local up --profile astrid" in capsys.readouterr().out
    assert dispatch._dispatch_backup(["--json"]) == 1
    assert "banodoco-local up --profile astrid" in capsys.readouterr().out
