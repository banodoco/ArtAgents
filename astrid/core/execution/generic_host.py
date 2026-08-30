"""Process-isolated generic executor host for the local runtime protocol.

This module deliberately contains no runtime/database/storage imports.  It is a
pack-side process: discovery and execution happen here, while admission,
leases, reservations, and settlement remain protocol operations on the daemon.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from astrid.core.execution.executor.runner import (
    ExecutorRunRequest,
    check_executor_binaries,
    run_executor,
)
from astrid.core.execution.executor.registry import ExecutorRegistry
from astrid.core.execution.executor.schema import ExecutorDefinition, ExecutorValidationError
from astrid.core.execution.executor.folder import discover_folder_executor_roots, load_folder_executor


class HostError(RuntimeError):
    """A controlled host-side error suitable for a worker diagnostic."""


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _source_digest(root: Path) -> str:
    """Hash the complete executor source tree without retaining a source path in a task."""
    entries: list[tuple[str, str]] = []
    if root.is_file():
        return hashlib.sha256(root.read_bytes()).hexdigest()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        entries.append((str(path.relative_to(root)), hashlib.sha256(path.read_bytes()).hexdigest()))
    return _canonical_digest(entries)


@dataclass(frozen=True)
class CapabilityRecord:
    definition: ExecutorDefinition
    capability_digest: str
    source_digest: str
    source_root: Path
    manifest_path: Path | None = None
    preflight: Mapping[str, Any] = field(default_factory=dict)
    ready: bool = False

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def resource_keys(self) -> tuple[str, ...]:
        metadata = self.definition.metadata
        values = metadata.get("resource_keys", metadata.get("resources", ()))
        if isinstance(values, str):
            values = (values,)
        return tuple(str(value) for value in (values or ()))

    @property
    def estimated_scratch_bytes(self) -> int:
        return int(self.definition.metadata.get("estimated_scratch_bytes", 0) or 0)

    @property
    def estimated_output_bytes(self) -> int:
        return int(self.definition.metadata.get("estimated_output_bytes", 0) or 0)

    def manifest(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "definition": self.definition.to_dict(),
            "capability_digest": self.capability_digest,
            "source_digest": self.source_digest,
            "source_root": str(self.source_root),
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "resource_keys": list(self.resource_keys),
            "estimated_scratch_bytes": self.estimated_scratch_bytes,
            "estimated_output_bytes": self.estimated_output_bytes,
            "preflight": dict(self.preflight),
            "ready": self.ready,
        }


class RuntimeProtocolClient:
    """Small generated-client-shaped transport used by the host.

    The host can be tested with a fake object implementing the same methods;
    production use speaks only JSON over the canonical runtime HTTP boundary.
    """

    def __init__(self, endpoint: str, credential: str, *, timeout: float = 30.0):
        self.endpoint = endpoint.rstrip("/")
        self.credential = credential
        self.timeout = timeout

    def request(self, method: str, path: str, payload: Any = None) -> Any:
        body = None if payload is None else json.dumps(payload, sort_keys=True).encode()
        request = urllib.request.Request(self.endpoint + path, data=body, method=method)
        request.add_header("Authorization", f"Bearer {self.credential}")
        if payload is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode())
            except Exception:
                detail = {"message": str(exc)}
            raise HostError(f"runtime request failed ({exc.code}): {detail}") from exc
        if not raw:
            return None
        data = json.loads(raw.decode())
        if isinstance(data, dict) and "ok" in data:
            if not data["ok"]:
                raise HostError(str(data.get("error")))
            return data.get("data")
        return data

    def register_executor(self, executor_id: str, *, capabilities: list[str], max_concurrency: int, resource_keys: list[str], source_digest: str | None):
        payload = {"executor_id": executor_id, "worker_id": executor_id, "capabilities": capabilities, "max_concurrency": max_concurrency, "resource_keys": resource_keys, "source_digest": source_digest}
        return self.request("POST", "/v1/executors", payload)

    def register_capability(self, capability_id: str, *, definition: Mapping[str, Any], digest: str):
        return self.request("POST", "/v1/capabilities", {"capability_id": capability_id, "definition": dict(definition), "digest": digest})

    def preflight_executor(self, executor_id: str, *, checks: Mapping[str, Any], ready: bool):
        return self.request("POST", f"/v1/executors/{executor_id}/preflight", {"checks": dict(checks), "ready": ready})

    def heartbeat(self, task_id: str, lease_token: str):
        return self.request("POST", f"/v1/tasks/{task_id}/heartbeat", {"lease_token": lease_token})

    def claim(self, task_id: str, worker_id: str, lease_token: str):
        return self.request("POST", f"/v1/tasks/{task_id}/claim", {"worker_id": worker_id, "lease_token": lease_token})

    def task(self, task_id: str):
        return self.request("GET", f"/v1/tasks/{task_id}")

    def settle(self, task_id: str, lease_token: str, *, result: Mapping[str, Any], outputs: list[dict[str, Any]], effect: Mapping[str, Any] | None):
        return self.request("POST", f"/v1/tasks/{task_id}/settle", {"lease_token": lease_token, "result": dict(result), "output_objects": outputs, "effect": effect})

    def fail(self, task_id: str, lease_token: str, error: str, *, retryable: bool = False):
        return self.request("POST", f"/v1/tasks/{task_id}/fail", {"lease_token": lease_token, "error": error, "retryable": retryable})

    def cancel(self, task_id: str):
        return self.request("POST", f"/v1/tasks/{task_id}/cancel", {})

    def get_object(self, digest: str) -> bytes:
        request = urllib.request.Request(self.endpoint + f"/v1/objects/{digest}", method="GET")
        request.add_header("Authorization", f"Bearer {self.credential}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise HostError(f"input object fetch failed ({exc.code})") from exc


class GenericPackHost:
    """Discover, register, preflight, and execute pack capabilities."""

    def __init__(self, *, pack_roots: list[str | Path], client: RuntimeProtocolClient | Any | None = None, executor_id: str = "astrid-pack-host", max_concurrency: int = 1, attempt_root: str | Path | None = None):
        self.pack_roots = tuple(Path(root).expanduser().resolve() for root in pack_roots)
        self.client = client
        self.executor_id = executor_id
        self.max_concurrency = max(1, int(max_concurrency))
        self.attempt_root = Path(attempt_root).expanduser().resolve() if attempt_root else None
        self.capabilities: dict[str, CapabilityRecord] = {}
        self._registered_digests: dict[str, str] = {}

    def discover(self) -> tuple[CapabilityRecord, ...]:
        records: dict[str, CapabilityRecord] = {}
        for root in self.pack_roots:
            for executor_root in discover_folder_executor_roots(root):
                try:
                    definition = load_folder_executor(executor_root)
                except (ExecutorValidationError, OSError, ValueError) as exc:
                    # A broken optional manifest is unavailable, but does not hide
                    # neighboring packs.  The manifest report records the reason.
                    continue
                manifest = next((executor_root / name for name in ("executor.yaml", "executor.yml", "executor.json") if (executor_root / name).is_file()), None)
                record = CapabilityRecord(definition=definition, capability_digest=_canonical_digest(definition.to_dict()), source_digest=_source_digest(executor_root), source_root=executor_root, manifest_path=manifest)
                records[record.id] = record
        self.capabilities = records
        return tuple(records[key] for key in sorted(records))

    def preflight(self, capability_id: str | None = None) -> tuple[CapabilityRecord, ...]:
        selected = [self.capabilities[capability_id]] if capability_id else list(self.capabilities.values())
        updated: dict[str, CapabilityRecord] = dict(self.capabilities)
        for record in selected:
            checks: dict[str, Any] = {"source": record.source_root.is_dir(), "definition": True}
            missing = list(check_executor_binaries(record.definition))
            if missing:
                checks["binaries"] = {"ok": False, "missing": missing}
            else:
                checks["binaries"] = {"ok": True}
            required_env = record.definition.metadata.get("required_env", record.definition.metadata.get("required_credentials", record.definition.metadata.get("env", ())))
            missing_env = [str(name) for name in (required_env or ()) if not os.environ.get(str(name))]
            checks["credentials"] = {"ok": not missing_env, "missing": missing_env}
            ready = all(value is True or (isinstance(value, dict) and value.get("ok") is True) for value in checks.values())
            updated[record.id] = CapabilityRecord(**{**record.__dict__, "preflight": checks, "ready": ready})
        self.capabilities = updated
        return tuple(updated[key] for key in sorted(updated) if capability_id is None or key == capability_id)

    def register(self, *, deliberate: bool = False) -> dict[str, Any]:
        if not self.capabilities:
            self.discover()
        self.preflight()
        changed = [key for key, record in self.capabilities.items() if key in self._registered_digests and self._registered_digests[key] != record.capability_digest]
        if changed and not deliberate:
            raise HostError("capability digest changed; deliberate re-registration required: " + ", ".join(sorted(changed)))
        if self.client is None:
            self._registered_digests = {key: record.capability_digest for key, record in self.capabilities.items()}
            return {"executor_id": self.executor_id, "capabilities": [r.manifest() for r in self.capabilities.values()], "ready": [r.id for r in self.capabilities.values() if r.ready]}
        all_keys = sorted({key for record in self.capabilities.values() for key in record.resource_keys})
        registration = self.client.register_executor(self.executor_id, capabilities=sorted(self.capabilities), max_concurrency=self.max_concurrency, resource_keys=all_keys, source_digest=_canonical_digest({key: record.source_digest for key, record in self.capabilities.items()}))
        if hasattr(self.client, "register_capability"):
            for record in self.capabilities.values():
                self.client.register_capability(record.id, definition=record.definition.to_dict(), digest=record.capability_digest)
        for record in self.capabilities.values():
            self.client.preflight_executor(record.id, checks=record.preflight, ready=record.ready)
        self._registered_digests = {key: record.capability_digest for key, record in self.capabilities.items()}
        return {"registration": registration, "capabilities": [r.manifest() for r in self.capabilities.values()]}

    def refresh(self) -> tuple[CapabilityRecord, ...]:
        """Re-scan source and report digest changes; callers must register again."""
        old = self.capabilities
        self.discover()
        changed = []
        for key, record in self.capabilities.items():
            if key in old and old[key].capability_digest != record.capability_digest:
                changed.append(key)
        return tuple(self.capabilities[key] for key in changed)

    def _materialize_inputs(self, spec: Mapping[str, Any], attempt: Path) -> dict[str, Any]:
        values = dict(spec.get("inputs", {})) if isinstance(spec.get("inputs", {}), Mapping) else {}
        for item in spec.get("input_digests", ()) if isinstance(spec.get("input_digests", ()), list) else ():
            if isinstance(item, Mapping) and item.get("name") and item.get("digest"):
                values.setdefault(str(item["name"]), {"digest": str(item["digest"])})
        for name, value in list(values.items()):
            digest = value.get("digest") if isinstance(value, Mapping) else (value if isinstance(value, str) and len(value) == 64 else None)
            if digest and self.client is not None and hasattr(self.client, "get_object"):
                data = self.client.get_object(digest)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise HostError(f"input object hash mismatch for {name}")
                path = attempt / "inputs" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                values[name] = str(path)
        return values

    def _typed_outputs(self, record: CapabilityRecord, result: Any, attempt: Path) -> list[dict[str, Any]]:
        paths = getattr(result, "outputs", {}) or {}
        outputs: list[dict[str, Any]] = []
        by_name = {output.name: output for output in record.definition.outputs}
        for name, raw_path in paths.items():
            path = Path(raw_path).resolve()
            if not path.is_file() or not path.is_relative_to(attempt):
                raise HostError(f"declared output {name!r} is not inside the attempt directory")
            data = path.read_bytes()
            output = by_name.get(name)
            outputs.append({"name": name, "artifact_type": getattr(output, "artifact_type", None), "digest": hashlib.sha256(data).hexdigest(), "size": len(data), "content_base64": base64.b64encode(data).decode("ascii")})
        return outputs

    def _run_command_definition(self, record: CapabilityRecord, inputs: Mapping[str, Any], output_root: Path, attempt: Path) -> Any:
        """Run a manifest command without importing Astrid's project authority.

        The legacy runner is still available for built-in pipeline steps, but
        command capabilities must be runnable from an attempt directory alone.
        """
        command = record.definition.command
        if command is None:
            raise HostError(f"capability {record.id!r} has no dispatchable command")
        values = {"out": str(output_root), "run_root": str(attempt), "python_exec": sys.executable, **inputs}
        argv = [str(part) for part in command.argv]
        for index, part in enumerate(argv):
            for key, value in values.items():
                argv[index] = argv[index].replace("{" + key + "}", str(value))
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in command.env.items()})
        completed = subprocess.run(argv, cwd=str(command.cwd or attempt), env=env, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise HostError(f"capability {record.id!r} exited {completed.returncode}: {(completed.stderr or completed.stdout).strip()}")
        outputs = {}
        for output in record.definition.outputs:
            template = output.path_template or output.placeholder
            if template:
                path = template.replace("{out}", str(output_root)).replace("{run_root}", str(attempt))
            else:
                path = str(output_root / output.name)
            candidate = Path(path)
            if candidate.is_file():
                outputs[output.name] = str(candidate)
        return type("CommandResult", (), {"outputs": outputs, "payload": {"returncode": completed.returncode, "capability_digest": record.capability_digest}})()

    def run_task(self, task: Mapping[str, Any], *, lease_token: str, keep_attempt: bool = False) -> Mapping[str, Any]:
        task_data = task.get("task", task)
        task_id = str(task_data["id"])
        capability_id = str(task_data["capability"])
        record = self.capabilities.get(capability_id)
        if record is None:
            self.discover()
            record = self.capabilities.get(capability_id)
        if record is None:
            raise HostError(f"capability not discovered: {capability_id}")
        if not record.ready:
            self.preflight(capability_id)
            record = self.capabilities[capability_id]
        if not record.ready:
            raise HostError(f"capability {capability_id!r} is unavailable: {record.preflight}")
        spec = task_data.get("spec", {})
        root = self.attempt_root or Path(tempfile.mkdtemp(prefix=f"astrid-attempt-{task_id}-")).resolve()
        root.mkdir(parents=True, exist_ok=True)
        try:
            inputs = self._materialize_inputs(spec, root)
            output_root = root / "outputs"
            output_root.mkdir(parents=True, exist_ok=True)
            if self.client is not None and hasattr(self.client, "heartbeat"):
                self.client.heartbeat(task_id, lease_token)
            if record.definition.command is not None:
                result = self._run_command_definition(record, inputs, output_root, root)
            else:
                request = ExecutorRunRequest(executor_id=capability_id, out=output_root, inputs=inputs, project=task_data.get("project"), project_was_auto_resolved=True, python_exec=sys.executable, run_id=task_id, run_root=root, execution_mode="subprocess", invocation="runtime")
                # Dispatch against the immutable definition selected at
                # admission, rather than reloading a mutable global registry.
                result = run_executor(request, ExecutorRegistry([record.definition]))
            if self.client is not None and hasattr(self.client, "task"):
                current = self.client.task(task_id)
                current_task = current.get("task", current) if isinstance(current, Mapping) else {}
                if current_task.get("status") == "cancelled":
                    return {"task_id": task_id, "status": "cancelled", "cancelled": True}
            outputs = self._typed_outputs(record, result, root)
            payload = getattr(result, "payload", {}) or {}
            effect = task_data.get("expected_effect")
            if isinstance(effect, list):
                effect = effect[0] if effect else None
            if self.client is not None:
                settlement = self.client.settle(task_id, lease_token, result=payload, outputs=outputs, effect=effect)
            else:
                settlement = {"task_id": task_id, "result": payload, "output_objects": outputs, "effect": effect}
            return settlement
        except Exception as exc:
            if self.client is not None and hasattr(self.client, "fail"):
                self.client.fail(task_id, lease_token, str(exc), retryable=False)
            raise
        finally:
            if not keep_attempt and self.attempt_root is None:
                shutil.rmtree(root, ignore_errors=True)


def _cli() -> int:
    parser = argparse.ArgumentParser(prog="astrid-generic-host")
    parser.add_argument("--pack-root", action="append", required=True, help="pack/executor root to discover")
    parser.add_argument("--runtime-endpoint")
    parser.add_argument("--credential")
    parser.add_argument("--executor-id", default="astrid-pack-host")
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--attempt-root")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--run-task")
    parser.add_argument("--lease-token")
    parser.add_argument("--keep-attempt", action="store_true")
    args = parser.parse_args()
    client = RuntimeProtocolClient(args.runtime_endpoint, args.credential) if args.runtime_endpoint else None
    host = GenericPackHost(pack_roots=args.pack_root, client=client, executor_id=args.executor_id, max_concurrency=args.max_concurrency, attempt_root=args.attempt_root)
    host.discover()
    host.preflight()
    if args.register or not args.run_task:
        print(json.dumps(host.register() if args.register else {"capabilities": [record.manifest() for record in host.capabilities.values()]}, indent=2, sort_keys=True))
    if args.run_task:
        if client is None or not args.lease_token:
            parser.error("--run-task requires --runtime-endpoint, --credential, and --lease-token")
        task = client.task(args.run_task)
        print(json.dumps(host.run_task(task, lease_token=args.lease_token, keep_attempt=args.keep_attempt), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
