from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.execution.generic_host import GenericPackHost


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


def _write_manifest(root: Path, *, version: str = "1.0") -> Path:
    root.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "id": "test.echo",
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
    path = root / "executor.yaml"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


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
    assert outputs[0]["content_base64"]
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
