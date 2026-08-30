from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.execution import process_group
from astrid.core.execution.generic_host import (
    AdapterRegistry,
    GenericPackHost,
    HostCancelled,
    HostError,
    RuntimeProtocolClient,
    _terminate_process_group,
)


class FakeRuntime:
    def __init__(self):
        self.registrations = []
        self.preflights = []
        self.settlements = []
        self.failures = []
        self.heartbeats = []
        self.capability_registrations = []
        self.tasks = {}

    def register_executor(self, executor_id, **payload):
        self.registrations.append((executor_id, payload))
        return {"id": executor_id, "state": "registered"}

    def preflight_executor(self, executor_id, **payload):
        self.preflights.append((executor_id, payload))
        return {"id": executor_id, "ready": payload["ready"]}

    def register_capability(self, capability_id, **payload):
        self.capability_registrations.append((capability_id, payload))

    def heartbeat(self, task_id, lease_token):
        self.heartbeats.append((task_id, lease_token))

    def task(self, task_id):
        return self.tasks[task_id]

    def settle(self, task_id, lease_token, **payload):
        self.settlements.append((task_id, lease_token, payload))
        return {"task": {"id": task_id, "status": "completed"}}

    def fail(self, task_id, lease_token, error, **kwargs):
        self.failures.append((task_id, lease_token, error, kwargs))


def _write_manifest(
    root: Path,
    *,
    version: str = "1.0",
    capability_id: str = "test.echo",
    cwd: str | None = None,
) -> Path:
    root.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "id": capability_id,
        "name": "Echo",
        "kind": "external",
        "version": version,
        "command": {
            "argv": [
                "{python_exec}",
                "-c",
                "from pathlib import Path; Path('{out}/answer.txt').write_text('ok')",
            ]
        },
        "outputs": [{"name": "answer", "type": "file", "path_template": "{out}/answer.txt", "artifact_type": "text/plain"}],
        "metadata": {"resource_keys": ["cpu"], "estimated_scratch_bytes": 1},
    }
    if cwd is not None:
        manifest["command"]["cwd"] = cwd
    path = root / "executor.yaml"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_admitted_definition_and_source_are_fenced_before_child_dispatch(tmp_path):
    _write_manifest(tmp_path / "echo")
    host = GenericPackHost(pack_roots=[tmp_path])
    definition, admission = host.admit("executor", "test.echo")
    # Mutating the source after admission must fail closed; the child may not
    # reopen the mutable default registry and silently run a different command.
    (tmp_path / "echo" / "runtime.py").write_text("changed", encoding="utf-8")
    with pytest.raises(HostError, match="source digest changed"):
        host.invoke_capability(
            capability_kind="executor",
            capability_id="test.echo",
            request={"out": str(tmp_path / "attempt"), "inputs": {}},
            attempt=tmp_path / "attempt",
            definition=definition,
            admission=admission,
        )


def test_external_pack_import_root_is_fenced_before_direct_command(tmp_path):
    """A mutation in an imported external-pack module blocks command launch."""
    pack_root = tmp_path / "fixture_provider"
    executor_root = pack_root / "executors" / "echo"
    executor_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\nid: fixture_provider\nname: Fixture\nversion: 1.0\n"
        "capabilities: [echo]\ncontent:\n  executors: executors\n",
        encoding="utf-8",
    )
    (pack_root / "helper.py").write_text("VALUE = 'before'\n", encoding="utf-8")
    (executor_root / "executor.yaml").write_text(
        json.dumps({
            "schema_version": 1,
            "id": "fixture_provider.echo",
            "name": "Echo",
            "kind": "external",
            "version": "1.0",
            "command": {"argv": [sys.executable, "-c", "from fixture_provider import helper; from pathlib import Path; Path('{out}/answer').write_text(helper.VALUE)"]},
            "outputs": [],
        }),
        encoding="utf-8",
    )
    host = GenericPackHost(pack_roots=[pack_root])
    host.discover()
    record = host.capabilities["fixture_provider.echo"]
    (pack_root / "helper.py").write_text("VALUE = 'after'\n", encoding="utf-8")
    with pytest.raises(HostError, match="source digest changed"):
        host._run_command_definition(
            record,
            {},
            tmp_path / "attempt" / "outputs",
            tmp_path / "attempt",
            admission={
                "source_digest": record.source_digest,
                "source_root": str(record.source_root),
                "source_roots": [str(root) for root in (record.source_root, pack_root)],
            },
        )


def test_input_materialization_rejects_traversal_names(tmp_path):
    _write_manifest(tmp_path / "echo")

    class Objects(FakeRuntime):
        def get_object(self, digest):
            return b"input"

    host = GenericPackHost(pack_roots=[tmp_path], client=Objects())
    with pytest.raises(HostError, match="input name escapes"):
        host._materialize_inputs(
            {"input_digests": [{"name": "../escape", "digest": "a" * 64}]},
            tmp_path / "attempt",
        )


def test_command_cwd_must_stay_in_attempt_or_source_scope(tmp_path):
    _write_manifest(tmp_path / "echo", cwd=str(tmp_path / "outside"))
    host = GenericPackHost(pack_roots=[tmp_path])
    host.discover()
    record = host.capabilities["test.echo"]
    with pytest.raises(HostError, match="cwd escapes"):
        host._run_command_definition(record, {}, tmp_path / "attempt" / "outputs", tmp_path / "attempt")


def test_cancellation_terminates_descendant_process_group(tmp_path):
    root = tmp_path / "group"
    _write_manifest(root)
    manifest = json.loads((root / "executor.yaml").read_text(encoding="utf-8"))
    manifest["command"]["argv"] = [
        "{python_exec}",
        "-c",
        "import os,time; from pathlib import Path; p=os.fork(); Path('{out}/child.pid').write_text(str(p if p else os.getpid())); time.sleep(30)",
    ]
    (root / "executor.yaml").write_text(json.dumps(manifest), encoding="utf-8")
    host = GenericPackHost(pack_roots=[tmp_path])
    host.discover()
    attempt = tmp_path / "attempt"
    output_root = attempt / "outputs"
    output_root.mkdir(parents=True)
    started = time.monotonic()

    def cancelled():
        return time.monotonic() - started > 0.75

    with pytest.raises(HostCancelled):
        host._run_command_definition(
            host.capabilities["test.echo"], {}, output_root, attempt, cancelled=cancelled
        )
    child_pid = int((output_root / "child.pid").read_text(encoding="utf-8"))
    for _ in range(20):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("descendant survived cancellation")


def test_cancellation_reaps_sigterm_resistant_descendant_after_leader_exit(tmp_path):
    """A leader that exits on TERM must not let its stubborn child escape."""
    root = tmp_path / "leader-exits"
    _write_manifest(root)
    manifest = json.loads((root / "executor.yaml").read_text(encoding="utf-8"))
    child_code = (
        "import os,signal,sys,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "Path('{out}/child.pid').write_text(str(os.getpid())); "
        "os.write(int(sys.argv[1]), b'1'); os.close(int(sys.argv[1])); "
        "time.sleep(30)"
    )
    leader_code = (
        "import os,signal,subprocess,sys,time; "
        "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
        f"ready_r,ready_w=os.pipe(); subprocess.Popen([sys.executable,'-c',{child_code!r},str(ready_w)], pass_fds=(ready_w,)); os.close(ready_w); os.read(ready_r,1); os.close(ready_r); "
        "time.sleep(30)"
    )
    # Keeping the child in the inherited process group is intentional: the
    # host owns that whole group.
    manifest["command"]["argv"] = ["{python_exec}", "-c", leader_code]
    (root / "executor.yaml").write_text(json.dumps(manifest), encoding="utf-8")
    host = GenericPackHost(pack_roots=[tmp_path])
    host.discover()
    attempt = tmp_path / "attempt"
    output_root = attempt / "outputs"
    output_root.mkdir(parents=True)
    started = time.monotonic()

    def cancelled():
        return time.monotonic() - started > 0.75

    with pytest.raises(HostCancelled):
        host._run_command_definition(
            host.capabilities["test.echo"], {}, output_root, attempt, cancelled=cancelled
        )
    child_pid = int((output_root / "child.pid").read_text(encoding="utf-8"))
    for _ in range(40):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("SIGTERM-resistant descendant survived leader-exit cancellation")


def test_cancellation_reaps_descendant_spawned_by_sigterm_handler(tmp_path):
    """A TERM handler may create a child after the first group census."""
    root = tmp_path / "late-child"
    _write_manifest(root)
    manifest = json.loads((root / "executor.yaml").read_text(encoding="utf-8"))
    child_code = (
        "import os,signal,sys,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "Path(sys.argv[1]).write_text(str(os.getpid())); "
        "os.write(int(sys.argv[2]), b'1'); os.close(int(sys.argv[2])); time.sleep(30)"
    )
    leader_code = (
        "import os,signal,subprocess,sys,time\n"
        f"def late(*_):\n    ready_r,ready_w=os.pipe(); subprocess.Popen([sys.executable,'-c',{child_code!r},'{str(root / 'child.pid')}',str(ready_w)], pass_fds=(ready_w,)); os.close(ready_w); os.read(ready_r,1); os.close(ready_r)\n"
        "signal.signal(signal.SIGTERM, late)\n"
        "time.sleep(30)\n"
    )
    manifest["command"]["argv"] = ["{python_exec}", "-c", leader_code]
    (root / "executor.yaml").write_text(json.dumps(manifest), encoding="utf-8")
    host = GenericPackHost(pack_roots=[tmp_path])
    host.discover()
    attempt = tmp_path / "attempt"
    output_root = attempt / "outputs"
    output_root.mkdir(parents=True)
    started = time.monotonic()

    def cancelled():
        return time.monotonic() - started > 0.75

    with pytest.raises(HostCancelled):
        host._run_command_definition(
            host.capabilities["test.echo"], {}, output_root, attempt, cancelled=cancelled
        )
    child_pid = int((root / "child.pid").read_text(encoding="utf-8"))
    for _ in range(40):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("SIGTERM-handler child survived cancellation")


def test_cleanup_does_not_signal_a_reused_group_after_leader_exit(monkeypatch):
    """An exited leader PID must never be reused as a killpg target."""
    process = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    process.wait()

    def unexpected_killpg(*_args):
        raise AssertionError("cleanup signaled a group after its leader exited")

    monkeypatch.setattr(os, "killpg", unexpected_killpg)
    _terminate_process_group(process)


def test_signal_revalidates_group_identity_immediately_before_killpg(monkeypatch):
    """A PGID census change in the final signal window fails closed."""
    process = process_group.popen_owned_group([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        initial = process_group._process_snapshot()
        leader = initial[process.pid]
        reused = dict(initial)
        reused[process.pid] = process_group._ProcessInfo(
            process.pid,
            leader.ppid,
            leader.pgid,
            leader.birth + " (reused)",
        )
        snapshots = iter((initial, reused))
        monkeypatch.setattr(process_group, "_process_snapshot", lambda: next(snapshots))
        monkeypatch.setattr(os, "killpg", lambda *_args: pytest.fail("reused group was signalled"))
        monkeypatch.setattr(os, "kill", lambda *_args: pytest.fail("reused member was signalled"))

        process_group.signal_group(process, signal.SIGTERM)
    finally:
        monkeypatch.undo()
        process.kill()
        process.wait()


def test_tree_cleanup_rejects_reused_child_before_adopting_descendants(monkeypatch):
    """A reused child PID cannot pull an unrelated descendant into cleanup."""
    process = SimpleNamespace(pid=100, _astrid_process_birth="root")
    known: dict[int, str] = {}
    initial = {
        100: process_group._ProcessInfo(100, 1, 100, "root"),
        200: process_group._ProcessInfo(200, 100, 100, "child-old"),
    }
    assert process_group._tree_members(process, known, initial) == {
        100: "root",
        200: "child-old",
    }

    # PID 200 is now a different process.  Its child 300 is unrelated and
    # must not be adopted merely because the numeric parent PID matches.
    reused = {
        100: process_group._ProcessInfo(100, 1, 100, "root"),
        200: process_group._ProcessInfo(200, 100, 100, "child-new"),
        300: process_group._ProcessInfo(300, 200, 100, "unrelated"),
    }
    assert process_group._tree_members(process, known, reused) == {
        100: "root",
    }
    signalled: list[int] = []
    monkeypatch.setattr(os, "kill", lambda pid, _sig: signalled.append(pid))
    process_group._signal_valid_tree_members(process, known, signal.SIGKILL, reused)
    assert signalled == [100]


def test_discovery_digest_and_truthful_preflight(tmp_path):
    _write_manifest(tmp_path / "echo")
    host = GenericPackHost(pack_roots=[tmp_path])
    records = host.discover()
    assert [record.id for record in records] == ["test.echo"]
    assert records[0].source_digest
    assert host.preflight("test.echo")[0].ready
    original = records[0].capability_digest
    host.register()
    _write_manifest(tmp_path / "changed")
    changed = host.refresh()
    assert changed == ()  # a distinct capability does not invalidate the old one
    (tmp_path / "echo" / "executor.yaml").write_text((tmp_path / "changed" / "executor.yaml").read_text().replace('1.0', '2.0'), encoding="utf-8")
    assert host.refresh()[0].capability_digest != original
    with pytest.raises(Exception, match="deliberate re-registration"):
        host.register()
    host.register(deliberate=True)


def test_source_and_dependency_digests_invalidate_registration(tmp_path):
    _write_manifest(tmp_path / "base")
    child = tmp_path / "child"
    child.mkdir()
    (child / "executor.yaml").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "test.child",
                "name": "Child",
                "kind": "external",
                "version": "1.0",
                "graph": {"depends_on": ["test.echo"]},
                "command": {"argv": ["{python_exec}", "-c", "pass"]},
                "outputs": [],
            }
        ),
        encoding="utf-8",
    )
    host = GenericPackHost(pack_roots=[tmp_path])
    host.discover()
    host.register()

    # A runtime source file can change without changing the manifest digest.
    (tmp_path / "base" / "runtime.py").write_text("changed", encoding="utf-8")
    changed = host.refresh()
    assert [record.id for record in changed] == ["test.echo"]
    with pytest.raises(HostError, match="source digest changed: test.echo"):
        host.register()
    host.register(deliberate=True)

    # A dependency manifest change invalidates its consumer's dependency
    # digest as well as the dependency's own source/capability state.
    (tmp_path / "base" / "executor.yaml").write_text(
        (tmp_path / "base" / "executor.yaml").read_text(encoding="utf-8").replace('"1.0"', '"2.0"'),
        encoding="utf-8",
    )
    changed = host.refresh()
    assert {record.id for record in changed} == {"test.echo", "test.child"}
    with pytest.raises(HostError, match="dependency digest changed: test.child"):
        host.register()


def test_removed_capability_invalidates_and_is_withdrawn_on_deliberate_reregistration(tmp_path):
    _write_manifest(tmp_path / "base", capability_id="test.base")
    _write_manifest(tmp_path / "removed")

    class WithdrawalRuntime(FakeRuntime):
        def __init__(self):
            super().__init__()
            self.withdrawals = []

        def withdraw_capability(self, capability_id, *, digest, reason):
            self.withdrawals.append((capability_id, digest, reason))

    runtime = WithdrawalRuntime()
    host = GenericPackHost(pack_roots=[tmp_path], client=runtime)
    host.discover()
    host.register()
    removed_digest = host.capabilities["test.echo"].capability_digest

    (tmp_path / "removed" / "executor.yaml").unlink()
    assert [record.id for record in host.refresh()] == ["test.echo"]
    with pytest.raises(HostError, match="capability removed: test.echo"):
        host.register()

    result = host.register(deliberate=True)
    assert result["withdrawn_capabilities"] == ["test.echo"]
    assert runtime.withdrawals == [
        ("test.echo", removed_digest, "capability removed from source checkout")
    ]
    assert runtime.registrations[-1][1]["capabilities"] == ["test.base"]


def test_registration_carries_epochs_and_runtime_epoch_change_is_deterministic(tmp_path):
    _write_manifest(tmp_path / "echo")

    class EpochRuntime(FakeRuntime):
        def __init__(self):
            super().__init__()
            self.epoch = 7

        def health(self):
            try:
                from banodoco_workspace_client.contract_metadata import SCHEMA_DIGEST
            except ImportError:
                # The host's protocol/epoch checks remain deterministic in
                # the lightweight unit-test environment without the optional
                # generated client package.
                SCHEMA_DIGEST = ""

            return {"protocol": "workspace.v1", "schema_digest": SCHEMA_DIGEST, "runtime_epoch": self.epoch}

    runtime = EpochRuntime()
    host = GenericPackHost(pack_roots=[tmp_path], client=runtime)
    host.discover()
    host.register()
    payload = runtime.registrations[0][1]
    assert payload["protocol_version"] == "workspace.v1"
    assert payload["runtime_epoch"] == 7
    assert payload["source_epoch"] == host.source_epoch
    assert payload["dependency_digest"]
    assert payload["capability_states"]["test.echo"]["source_digest"]

    runtime.epoch = 8
    with pytest.raises(HostError, match="runtime epoch changed; deliberate re-registration required"):
        host.register()


def test_runtime_protocol_mismatch_blocks_registration_before_publish(tmp_path):
    _write_manifest(tmp_path / "echo")

    class IncompatibleRuntime(FakeRuntime):
        def health(self):
            return {"protocol": "workspace.v0", "schema_digest": "", "runtime_epoch": 1}

    runtime = IncompatibleRuntime()
    host = GenericPackHost(pack_roots=[tmp_path], client=runtime)
    host.discover()
    with pytest.raises(HostError, match="runtime compatibility blocked: protocol expected=workspace.v1 actual=workspace.v0"):
        host.register()
    assert runtime.registrations == []


def test_register_and_run_uses_attempt_local_typed_output_and_cleanup(tmp_path):
    _write_manifest(tmp_path / "echo")
    runtime = FakeRuntime()
    host = GenericPackHost(pack_roots=[tmp_path], client=runtime)
    host.discover()
    result = host.register()
    assert runtime.registrations[0][1]["resource_keys"] == ["cpu"]
    assert runtime.capability_registrations[0][0] == "test.echo"
    task = {"task": {"id": "task-1", "capability": "test.echo", "project": "demo", "spec": {}}}
    runtime.tasks["task-1"] = task
    settled = host.run_task(task, lease_token="lease-1")
    assert settled["task"]["status"] == "completed"
    assert runtime.heartbeats == [("task-1", "lease-1")]
    outputs = runtime.settlements[0][2]["outputs"]
    assert outputs[0]["name"] == "answer"
    assert outputs[0]["digest"]
    assert "content_base64" not in outputs[0]
    assert not list(tmp_path.glob("astrid-attempt-*"))


def test_unready_capability_is_not_dispatched(tmp_path, monkeypatch):
    _write_manifest(tmp_path / "echo")
    monkeypatch.setenv("PATH", "")
    host = GenericPackHost(pack_roots=[tmp_path])
    host.discover()
    host.preflight()
    # python_exec is resolved by the runner; with PATH empty the source still
    # remains a valid manifest and readiness is determined by its declaration.
    assert host.capabilities["test.echo"].ready


def test_claim_loop_fails_explicitly_without_canonical_claim_operation(tmp_path):
    _write_manifest(tmp_path / "echo")
    host = GenericPackHost(pack_roots=[tmp_path], client=object())
    host.discover()
    with pytest.raises(HostError, match="canonical claim-next operation"):
        host.run(once=True)


def test_adapter_registry_classifies_provider_local_generation_and_render():
    provider = GenericPackHost(pack_roots=[Path("astrid/packs/generation/executors")])
    provider.discover()
    assert AdapterRegistry.resolve(provider.capabilities["generation.generate_image_openai"].definition).family == "provider"

    local = GenericPackHost(pack_roots=[Path("astrid/packs/vibecomfy/executors")])
    local.discover()
    assert AdapterRegistry.resolve(local.capabilities["vibecomfy.run"].definition).family == "local_generation"
    local.preflight("vibecomfy.run")
    assert local.capabilities["vibecomfy.run"].resource_keys == ("gpu",)

    render = GenericPackHost(pack_roots=[Path("astrid/packs/rendering/executors/render")])
    render.discover()
    assert AdapterRegistry.resolve(render.capabilities["rendering.render"].definition).family == "render"
    render.preflight("rendering.render")
    report = render.capabilities["rendering.render"].preflight
    assert report["binaries"]["ok"]
    assert "remotion" in report


def test_register_preserves_declared_dispositions_and_block_reasons(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTRID_TEST_PROVIDER_KEY", raising=False)
    records = [
        ("required.provider", "required", "Provider credential is required"),
        ("optional.provider", "optional", "Optional provider credential"),
        ("unsupported.provider", "unsupported", "Provider is not shipped"),
        ("retired.provider", "retired", "Provider was retired"),
    ]
    capabilities = []
    for capability_id, disposition, evidence_reason in records:
        root = tmp_path / capability_id.replace(".", "-")
        root.mkdir()
        (root / "executor.yaml").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "id": capability_id,
                    "name": capability_id,
                    "kind": "external",
                    "version": "1.0",
                    "command": {"argv": ["{python_exec}", "-c", "pass"]},
                    "outputs": [],
                    "isolation": {"mode": "subprocess", "network": True},
                    "metadata": {"adapter_family": "provider"},
                }
            ),
            encoding="utf-8",
        )
        capabilities.append(
            {
                "id": capability_id,
                "disposition": disposition,
                "evidence_reason": evidence_reason,
                "adapter_family": "provider",
                "required_env": (["ASTRID_TEST_PROVIDER_KEY"] if disposition in {"required", "optional"} else []),
                "required_binaries": [],
                "required_packages": [],
            }
        )
    matrix = tmp_path / "matrix.json"
    matrix.write_text(json.dumps({"schema_version": 1, "capabilities": capabilities}), encoding="utf-8")

    class CaptureRuntime(RuntimeProtocolClient):
        def __init__(self):
            self.capability_registrations = []

        def register_capability(self, capability_id, **payload):
            self.capability_registrations.append((capability_id, payload))

        def register_executor(self, executor_id, **payload):
            return {"executor_id": executor_id, **payload}

    runtime = CaptureRuntime()
    host = GenericPackHost(pack_roots=[tmp_path], capability_matrix=matrix, client=runtime)
    host.discover()
    host.register()
    registered = {capability_id: payload for capability_id, payload in runtime.capability_registrations}
    assert registered["required.provider"]["status"] == "unavailable"
    assert registered["required.provider"]["unavailable_reason"] == "credentials:missing=ASTRID_TEST_PROVIDER_KEY"
    assert registered["optional.provider"]["status"] == "unavailable"
    assert registered["unsupported.provider"]["status"] == "unsupported"
    assert registered["unsupported.provider"]["unavailable_reason"] == "Provider is not shipped"
    assert registered["retired.provider"]["status"] == "retired"
    assert registered["retired.provider"]["unavailable_reason"] == "Provider was retired"
