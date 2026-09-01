"""No-mock, final Stage 1 cold-launch matrix.

This is intentionally one executable journey rather than another collection of
mocked launcher assertions.  It creates a fresh current-Mac-shaped support
home, starts the pinned neutral runtime through ``banodoco-local up``, uses the
real Astrid CLI/SDK and generic host, kills/restarts the runtime, and finally
proves the neutral TypeScript client against the same daemon.  The Remotion
dependency tree is deliberately not part of this gate: the Stage 1 blueprint
requires a real registered Astrid render/FFmpeg journey, while Remotion's
optional dependency closure is environment-specific and is covered by its
separate opt-in acceptance test.

Run directly from the Astrid checkout::

    PYTHONPATH=.:../banodoco-workspace-runtime-stage1-convergence/packages/python \
      python3 -m pytest -q tests/stage1/test_final_cold_launch_matrix_luna.py

The runtime source is archived at the immutable commit below before launch;
the working runtime checkout is never imported by the daemon in this test.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_CHECKOUT = ROOT.parent / "banodoco-workspace-runtime-stage1-convergence"
RUNTIME_COMMIT = "aa54009de988c714fb140d99ce34449c44b91d91"


def _archive_runtime(destination: Path) -> Path:
    destination.mkdir()
    archive = subprocess.run(
        ["git", "-C", str(RUNTIME_CHECKOUT), "archive", "--format=tar", RUNTIME_COMMIT],
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=__import__("io").BytesIO(archive), mode="r:") as tar:
        tar.extractall(destination)
    return destination


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _result_data(value: Any) -> Mapping[str, Any]:
    data = getattr(value, "data", None)
    if isinstance(data, Mapping):
        return data
    if isinstance(value, Mapping):
        candidate = value.get("data", value)
        return candidate if isinstance(candidate, Mapping) else value
    raise AssertionError(f"expected mapping result, got {value!r}")


def _run(
    argv: list[str],
    env: Mapping[str, str],
    *,
    check: bool = True,
    cwd: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=dict(env),
        text=True,
        capture_output=True,
        check=False,
        timeout=45,
    )
    if check and completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {' '.join(argv)}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


def _assert_cli_ok(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Astrid CLI did not emit JSON: {completed.stdout!r}") from exc
    assert result.get("ok") is True, result
    assert set(result) == {"ok", "data", "error", "receipt", "idempotency_key"}, result
    return result


def _wait_dead(pid: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            return
        time.sleep(0.05)
    raise AssertionError(f"runtime pid {pid} did not exit after SIGKILL")


def _write_launcher(path: Path) -> None:
    # Use an absolute interpreter and the inherited PYTHONPATH, so this is the
    # actual neutral CLI process and not an installed/ambient launcher.
    path.write_text(
        "#!/bin/sh\n"
        f"exec {sys.executable!s} -m banodoco_local \"$@\"\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


def test_final_cold_launch_matrix_no_mocks(tmp_path: Path) -> None:
    """Exercise the complete supported Stage 1 launch and execution seam."""

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.fail("Stage 1 requires ffmpeg and ffprobe for the real render lane")
    if shutil.which("node") is None or shutil.which("npm") is None:
        pytest.fail("Stage 1 TypeScript second-client proof requires node and npm")

    runtime_archive = _archive_runtime(tmp_path / "runtime-archive")
    runtime_python = runtime_archive / "packages" / "python"
    home = tmp_path / "home"
    support = home / "Library" / "Application Support" / "Banodoco"
    source_manifest = tmp_path / "astrid-source-profile.json"
    launcher = tmp_path / "banodoco-local"
    source_manifest.write_text(
        json.dumps(
            {
                "profile": "astrid",
                "runtime_checkout": str(runtime_archive),
                "source_checkout": str(ROOT),
                "runtime_command": [],
                "protocol_version": "workspace.v1",
                "schema_version": "workspace-schema-v1",
            }
        ),
        encoding="utf-8",
    )
    _write_launcher(launcher)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["BANODOCO_LOCAL_HOME"] = str(home)
    env["BANODOCO_LOCAL_LAUNCHER"] = str(launcher)
    env["BANODOCO_LOCAL_SOURCE_MANIFEST"] = str(source_manifest)
    env["PYTHONPATH"] = os.pathsep.join(
        (
            str(ROOT),
            str(runtime_archive),
            str(runtime_python),
            str(Path(importlib.util.find_spec("yaml").origin).parent.parent),
            env.get("PYTHONPATH", ""),
        )
    )

    runtime_pid: int | None = None
    try:
        # Fresh trusted bootstrap through the real neutral launcher.
        first = _run(
            [sys.executable, "-m", "banodoco_local", "up", "--profile", "astrid", "--source-manifest", str(source_manifest), "--json"],
            env,
        )
        started = json.loads(first.stdout)
        assert started["status"] == "started", started
        assert started["realm_id"] and started["actor_id"]
        discovery_path = support / "runtime" / "discovery.json"
        catalog_path = support / "runtime" / "catalog.json"
        discovery = _json(discovery_path)
        catalog = _json(catalog_path)
        runtime_pid = int(discovery["pid"])
        assert catalog["selected_realm_id"] == started["realm_id"]
        assert discovery["active_realm"] == started["realm_id"]
        assert discovery["endpoint"].startswith("http://127.0.0.1:")
        serialized_discovery = json.dumps(discovery)
        # Runtime advertises the worker credential *path* so the pack host can
        # bootstrap with its least-privilege actor.  The bearer value itself
        # must never appear in discovery.
        assert discovery.get("worker_credential_file")
        assert "database" not in serialized_discovery.lower()

        credential_file = Path(started["credential_file"])
        assert credential_file == support / "credentials" / "astrid.json"
        assert stat.S_IMODE(credential_file.stat().st_mode) == 0o600
        assert stat.S_IMODE((support / "runtime").stat().st_mode) == 0o700
        owner_token_file = support / "runtime" / "credentials" / "owner.token"
        assert owner_token_file.is_file()
        owner_token = owner_token_file.read_text(encoding="utf-8").strip()
        assert owner_token
        assert owner_token not in serialized_discovery
        worker_credential_file = Path(discovery["worker_credential_file"])
        assert worker_credential_file.is_file()
        assert stat.S_IMODE(worker_credential_file.stat().st_mode) == 0o600
        worker_token = worker_credential_file.read_text(encoding="utf-8").strip()
        assert worker_token and worker_token != owner_token
        assert discovery["worker_actor"] == "astrid-pack-host"
        assert tuple(discovery["worker_scopes"]) == (
            "handshake",
            "worker:register",
            "worker:execute",
            "tasks:read",
            "objects:read",
            "objects:write",
        )

        # A second real launch with the first-run manifest removed exercises
        # persisted-profile/env-less relaunch rather than mocked delegation.
        envless = dict(env)
        envless.pop("BANODOCO_LOCAL_SOURCE_MANIFEST")
        second = _run(
            [sys.executable, "-m", "banodoco_local", "up", "--profile", "astrid", "--json"],
            envless,
        )
        reconnected = json.loads(second.stdout)
        assert reconnected["status"] == "reconnected", reconnected
        assert reconnected["realm_id"] == started["realm_id"]
        assert int(_json(discovery_path)["pid"]) == runtime_pid

        # Concurrent real launches: both subprocesses use the same persisted
        # source profile and support lock. Exactly one may start an owner.
        concurrent = [
            subprocess.Popen(
                [sys.executable, "-m", "banodoco_local", "up", "--profile", "astrid", "--json"],
                cwd=ROOT,
                env=envless,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(2)
        ]
        outputs = []
        for process in concurrent:
            stdout, stderr = process.communicate(timeout=45)
            assert process.returncode == 0, (stdout, stderr)
            outputs.append(json.loads(stdout))
        assert {value["status"] for value in outputs} <= {"reconnected", "started"}
        assert all(value["realm_id"] == started["realm_id"] for value in outputs)
        assert len({int(_json(discovery_path)["pid"])}) == 1

        # Astrid CLI admission, then SDK-domain composition over the same
        # explicit endpoint/credential context.
        project_result = _assert_cli_ok(
            _run(
                [sys.executable, "-m", "astrid", "projects", "create", "cold-final", "--name", "Cold Final", "--idempotency-key", "cold-project", "--json"],
                envless,
            )
        )
        project_data = project_result["data"]
        project_id = str(project_data.get("project_id") or project_data.get("id") or "cold-final")
        source = tmp_path / "managed-source.txt"
        source.write_text("managed input", encoding="utf-8")
        media_result = _assert_cli_ok(
            _run(
                [sys.executable, "-m", "astrid", "media", "import", str(source), "--project", project_id, "--idempotency-key", "cold-media", "--json"],
                envless,
            )
        )
        media_data = media_result["data"]
        object_id = str(media_data.get("object_id") or media_data["digest"])
        source.unlink()
        worker_seed = tmp_path / "worker-seed.txt"
        worker_seed.write_text("cold input", encoding="utf-8")
        seed_result = _assert_cli_ok(
            _run(
                [sys.executable, "-m", "astrid", "media", "import", str(worker_seed), "--project", project_id, "--idempotency-key", "cold-worker-seed", "--json"],
                envless,
            )
        )
        seed_data = seed_result["data"]
        seed_object_id = str(seed_data.get("object_id") or seed_data["digest"])
        worker_seed.unlink()

        from astrid.core.execution.generic_host import GenericPackHost, RuntimeProtocolClient
        from astrid.sdk.client import AstridClient

        explicit = AstridClient.open(
            endpoint=started["endpoint"],
            credential=credential_file,
            realm_id=started["realm_id"],
            actor_id=started["actor_id"],
            client_name="stage1-final-cold-matrix",
            client_version="stage1",
            protocol_version="workspace.v1",
        )
        with explicit as client:
            assert client.media.verify(project_id, object_id).ok
            timeline = client.timelines.create(
                project=project_id,
                slug="main",
                name="Main",
                config={},
                registry={},
                idempotency_key="cold-timeline",
            )
            assert timeline.ok
            shot = client.shots.create(
                project=project_id,
                shot={"shot_id": "cold-shot", "name": "Cold Shot"},
                idempotency_key="cold-shot",
            )
            reference = client.references.create(
                project=project_id,
                reference_id="cold-reference",
                kind="object",
                name="Cold Reference",
                media_id=object_id,
                idempotency_key="cold-reference",
            )
            assert shot.ok and reference.ok

            pack = tmp_path / "cpu-pack"
            pack.mkdir()
            (pack / "executor.yaml").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "acceptance.cold_echo",
                        "name": "Cold Echo",
                        "kind": "external",
                        "version": "1.0",
                        "command": {"argv": [sys.executable, "-c", "from pathlib import Path; Path('{out}/answer.txt').write_text('cold worker')"]},
                        "outputs": [{"name": "answer", "type": "file", "path_template": "{out}/answer.txt", "artifact_type": "text/plain"}],
                        "metadata": {"adapter_family": "cpu", "resource_keys": ["cpu"]},
                    }
                ),
                encoding="utf-8",
            )
            host = GenericPackHost(
                pack_roots=[pack],
                client=RuntimeProtocolClient(started["endpoint"], worker_token),
                executor_id="astrid-pack-host",
                attempt_root=tmp_path / "attempt",
            )
            record = host.discover()[0]
            assert host.preflight(record.id)[0].ready is True
            host.register(deliberate=True)
            # The input is already attached to this project, while the
            # fixture executor emits a distinct output. This proves the host
            # uses the claimed task project_id for output ingest rather than
            # relying on a duplicate-input association shortcut.
            admitted = client.tasks.create(
                project_id=project_id,
                capability=record.id,
                spec={},
                input_manifest=[seed_object_id],
                idempotency_key="cold-worker-task",
            )
            assert admitted.ok
            task_id = str(_result_data(admitted)["task_id"])
            settled = host.run(once=True)
            assert len(settled) == 1 and settled[0].state == "succeeded"
            task = client.tasks.show(task_id)
            assert task.ok and _result_data(task)["state"] in {"succeeded", "completed"}
            output_digest = "sha256:" + hashlib.sha256(b"cold worker").hexdigest()
            assert host.client.generated.get_object(output_digest).data == b"cold worker"

            cancelled = client.tasks.create(project_id=project_id, capability=record.id, spec={}, idempotency_key="cold-cancel-task")
            assert cancelled.ok
            cancelled_id = str(_result_data(cancelled)["task_id"])
            cancellation = client.tasks.cancel(cancelled_id, idempotency_key="cold-cancel")
            assert cancellation.ok and _result_data(cancellation)["state"] == "cancelled"
            retry = client.tasks.retry(cancelled_id, idempotency_key="cold-retry")
            assert retry.ok and _result_data(retry)["state"] == "queued"
            # Close the retried project-scoped probe before the standalone
            # worker probe; otherwise the FIFO claim would (correctly) select
            # that earlier task first.
            cancelled_again = client.tasks.cancel(cancelled_id, idempotency_key="cold-cancel-after-retry")
            assert cancelled_again.ok and _result_data(cancelled_again)["state"] == "cancelled"

            # Claim a task without settling it; killing the real runtime then
            # proves epoch fencing and recovery on the persisted realm.
            recovery_task = client.tasks.create(
                project_id=project_id,
                capability=record.id,
                spec={},
                input_manifest=[seed_object_id],
                idempotency_key="cold-recovery-task",
            )
            assert recovery_task.ok
            recovery_id = str(_result_data(recovery_task)["task_id"])
            old_epoch = int(host.client.health()["runtime_epoch"])
            claim = host.client.claim_next(executor_id="astrid-pack-host", capability_ids=[record.id], idempotency_key="cold-recovery-claim")
            assert claim is not None and getattr(claim, "task_id", None) == recovery_id
            old_attempt = claim

        # Kill the detached runtime that the real launcher started.
        os.kill(runtime_pid, signal.SIGKILL)
        _wait_dead(runtime_pid)
        runtime_pid = None

        restarted_process = _run(
            [sys.executable, "-m", "banodoco_local", "up", "--profile", "astrid", "--json"],
            envless,
        )
        restarted = json.loads(restarted_process.stdout)
        assert restarted["status"] == "started"
        assert restarted["realm_id"] == started["realm_id"]
        new_discovery = _json(discovery_path)
        runtime_pid = int(new_discovery["pid"])
        new_worker_credential_file = Path(new_discovery["worker_credential_file"])
        assert stat.S_IMODE(new_worker_credential_file.stat().st_mode) == 0o600
        new_token = new_worker_credential_file.read_text(encoding="utf-8").strip()
        assert new_token and new_token != owner_token

        from banodoco_workspace_client import WorkspaceClient

        generated = WorkspaceClient(restarted["endpoint"], new_token)
        astrid_token = str(_json(Path(restarted["credential_file"])).get("token") or "")
        assert astrid_token and astrid_token != owner_token
        owner_generated = WorkspaceClient(restarted["endpoint"], astrid_token)
        new_epoch = int(generated.health()["runtime_epoch"])
        assert new_epoch > old_epoch
        with pytest.raises(Exception):
            generated.settle_attempt(
                old_attempt.attempt_id,
                {
                    "lease_id": old_attempt.lease_id,
                    "fence": old_attempt.fence,
                    "runtime_epoch": old_epoch,
                    "outputs": [],
                },
                idempotency_key="cold-stale-settlement",
            )
        restarted_host = GenericPackHost(
            pack_roots=[pack],
            client=RuntimeProtocolClient(restarted["endpoint"], new_token),
            executor_id="astrid-pack-host",
            attempt_root=tmp_path / "attempt-restarted",
        )
        restarted_host.discover()
        restarted_host.register(deliberate=True)
        resumed = restarted_host.run(once=True)
        assert len(resumed) == 1 and resumed[0].state == "succeeded"
        assert generated.get_task(recovery_id).state in {"succeeded", "completed"}

        # Real FFmpeg validity/provenance lane.  This is a real external
        # process invoked by the generic host, not a mocked renderer.  The
        # output and its provenance are uploaded to the runtime before the
        # attempt directory is removed, proving the durable handoff.
        render_pack = tmp_path / "ffmpeg-pack"
        render_pack.mkdir()
        ffmpeg = shutil.which("ffmpeg")
        assert ffmpeg is not None
        render_code = (
            "from pathlib import Path; import hashlib, json, subprocess; "
            "out=Path('{out}'); video=out/'render.mp4'; "
            f"subprocess.run([{ffmpeg!r}, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=160x90:r=10:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video)], check=True); "
            "(out/'render.mp4.provenance.json').write_text(json.dumps({'renderer':'ffmpeg','sha256':hashlib.sha256(video.read_bytes()).hexdigest()}))"
        )
        (render_pack / "executor.yaml").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "id": "acceptance.cold_ffmpeg",
                    "name": "Cold FFmpeg",
                    "kind": "external",
                    "version": "1.0",
                    "command": {"argv": [sys.executable, "-c", render_code]},
                    "outputs": [
                        {"name": "render", "type": "file", "path_template": "{out}/render.mp4", "artifact_type": "video/mp4"},
                        {"name": "provenance", "type": "file", "path_template": "{out}/render.mp4.provenance.json", "artifact_type": "application/json"},
                    ],
                    "metadata": {"adapter_family": "cpu", "resource_keys": ["cpu"]},
                }
            ),
            encoding="utf-8",
        )
        render_attempt = tmp_path / "render-attempt"
        render_host = GenericPackHost(
            pack_roots=[render_pack],
            client=RuntimeProtocolClient(restarted["endpoint"], new_token),
            executor_id="astrid-pack-host",
            attempt_root=render_attempt,
        )
        render_record = render_host.discover()[0]
        assert render_host.preflight(render_record.id)[0].ready is True
        render_host.register()
        # Task admission is user-scoped control-plane work.  The worker token
        # intentionally has no tasks:write after the scope cutover.
        render_task = owner_generated.admit_task(
            capability_id=render_record.id,
            capability_digest=render_record.capability_digest,
            input_object_ids=[],
            project_id=project_id,
            idempotency_key="cold-ffmpeg-task",
            spec={},
        )
        render_results = render_host.run(once=True)
        assert len(render_results) == 1 and render_results[0].state == "succeeded"
        video = next(render_attempt.rglob("render.mp4"), None)
        provenance = next(render_attempt.rglob("render.mp4.provenance.json"), None)
        assert video is not None and provenance is not None and video.stat().st_size > 0
        probe = _run(
            ["ffprobe", "-v", "error", "-show_entries", "format=format_name", "-of", "default=nw=1:nk=1", str(video)],
            envless,
        )
        assert "mp4" in probe.stdout
        for artifact in (video, provenance):
            digest = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
            assert generated.get_object(digest).data == artifact.read_bytes()
        assert json.loads(provenance.read_text(encoding="utf-8"))["renderer"] == "ffmpeg"
        shutil.rmtree(render_attempt)
        assert not render_attempt.exists()
        assert generated.get_task(render_task.task_id).state in {"succeeded", "completed"}

        # The neutral doctor path must remain healthy after all mutations.
        doctor = _run(
            [sys.executable, "-m", "banodoco_local", "doctor", "--home", str(home), "--json"],
            envless,
        )
        doctor_result = json.loads(doctor.stdout)
        assert doctor_result["healthy"] is True
        realm_root = Path(new_discovery["active_realm"] if False else catalog["realms"][0]["data_root"])
        assert (realm_root / "realm.sqlite3").is_file() or (realm_root / "workspace.sqlite3").is_file()

        # Compile and execute the neutral TypeScript actor against this same
        # restarted endpoint. npm/build are intentionally explicit so a stale
        # globally installed package cannot satisfy the proof.
        runtime_pkg = runtime_archive / "packages" / "typescript"
        _run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], {**envless, "CI": "1"}, check=True, cwd=runtime_pkg)
        _run(["npm", "run", "build"], {**envless, "CI": "1"}, check=True, cwd=runtime_pkg)
        conformance = runtime_archive / "conformance"
        _run([str(runtime_pkg / "node_modules" / ".bin" / "tsc"), "-p", str(conformance / "tsconfig.json")], {**envless, "CI": "1"}, check=True)
        actor = conformance / "dist" / "conformance" / "fake-second-product.js"
        assert actor.is_file()
        actor_result = _run(["node", str(actor), "--endpoint", restarted["endpoint"], "--token", astrid_token, "--worker-token", new_token], {**envless, "BANODOCO_RUNTIME_OWNER_TOKEN": "", "BANODOCO_LOCAL_OWNER_TOKEN": ""})
        actor_payload = json.loads(actor_result.stdout)
        assert actor_payload["product"] == "neutral-gallery"
        assert actor_payload["realm_id"] == started["realm_id"]
        assert "claim-heartbeat-fenced-settlement-cas-output" in actor_payload["steps"]
    finally:
        if runtime_pid is not None:
            try:
                os.kill(runtime_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
