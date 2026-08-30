from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest

RUNTIME = Path(__file__).parents[3] / "banodoco-workspace-runtime-stage1-convergence"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "packages" / "python"))

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


def test_remote_reads_are_scoped_and_unsupported_operations_fail_honestly(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        client = AstridClient.open()
        project = client.projects.create(slug="scoped", name="Scoped", idempotency_key="p")
        source = tmp_path / "scoped.bin"
        source.write_bytes(b"scoped")
        imported = client.media.import_file(project="scoped", path=source, idempotency_key="m")
        assert imported.ok
        listed = client.media.list("scoped")
        assert listed.ok and any(item.get("digest") == imported.data["digest"] for item in listed.data)
        verified = client.media.verify("scoped", imported.data["digest"])
        assert verified.ok and verified.data["verified"] is True
        tasks = client.tasks.list("scoped")
        assert tasks.ok and tasks.data == []
        assert not client.timelines.save("scoped", "missing").ok
    finally:
        daemon.stop()


def test_client_reopens_after_close_against_same_daemon(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        first = AstridClient.open()
        assert isinstance(first.health(), dict)
        first.close()
        second = AstridClient.open()
        assert isinstance(second.health(), dict)
        second.close()
    finally:
        daemon.stop()


def test_serve_is_not_a_public_dispatch_command(capsys):
    assert "serve" not in dispatch._top_level_commands()
    assert dispatch._top_level_commands() == frozenset({"projects", "timelines", "media", "tasks", "runs", "doctor", "backup"})


def test_remote_boundary_has_no_storage_or_runtime_imports():
    source = "\n".join((Path(__file__).parents[2] / "astrid" / "sdk" / name).read_text() for name in ("remote.py", "workspace_client.py"))
    assert "import sqlite" not in source and "import cas" not in source
    assert "runtime_protocol" not in source


def test_sdk_client_import_does_not_construct_local_authority():
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", "import sys; import astrid.sdk.client; print([name for name in sys.modules if name == 'astrid.application' or name.startswith('astrid.core.threads') or name == 'sqlite3'])"],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(Path(__file__).parents[2]),
    )
    assert result.stdout.strip() == "[]"


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


def test_remote_domains_use_generated_runtime_and_reopen(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        client = AstridClient.open()
        project = client.projects.create(slug="journey", name="Journey", idempotency_key="journey-project")
        assert project.ok
        timeline = client.timelines.create(project="journey", slug="main", idempotency_key="journey-timeline")
        assert timeline.ok
        timeline_id = timeline.data["timeline_id"]
        saved = client.timelines.save("journey", timeline_id, expected_version=1, shots=[{"shot_id": "s1", "start_ms": 0, "duration_ms": 100}])
        assert saved.ok and saved.data["version"] == 2
        task = client.tasks.create(project_id="journey", capability="render.basic", spec={}, idempotency_key="journey-task")
        assert task.ok
        assert client.tasks.show(task.data["task_id"], project="journey").ok
        assert client.tasks.events(task.data["task_id"]).ok
        invoked = client.invoke("render.basic", idempotency_key="journey-invoke")
        rendered = client.render("render.basic", idempotency_key="journey-render")
        assert invoked.ok and rendered.ok
        run = client.runs.show("journey", task.data["run_id"])
        assert run.ok
        assert client.runs.events("journey", task.data["run_id"]).ok
        client.close()
        daemon.stop()
        daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
        monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
        reopened = AstridClient.open()
        assert reopened.projects.show("journey").ok
        assert reopened.timelines.show("journey", timeline_id).ok
        reopened.close()
    finally:
        daemon.stop()


def test_editor_domain_reads_and_media_relations_use_generated_operations(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        client = AstridClient.open()
        project = client.projects.create(slug="editor", name="Editor", idempotency_key="project").data
        project_id = project["project_id"]
        first_path, second_path = tmp_path / "first.bin", tmp_path / "second.bin"
        first_path.write_bytes(b"first")
        second_path.write_bytes(b"second")
        first = client.media.import_file(project=project_id, path=first_path, idempotency_key="first").data
        second = client.media.import_file(project=project_id, path=second_path, idempotency_key="second").data
        relation = client.media.relate(
            project_id,
            from_object_id=first["object_id"],
            to_object_id=second["object_id"],
            kind="derived_from",
            metadata={"source": "test"},
            idempotency_key="relation",
        )
        assert relation.ok and client.media.list_relations(project_id).data[0]["kind"] == "derived_from"

        timeline = client.timelines.create(project=project_id, slug="main", idempotency_key="timeline").data["timeline_id"]
        shot = client.shots.create(timeline_id=timeline, shot={"shot_id": "shot", "start_ms": 0, "duration_ms": 100}, idempotency_key="shot").data
        reference = client.references.create(timeline_id=timeline, reference_id="reference", object_id=first["object_id"], idempotency_key="reference").data
        assert client.shots.list(project_id).data[0]["shot_id"] == shot["shot_id"]
        assert client.references.list(project_id).data[0]["reference_id"] == reference["reference_id"]
        assert client.shots.update(project_id, shot["shot_id"], start_ms=10).ok
        assert client.shots.archive(project_id, shot["shot_id"], idempotency_key="shot-archive").ok
        assert client.shots.recover(project_id, shot["shot_id"], idempotency_key="shot-recover").ok
        assert client.references.update(project_id, reference["reference_id"], role="primary").ok
        assert client.references.archive(project_id, reference["reference_id"], idempotency_key="reference-archive").ok
        assert client.references.unarchive(project_id, reference["reference_id"], idempotency_key="reference-recover").ok

        task = client.tasks.create(project_id=project_id, capability="render.basic", spec={"prompt": "editor"}, idempotency_key="task").data
        assert client.tasks.list(project_id).data[0]["task_id"] == task["task_id"]
        assert client.runs.list(project_id).data[0]["id"] == task["run_id"]
    finally:
        daemon.stop()


def test_operational_gateway_uses_typed_runtime_backup_and_lifecycle(tmp_path, monkeypatch, capsys):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        assert dispatch._dispatch_doctor(["--json"]) == 0
        doctor = json.loads(capsys.readouterr().out)
        assert doctor["ok"] is True
        assert doctor["recovery_action"] == "No recovery action required."

        backup_path = tmp_path / "backup"
        assert dispatch._dispatch_backup(["create", str(backup_path), "--json"]) == 0
        backup = json.loads(capsys.readouterr().out)
        assert backup["ok"] is True and "manifest" in backup and "cas_manifest" in backup

        client = AstridClient.open()
        exported = client.export_realm()
        assert exported["format_version"] == 1 and "realm" in exported
        tombstoned = client.tombstone_realm(reason="acceptance")
        assert tombstoned["state"] == "tombstoned" and tombstoned["reason"] == "acceptance"
        recovered = client.recover_realm(expected_version=tombstoned["version"])
        assert recovered["state"] == "active"

        restored_path = tmp_path / "restored"
        restored = client.restore_backup(str(backup_path), str(restored_path))
        assert restored["destination"] == str(restored_path)
        assert restored["verification"]["realm_id"] == backup["manifest"]["realm_id"]
        client.close()
    finally:
        daemon.stop()
