from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest

ASTRID_SOURCE = Path(
    subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
).parent
RUNTIME_WORKTREE = ASTRID_SOURCE.parent / "banodoco-workspace-runtime"
RUNTIME_COMMIT = "4050394c5395206f1ec6bf0d905ffbfb7bb0e4de"
_RUNTIME_TMP = tempfile.TemporaryDirectory(prefix="astrid-runtime-archive-")
RUNTIME = Path(_RUNTIME_TMP.name)
archive = subprocess.run(
    ["git", "-C", str(RUNTIME_WORKTREE), "archive", "--format=tar", RUNTIME_COMMIT],
    check=True,
    capture_output=True,
).stdout
with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
    tar.extractall(RUNTIME)
sys.path.insert(0, str(RUNTIME))

pytest.importorskip("runtime_protocol.daemon")
from runtime_protocol.daemon import RuntimeDaemon  # noqa: E402

from astrid.core.gateway import dispatch  # noqa: E402
from astrid.core.gateway import main as gateway_main
from astrid.sdk.client import AstridClient  # noqa: E402


def _open_client(daemon: RuntimeDaemon) -> AstridClient:
    """Open with the runtime-issued identity and canonical protocol explicitly."""
    return AstridClient.open(
        endpoint=daemon.endpoint,
        credential=daemon.credential_path,
        realm_id=daemon.service.realm["id"],
        actor_id="owner",
        client_name="astrid-stage1-tests",
        client_version="stage1",
        protocol_version="workspace.v1",
    )


def _register_render_basic(daemon: RuntimeDaemon) -> None:
    """Seed the capability catalog required by task-admission journeys."""
    daemon.service.register_capability({
        "capability_id": "render.basic",
        "definition_digest": "sha256:" + hashlib.sha256(b"render.basic").hexdigest(),
        "status": "ready",
    })


def _use_explicit_gateway_connection(monkeypatch: pytest.MonkeyPatch, daemon: RuntimeDaemon) -> None:
    """Keep gateway integration online without asking the launcher to boot."""
    monkeypatch.setattr(
        AstridClient,
        "open_from_launcher",
        classmethod(lambda cls, **_kwargs: _open_client(daemon)),
    )


def test_product_client_requires_bootstrap_with_exact_next_action(tmp_path, monkeypatch):
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "missing-credential.json"))
    monkeypatch.delenv("BANODOCO_RUNTIME_ENDPOINT", raising=False)
    with pytest.raises(Exception, match=r"banodoco-local up --profile astrid"):
        AstridClient.open()


def test_product_client_crosses_real_daemon_and_returns_stable_envelopes(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    _register_render_basic(daemon)
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        client = _open_client(daemon)
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
    finally:
        daemon.stop()


def test_documented_minimal_timeline_create_defaults_empty_document_on_real_gateway(
    tmp_path, monkeypatch, capsys
):
    """The documented create command reaches the real runtime with defaults."""
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    _use_explicit_gateway_connection(monkeypatch, daemon)
    try:
        assert gateway_main(
            ["projects", "create", "demo", "--name", "Demo", "--json"]
        ) == 0
        project = json.loads(capsys.readouterr().out)
        assert project["ok"]

        # This is the documented minimal command: no --config or --registry.
        assert gateway_main(
            [
                "timelines",
                "create",
                "--project",
                "demo",
                "primary",
                "--name",
                "Primary",
                "--default",
                "--json",
            ]
        ) == 0
        created = json.loads(capsys.readouterr().out)
        assert set(created) == {"ok", "data", "error", "receipt", "idempotency_key"}
        assert created["ok"]
        assert created["data"]["config"] == {}
        assert created["data"]["registry"] == {"assets": {}}
        assert created["data"]["config_version"] == 1

        # Explicit JSON remains authoritative, including an explicitly empty
        # registry rather than being replaced by the default.
        assert gateway_main(
            [
                "timelines",
                "create",
                "--project",
                "demo",
                "explicit",
                "--name",
                "Explicit",
                "--config",
                '{"tracks": []}',
                "--registry",
                '{"assets": {"clip": {"media_id": "media-1"}}}',
                "--json",
            ]
        ) == 0
        explicit = json.loads(capsys.readouterr().out)
        assert set(explicit) == {"ok", "data", "error", "receipt", "idempotency_key"}
        assert explicit["ok"]
        assert explicit["data"]["config"] == {"tracks": []}
        assert explicit["data"]["registry"] == {
            "assets": {"clip": {"media_id": "media-1"}}
        }
    finally:
        daemon.stop()


def test_cold_mutations_expose_server_receipts_on_cli_sdk_replay(tmp_path, monkeypatch, capsys):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    _register_render_basic(daemon)
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    _use_explicit_gateway_connection(monkeypatch, daemon)
    try:
        with _open_client(daemon) as client:
            assert gateway_main(["projects", "create", "cold", "--name", "Cold", "--idempotency-key", "cold-project", "--json"]) == 0
            created = json.loads(capsys.readouterr().out)
            assert created["ok"] and created["data"]["slug"] == "cold"
            assert created["receipt"] is not None
            assert created["receipt"]["command_kind"] == "project.create"
            project_id = created["data"]["project_id"]
            replay = client.projects.create(slug="cold", name="Cold", idempotency_key="cold-project")
            assert replay.ok and replay.receipt is not None
            assert replay.receipt.command_kind == "project.create"
            assert replay.receipt.as_dict() == created["receipt"]

            assert gateway_main(["projects", "select", project_id, "--scope", "workspace", "--json"]) == 0
            selected = json.loads(capsys.readouterr().out)
            assert selected["ok"] and selected["data"]["project"]["project_id"] == project_id
            sdk_selected = client.projects.select(project_id, scope="workspace", idempotency_key=selected["idempotency_key"])
            assert sdk_selected.ok

            assert gateway_main(["tasks", "create", "--project", project_id, "--capability", "render.basic", "--spec", "{}", "--idempotency-key", "cold-task", "--json"]) == 0
            admitted = json.loads(capsys.readouterr().out)
            assert admitted["ok"] and admitted["data"]["capability_id"] == "render.basic"
            assert admitted["receipt"] is not None
            assert admitted["receipt"]["command_kind"] == "task.create"
            sdk_task = client.tasks.create(project_id=project_id, capability="render.basic", spec={}, idempotency_key="cold-task")
            assert sdk_task.ok and sdk_task.receipt is not None
            assert sdk_task.receipt.command_kind == "task.create"
            assert sdk_task.receipt.as_dict() == admitted["receipt"]

            before = daemon.service.store.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            daemon.service.register_capability({
                "capability_id": "cold.gpu",
                "definition_digest": "sha256:" + hashlib.sha256(b"cold.gpu").hexdigest(),
                "status": "unavailable",
                "unavailable_reason": "gpu_not_configured",
            })
            failed = client.tasks.create(project_id=project_id, capability="cold.gpu", spec={}, idempotency_key="cold-gpu")
            assert not failed.ok and failed.receipt is None and failed.error.code == "unavailable"
            assert daemon.service.store.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == before
    finally:
        daemon.stop()


def test_projects_selection_and_unready_admission_are_typed_on_real_daemon(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        with _open_client(daemon) as client:
            project = client.projects.create(slug="selected", name="Selected", idempotency_key="selected").data
            selected = client.projects.select(project["project_id"], scope="workspace")
            assert selected.ok and selected.data["project"]["project_id"] == project["project_id"]
            current = client.projects.current()
            assert current.ok and current.data["scope"] == "workspace"
            assert current.data["project"]["project_id"] == project["project_id"]

            import hashlib

            digest = "sha256:" + hashlib.sha256(b"acceptance.gpu").hexdigest()
            daemon.service.register_capability({
                "capability_id": "acceptance.gpu",
                "definition_digest": digest,
                "status": "unavailable",
                "unavailable_reason": "gpu_not_configured",
            })
            before = daemon.service.store.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            blocked = client.tasks.create(project_id=project["project_id"], capability="acceptance.gpu", spec={}, idempotency_key="blocked-gpu")
            assert not blocked.ok and blocked.error.code == "unavailable"
            assert blocked.error.details["next_action"] == "wait for capability readiness and retry"
            assert daemon.service.store.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == before
    finally:
        daemon.stop()


def test_documented_project_cli_mutations_return_committed_receipts(tmp_path, monkeypatch, capsys):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    _use_explicit_gateway_connection(monkeypatch, daemon)
    _use_explicit_gateway_connection(monkeypatch, daemon)
    try:
        client = _open_client(daemon)
        assert client.projects.create(slug="cli", name="CLI", idempotency_key="cli-project").ok
        first_path, second_path = tmp_path / "first.bin", tmp_path / "second.bin"
        first_path.write_bytes(b"first")
        second_path.write_bytes(b"second")
        first = client.media.import_file(project="cli", path=first_path, idempotency_key="cli-media-1").data
        second = client.media.import_file(project="cli", path=second_path, idempotency_key="cli-media-2").data
        ref_a = client.references.create(project="cli", kind="character", name="A", media_id=first["object_id"], idempotency_key="cli-ref-a").data
        ref_b = client.references.create(project="cli", kind="character", name="B", media_id=second["object_id"], idempotency_key="cli-ref-b").data
        association = client.references.associate("cli", ref_a["reference_id"], media_id=second["object_id"], idempotency_key="cli-association").data
        shot = client.shots.create(project="cli", name="Shot", idempotency_key="cli-shot").data
        first_item = client.shots.add_item("cli", shot["shot_id"], media_id=first["object_id"], idempotency_key="cli-item-1").data
        second_item = client.shots.add_item("cli", shot["shot_id"], media_id=second["object_id"], idempotency_key="cli-item-2").data
        assert association["media_references"]

        assert gateway_main(["media", "references", "link", "--project", "cli", "--from", ref_a["reference_id"], "--to", ref_b["reference_id"], "--kind", "related_to", "--idempotency-key", "cli-link", "--json"]) == 0
        link_result = json.loads(capsys.readouterr().out)
        assert link_result["ok"]

        assert gateway_main(["media", "references", "set-primary", ref_a["reference_id"], "--project", "cli", "--media-reference", association["media_references"][-1]["association_id"], "--idempotency-key", "cli-primary", "--json"]) == 0
        primary_result = json.loads(capsys.readouterr().out)
        assert primary_result["ok"]

        assert gateway_main(["timelines", "shots", "reorder", shot["shot_id"], "--project", "cli", "--items", f"{second_item['items'][1]['item_id']},{first_item['items'][0]['item_id']}", "--idempotency-key", "cli-reorder", "--json"]) == 0
        reorder_result = json.loads(capsys.readouterr().out)
        assert reorder_result["ok"]
        assert set(reorder_result) == {"ok", "data", "error", "receipt", "idempotency_key"}
    finally:
        daemon.stop()


def test_project_shot_scope_stays_with_project_route(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))

    def assert_not_found(result):
        assert not result.ok
        assert result.error is not None and result.error.code == "not_found"
        assert result.receipt is None

    try:
        client = _open_client(daemon)
        owner = client.projects.create(slug="shot-owner", name="Shot owner", idempotency_key="shot-owner").data
        other = client.projects.create(slug="shot-other", name="Shot other", idempotency_key="shot-other").data
        legacy = client.shots.create(
            project=owner["project_id"],
            shot={"shot_id": "collision", "name": "Owner shot"},
            idempotency_key="legacy-shot",
        )
        assert legacy.ok
        before = client._remote._transport.get_project_shot(owner["project_id"], "collision")

        # A project-scoped read and every version-resolving mutation must stay
        # in the project route.  The colliding legacy child is not in other.
        assert_not_found(client.shots.show(other["project_id"], "collision"))
        assert_not_found(client.shots.update(other["project_id"], "collision", name="Hacked", idempotency_key="wrong-update"))
        assert_not_found(client.shots.archive(other["project_id"], "collision", idempotency_key="wrong-archive"))
        assert_not_found(client.shots.recover(other["project_id"], "collision", idempotency_key="wrong-recover"))
        assert client._remote._transport.get_project_shot(owner["project_id"], "collision") == before

        # Project-owned mutations remain receipt-bearing on success.
        owned = client.shots.create(project=other["project_id"], name="Owned", idempotency_key="owned-shot")
        assert owned.ok
        updated = client.shots.update(other["project_id"], owned.data["shot_id"], name="Owned 2", idempotency_key="owned-update")
        assert updated.ok
        archived = client.shots.archive(other["project_id"], owned.data["shot_id"], idempotency_key="owned-archive")
        assert archived.ok
        recovered = client.shots.recover(other["project_id"], owned.data["shot_id"], idempotency_key="owned-recover")
        assert recovered.ok
    finally:
        daemon.stop()


def test_project_reference_scope_stays_with_project_route(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))

    def assert_not_found(result):
        assert not result.ok
        assert result.error is not None and result.error.code == "not_found"
        assert result.receipt is None

    try:
        client = _open_client(daemon)
        owner = client.projects.create(slug="reference-owner", name="Reference owner", idempotency_key="reference-owner").data
        other = client.projects.create(slug="reference-other", name="Reference other", idempotency_key="reference-other").data
        owner_path, other_path = tmp_path / "owner.bin", tmp_path / "other.bin"
        owner_path.write_bytes(b"owner")
        other_path.write_bytes(b"other")
        owner_media = client.media.import_file(project=owner["project_id"], path=owner_path, idempotency_key="owner-media").data
        other_media = client.media.import_file(project=other["project_id"], path=other_path, idempotency_key="other-media").data
        legacy = client.references.create(
            project=owner["project_id"],
            reference_id="collision",
            kind="character",
            name="Owner reference",
            media_id=owner_media["object_id"],
            idempotency_key="legacy-reference",
        )
        assert legacy.ok
        before = client._remote._transport.get_project_reference(owner["project_id"], "collision")

        assert_not_found(client.references.show(other["project_id"], "collision"))
        assert_not_found(client.references.update(other["project_id"], "collision", name="Hacked", idempotency_key="wrong-update"))
        assert_not_found(client.references.archive(other["project_id"], "collision", idempotency_key="wrong-archive"))
        assert_not_found(client.references.recover(other["project_id"], "collision", idempotency_key="wrong-recover"))
        assert client._remote._transport.get_project_reference(owner["project_id"], "collision") == before

        owned = client.references.create(
            project=other["project_id"],
            reference_id="owned-reference",
            kind="character",
            name="Owned",
            media_id=other_media["object_id"],
            idempotency_key="owned-reference",
        )
        assert owned.ok
        updated = client.references.update(other["project_id"], "owned-reference", name="Owned 2", idempotency_key="owned-update")
        assert updated.ok
        archived = client.references.archive(other["project_id"], "owned-reference", idempotency_key="owned-archive")
        assert archived.ok
        recovered = client.references.recover(other["project_id"], "owned-reference", idempotency_key="owned-recover")
        assert recovered.ok
    finally:
        daemon.stop()


def test_remote_reads_are_scoped_and_unsupported_operations_fail_honestly(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        client = _open_client(daemon)
        project = client.projects.create(slug="scoped", name="Scoped", idempotency_key="p")
        source = tmp_path / "scoped.bin"
        source.write_bytes(b"scoped")
        imported = client.media.import_file(project="scoped", path=source, idempotency_key="m")
        assert imported.ok
        listed = client.media.list("scoped")
        assert listed.ok and any(item.get("digest") == imported.data["digest"] for item in listed.data[0])
        verified = client.media.verify("scoped", imported.data["digest"])
        assert verified.ok and verified.data["verified"] is True
        tasks = client.tasks.list("scoped")
        assert tasks.ok and tasks.data[0] == []
        missing_save = client.timelines.save("scoped", "missing", config={}, registry={})
        assert not missing_save.ok
    finally:
        daemon.stop()


def test_client_reopens_after_close_against_same_daemon(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        first = _open_client(daemon)
        assert isinstance(first.health(), dict)
        second = _open_client(daemon)
        assert isinstance(second.health(), dict)
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
    from astrid.core.cli.domain_media import build_parser as media_parser
    from astrid.core.pack.cli_parser import build_parser

    pack_commands = next(action for action in build_parser()._actions if isinstance(getattr(action, "choices", None), dict)).choices
    assert not {"install", "update", "rollback", "uninstall"} & set(pack_commands)
    media_commands = next(action for action in media_parser(None)._actions if isinstance(getattr(action, "choices", None), dict)).choices
    assert "relocate" not in media_commands


def test_doctor_and_backup_never_open_local_storage(capsys, monkeypatch, tmp_path):
    monkeypatch.delenv("BANODOCO_RUNTIME_ENDPOINT", raising=False)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "missing.token"))

    assert dispatch._dispatch_doctor(["--json"]) == 1
    assert "banodoco-local up --profile astrid" in capsys.readouterr().out
    assert dispatch._dispatch_backup(["--json"]) == 1
    assert "banodoco-local up --profile astrid" in capsys.readouterr().out


def test_remote_domains_use_generated_runtime_and_reopen(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    _register_render_basic(daemon)
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        client = _open_client(daemon)
        project = client.projects.create(slug="journey", name="Journey", idempotency_key="journey-project")
        assert project.ok
        timeline = client.timelines.create(project="journey", config={}, registry={}, slug="main", idempotency_key="journey-timeline")
        assert timeline.ok
        timeline_id = timeline.data["timeline_id"]
        saved = client.timelines.save("journey", timeline_id, config={}, registry={}, expected_version=1)
        assert saved.ok
        task = client.tasks.create(project_id="journey", capability="render.basic", spec={}, idempotency_key="journey-task")
        assert task.ok
        assert client.tasks.show(task.data["task_id"]).ok
        assert client.tasks.events(task.data["task_id"]).ok
        invoked = client.invoke("render.basic", project_id="journey", spec={}, idempotency_key="journey-invoke")
        assert invoked.ok
        assert not hasattr(client, "render")
        run = client.runs.show(task.data["run_id"])
        assert run.ok
        assert client.runs.events(task.data["run_id"]).ok
        daemon.stop()
        daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
        monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
        reopened = _open_client(daemon)
        assert reopened.projects.show("journey").ok
        assert reopened.timelines.show("journey", timeline_id).ok
    finally:
        daemon.stop()


def test_editor_domain_reads_and_media_relations_use_generated_operations(tmp_path, monkeypatch):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    _register_render_basic(daemon)
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    try:
        client = _open_client(daemon)
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
        assert relation.ok and client.media.list_relations(project_id).data[0][0]["kind"] == "derived_from"

        timeline = client.timelines.create(project=project_id, config={}, registry={}, slug="main", idempotency_key="timeline").data["timeline_id"]
        shot_result = client.shots.create(project=project_id, name="Shot", idempotency_key="shot")
        reference_result = client.references.create(project=project_id, reference_id="reference", kind="character", name="Reference", media_id=first["object_id"], idempotency_key="reference")
        assert shot_result.ok and reference_result.ok
        shot, reference = shot_result.data, reference_result.data
        assert client.shots.list(project_id).data[0][0]["shot_id"] == shot["shot_id"]
        assert client.references.list(project_id).data[0][0]["reference_id"] == reference["reference_id"]
        assert client.shots.update(project_id, shot["shot_id"], name="Shot 2", idempotency_key="shot-update").ok
        assert client.shots.archive(project_id, shot["shot_id"], idempotency_key="shot-archive").ok
        assert client.shots.recover(project_id, shot["shot_id"], idempotency_key="shot-recover").ok
        assert client.references.update(project_id, reference["reference_id"], name="Reference 2").ok
        assert client.references.archive(project_id, reference["reference_id"], idempotency_key="reference-archive").ok
        assert client.references.recover(project_id, reference["reference_id"], idempotency_key="reference-recover").ok

        task = client.tasks.create(project_id=project_id, capability="render.basic", spec={"prompt": "editor"}, idempotency_key="task").data
        assert client.tasks.list(project_id).data[0][0]["task_id"] == task["task_id"]
        assert client.runs.list(project_id).data[0][0]["id"] == task["run_id"]
    finally:
        daemon.stop()


def test_operational_gateway_uses_typed_runtime_backup_and_lifecycle(tmp_path, monkeypatch, capsys):
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "support" / "credentials" / "owner.token"))
    _use_explicit_gateway_connection(monkeypatch, daemon)
    try:
        assert dispatch._dispatch_doctor(["--json"]) == 0
        doctor = json.loads(capsys.readouterr().out)
        assert doctor["ok"] is True
        assert doctor["recovery_action"] == "No recovery action required."

        backup_path = tmp_path / "backup"
        assert dispatch._dispatch_backup(["create", str(backup_path), "--json"]) == 0
        backup = json.loads(capsys.readouterr().out)
        assert backup["ok"] is True and "manifest" in backup and "cas_manifest" in backup

        client = _open_client(daemon)
        exported = client.export_realm()
        assert exported["format_version"] == 1 and "realm" in exported
        tombstoned = client.tombstone_realm(reason="acceptance")
        assert tombstoned["state"] == "tombstoned" and tombstoned["reason"] == "acceptance"
        realm_id = daemon.service.realm["id"]
        recovered = client.recover_realm(expected_realm_id=realm_id, expected_version=tombstoned["version"], confirmation=f"RECOVER {realm_id}")
        assert recovered["state"] == "active"

        restored_path = tmp_path / "restored"
        restored = client.restore_backup(str(backup_path), str(restored_path))
        assert restored["destination"] == str(restored_path)
        assert restored["verification"]["realm_id"] == backup["manifest"]["realm_id"]
    finally:
        daemon.stop()
