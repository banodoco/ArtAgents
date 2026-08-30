"""Process-isolated generic executor host for the local runtime protocol.

This module deliberately contains no runtime/database/storage imports.  It is a
pack-side process: discovery and execution happen here, while admission,
leases, reservations, and settlement remain protocol operations on the daemon.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import subprocess
import tempfile
import threading
import time
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


class HostCancelled(HostError):
    """The runtime cancelled the attempt while the subprocess was running."""


@dataclass(frozen=True)
class AdapterSpec:
    family: str
    resource_keys: tuple[str, ...] = ()
    required_binaries: tuple[str, ...] = ()
    required_packages: tuple[str, ...] = ()
    requires_network: bool = False


class AdapterRegistry:
    """Small explicit family map; adapter code stays behind the host seam."""

    _specs = {
        "cpu": AdapterSpec("cpu", ("cpu",)),
        "provider": AdapterSpec("provider", ("provider",), requires_network=True),
        "render": AdapterSpec("render", ("render",), ("node", "ffmpeg")),
        "local_generation": AdapterSpec("local_generation", ("gpu",), ()),
    }

    @classmethod
    def resolve(cls, definition: ExecutorDefinition) -> AdapterSpec:
        metadata = definition.metadata
        explicit = metadata.get("adapter_family") or metadata.get("adapter")
        if explicit:
            family = str(explicit)
        elif definition.id.startswith("rendering.") or "render" in definition.id:
            family = "render"
        elif definition.id.startswith(("vibecomfy.", "comfy_wrap.")) or metadata.get("vibecomfy_command"):
            family = "local_generation"
        elif metadata.get("api_provider") or metadata.get("env") or metadata.get("secrets_required") or definition.isolation.network:
            family = "provider"
        else:
            family = "cpu"
        return cls._specs.get(family, AdapterSpec(family))

    @classmethod
    def families(cls) -> tuple[str, ...]:
        return tuple(sorted(cls._specs))

    @classmethod
    def from_matrix(cls, definition: ExecutorDefinition, entry: Mapping[str, Any] | None = None) -> AdapterSpec:
        base = cls.resolve(definition)
        entry = entry or {}
        family = str(entry.get("adapter_family") or base.family)
        if family not in cls._specs:
            raise HostError(f"unknown adapter family {family!r} for {definition.id!r}")
        builtin = cls._specs[family]
        return AdapterSpec(
            family,
            tuple(entry.get("resource_keys") or builtin.resource_keys),
            tuple(entry.get("required_binaries") or builtin.required_binaries),
            tuple(entry.get("required_packages") or builtin.required_packages),
            builtin.requires_network,
        )


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
    matrix: Mapping[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def resource_keys(self) -> tuple[str, ...]:
        metadata = self.definition.metadata
        values = metadata.get("resource_keys", metadata.get("resources", ()))
        if isinstance(values, str):
            values = (values,)
        declared = tuple(str(value) for value in (values or ()))
        adapter = AdapterRegistry.from_matrix(self.definition, self.matrix)
        return tuple(dict.fromkeys((*adapter.resource_keys, *declared)))

    @property
    def adapter(self) -> AdapterSpec:
        return AdapterRegistry.from_matrix(self.definition, self.matrix)

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
            "inputs": [port.__dict__ for port in self.definition.inputs],
            "outputs": [output.__dict__ for output in self.definition.outputs],
            "capability_digest": self.capability_digest,
            "source_digest": self.source_digest,
            "source_root": str(self.source_root),
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "resource_keys": list(self.resource_keys),
            "estimated_scratch_bytes": self.estimated_scratch_bytes,
            "estimated_output_bytes": self.estimated_output_bytes,
            "adapter_family": self.adapter.family,
            "disposition": self.matrix.get("disposition", "unclassified"),
            "evidence_reason": self.matrix.get("evidence_reason", ""),
            "preflight": dict(self.preflight),
            "ready": self.ready,
        }


class RuntimeProtocolClient:
    """Host adapter composed over the generated workspace client.

    This class intentionally contains no HTTP implementation.  The generated
    client owns transport, envelopes, authentication, and route paths; this
    adapter only translates host lifecycle values to its typed operations.
    """

    def __init__(self, endpoint: str, credential: str, *, timeout: float = 30.0):
        self.endpoint = endpoint.rstrip("/")
        self.credential = credential
        self.timeout = timeout
        try:
            from banodoco_workspace_client import WorkspaceClient
        except ImportError as exc:
            raise HostError(
                "generated banodoco_workspace_client is unavailable; install the "
                "workspace runtime client or set PYTHONPATH to its packages/python"
            ) from exc
        self.generated = WorkspaceClient(self.endpoint, self.credential)

    def register_executor(self, executor_id: str, *, capabilities: list[str], max_concurrency: int, resource_keys: list[str], source_digest: str | None, capability_digests: Mapping[str, str] | None = None):
        payload = {
            "executor_id": executor_id,
            "capabilities": capabilities,
            "max_concurrency": max_concurrency,
            "resource_keys": resource_keys,
            "protocol": "workspace.v1",
            "source_digest": source_digest,
            "capability_digests": dict(capability_digests or {}),
            "definition_digests": dict(capability_digests or {}),
        }
        try:
            return self.generated.register_executor(payload, idempotency_key=f"executor:{executor_id}")
        except TypeError:
            # control2 currently returns capability ids while the generated
            # response model expects expanded capability records.  The HTTP
            # operation has succeeded; preserve its neutral response shape.
            return payload

    def register_capability(self, capability_id: str, *, definition: Mapping[str, Any], digest: str):
        raise HostError(
            "generated workspace client has no capability-registration operation; "
            "runtime client route needed: POST /v1/capabilities"
        )

    def preflight_executor(self, executor_id: str, *, checks: Mapping[str, Any], ready: bool):
        return {"executor_id": executor_id, "checks": dict(checks), "ready": ready}

    def heartbeat(self, task_id: str, lease_token: str, *, attempt_id: str | None = None, fence: int | None = None):
        if not attempt_id or fence is None:
            raise HostError("generated heartbeat requires attempt_id and fence")
        return self.generated.heartbeat_attempt(
            attempt_id,
            lease_id=lease_token,
            fence=int(fence),
            idempotency_key=f"heartbeat:{attempt_id}:{fence}",
        )

    def claim(self, task_id: str, worker_id: str, lease_token: str):
        raise HostError("per-task claim is not a canonical operation; use claim_task")

    def claim_next(self, *, executor_id: str, capability_ids: list[str], idempotency_key: str):
        if not hasattr(self.generated, "claim_task"):
            raise HostError("generated workspace client lacks claim-next operation: POST /v1/tasks/claim")
        return self.generated.claim_task(
            executor_id=executor_id,
            capability_ids=capability_ids,
            idempotency_key=idempotency_key,
        )

    def task(self, task_id: str):
        return self.generated.get_task(task_id)

    def settle(self, task_id: str, lease_token: str, *, result: Mapping[str, Any], outputs: list[dict[str, Any]], effect: Mapping[str, Any] | None, attempt_id: str | None = None, fence: int | None = None):
        if not attempt_id or fence is None:
            raise HostError("generated settlement requires attempt_id and fence")
        settlement = {
            "attempt_id": attempt_id,
            "lease_id": lease_token,
            "fence": int(fence),
            "outputs": outputs,
            "effect": effect,
            "result": dict(result),
        }
        return self.generated.settle_attempt(
            attempt_id,
            settlement,
            idempotency_key=f"settle:{attempt_id}:{fence}",
        )

    def fail(self, task_id: str, lease_token: str, error: str, *, retryable: bool = False):
        raise HostError(
            "generated workspace client has no attempt-fail operation; "
            "runtime client route needed: POST /v1/attempts/{attempt_id}/fail"
        )

    def cancel(self, task_id: str):
        return self.generated.cancel_task(task_id, idempotency_key=f"cancel:{task_id}")

    def get_object(self, digest: str) -> bytes:
        response = self.generated.get_object(digest)
        return response.data

    def upload_object(self, path: Path, *, media_type: str, filename: str | None = None):
        with path.open("rb") as stream:
            data = stream.read()
            return self.generated.ingest_object(
                data,
                media_type=media_type,
                idempotency_key=f"output:{hashlib.sha256(data).hexdigest()}",
                filename=filename,
            )


class GenericPackHost:
    """Discover, register, preflight, and execute pack capabilities."""

    def __init__(self, *, pack_roots: list[str | Path], client: RuntimeProtocolClient | Any | None = None, executor_id: str = "astrid-pack-host", max_concurrency: int = 1, attempt_root: str | Path | None = None, capability_matrix: str | Path | None = None):
        self.pack_roots = tuple(Path(root).expanduser().resolve() for root in pack_roots)
        self.client = client
        self.executor_id = executor_id
        self.max_concurrency = max(1, int(max_concurrency))
        self.attempt_root = Path(attempt_root).expanduser().resolve() if attempt_root else None
        self.capabilities: dict[str, CapabilityRecord] = {}
        self._registered_digests: dict[str, str] = {}
        self.capability_matrix_path = Path(capability_matrix).expanduser().resolve() if capability_matrix else self._default_matrix_path()
        self.matrix: dict[str, dict[str, Any]] = self._load_matrix(self.capability_matrix_path)

    def _default_matrix_path(self) -> Path | None:
        checkout = Path(__file__).resolve().parents[3]
        candidate = checkout / "config" / "astrid-beta-capabilities.json"
        source_pack_root = checkout / "astrid" / "packs"
        if candidate.is_file() and any(root == source_pack_root for root in self.pack_roots):
            return candidate
        return None

    @staticmethod
    def _load_matrix(path: Path | None) -> dict[str, dict[str, Any]]:
        if path is None:
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HostError(f"cannot read capability matrix {path}: {exc}") from exc
        if payload.get("schema_version") != 1 or not isinstance(payload.get("capabilities"), list):
            raise HostError("capability matrix requires schema_version 1 and a capabilities list")
        allowed = {"required", "optional", "unsupported", "retired"}
        result = {}
        for entry in payload["capabilities"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                raise HostError("capability matrix entries require an id")
            if entry.get("disposition") not in allowed:
                raise HostError(f"invalid capability disposition for {entry.get('id')!r}")
            if not entry.get("evidence_reason"):
                raise HostError(f"capability matrix entry {entry['id']!r} needs evidence_reason")
            if entry["id"] in result:
                raise HostError(f"duplicate capability matrix entry {entry['id']!r}")
            result[entry["id"]] = entry
        return result

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
                matrix_entry = self.matrix.get(definition.id, {})
                record = CapabilityRecord(definition=definition, capability_digest=_canonical_digest(definition.to_dict()), source_digest=_source_digest(executor_root), source_root=executor_root, manifest_path=manifest, matrix=matrix_entry)
                records[record.id] = record
        if self.matrix:
            discovered = set(records)
            expected = set(self.matrix)
            missing = sorted(discovered - expected)
            stale = sorted(expected - discovered)
            if missing or stale:
                details = []
                if missing:
                    details.append("missing matrix entries: " + ", ".join(missing))
                if stale:
                    details.append("matrix entries not discovered: " + ", ".join(stale))
                raise HostError("capability matrix does not exactly cover discovered corpus; " + "; ".join(details))
        self.capabilities = records
        return tuple(records[key] for key in sorted(records))

    def preflight(self, capability_id: str | None = None) -> tuple[CapabilityRecord, ...]:
        selected = [self.capabilities[capability_id]] if capability_id else list(self.capabilities.values())
        updated: dict[str, CapabilityRecord] = dict(self.capabilities)
        for record in selected:
            checks: dict[str, Any] = {"source": record.source_root.is_dir(), "definition": True}
            adapter = record.adapter
            matrix_binaries = tuple(str(binary) for binary in record.matrix.get("required_binaries", ()))
            binary_requirements = tuple(dict.fromkeys((*record.definition.isolation.binaries, *matrix_binaries, *adapter.required_binaries)))
            missing = list(dict.fromkeys(binary for binary in binary_requirements if shutil.which(binary) is None))
            if missing:
                checks["binaries"] = {"ok": False, "missing": missing}
            else:
                checks["binaries"] = {"ok": True}
            required_env = record.matrix.get("required_env") or record.definition.metadata.get("required_env", record.definition.metadata.get("required_credentials", record.definition.metadata.get("env", ())))
            missing_env = [str(name) for name in (required_env or ()) if not os.environ.get(str(name))]
            checks["credentials"] = {"ok": not missing_env, "missing": missing_env}
            required_packages = record.matrix.get("required_packages") or record.definition.metadata.get("required_packages", adapter.required_packages)
            missing_packages = [package for package in (required_packages or ()) if importlib.util.find_spec(str(package)) is None]
            checks["packages"] = {"ok": not missing_packages, "missing": missing_packages}
            if adapter.family == "render":
                checkout = next((parent.parent for parent in (record.source_root, *record.source_root.parents) if parent.name == "astrid" and (parent.parent / "remotion").is_dir()), None)
                package_json = checkout / "remotion" / "package.json" if checkout else None
                lock_file = checkout / "remotion" / "package-lock.json" if checkout else None
                node_modules = checkout / "remotion" / "node_modules" if checkout else None
                checks["remotion"] = {"ok": bool(package_json and lock_file and node_modules and node_modules.is_dir()), "package_json": str(package_json) if package_json else None, "lock_file": str(lock_file) if lock_file else None, "dependencies": str(node_modules) if node_modules else None}
            if adapter.requires_network and not record.definition.isolation.network:
                checks["network"] = {"ok": False, "reason": "adapter_requires_network"}
            else:
                checks["network"] = {"ok": True}
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
        digests = {key: record.capability_digest for key, record in self.capabilities.items()}
        registration_kwargs = {
            "capabilities": sorted(self.capabilities),
            "max_concurrency": self.max_concurrency,
            "resource_keys": all_keys,
            "source_digest": _canonical_digest({key: record.source_digest for key, record in self.capabilities.items()}),
            "capability_digests": digests,
        }
        try:
            registration = self.client.register_executor(self.executor_id, **registration_kwargs)
        except TypeError as exc:
            if "capability_digests" not in str(exc):
                raise
            registration_kwargs.pop("capability_digests")
            registration = self.client.register_executor(self.executor_id, **registration_kwargs)
        # Legacy fakes retain their old registration seam.  The generated
        # client has no capability-registration operation yet, so its
        # canonical definition digests travel in the executor registration;
        # do not fall back to hand-written HTTP here.
        if hasattr(self.client, "register_capability") and not isinstance(self.client, RuntimeProtocolClient):
            for record in self.capabilities.values():
                self.client.register_capability(record.id, definition=record.definition.to_dict(), digest=record.capability_digest)
        if not isinstance(self.client, RuntimeProtocolClient):
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
            output = by_name.get(name)
            outputs.append({
                "name": name,
                "artifact_type": getattr(output, "artifact_type", None),
                "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
                "path": str(path),
            })
        return outputs

    def _upload_outputs(self, outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Publish staged outputs and return settlement-safe object refs."""
        uploaded: list[dict[str, Any]] = []
        for descriptor in outputs:
            path = Path(str(descriptor.pop("path")))
            if self.client is not None and hasattr(self.client, "upload_object"):
                media_type = str(descriptor.get("artifact_type") or "application/octet-stream")
                object_row = self.client.upload_object(path, media_type=media_type, filename=path.name)
                object_id = getattr(object_row, "object_id", None)
                digest = getattr(object_row, "digest", None)
                if not object_id or not digest:
                    raise HostError("generated object upload returned no canonical object id/digest")
                uploaded.append({
                    "name": descriptor.get("name"),
                    "media_type": media_type,
                    "object_id": object_id,
                    "digest": digest,
                    "size": int(getattr(object_row, "size", descriptor.get("size", 0))),
                })
            else:
                # Offline and legacy fakes receive a digest-only reference;
                # never put staged bytes in a settlement payload.
                uploaded.append({key: value for key, value in descriptor.items() if key != "path"})
        return uploaded

    def _run_command_definition(self, record: CapabilityRecord, inputs: Mapping[str, Any], output_root: Path, attempt: Path, *, cancelled=None) -> Any:
        """Run a manifest command without importing Astrid's project authority.

        The legacy runner is still available for built-in pipeline steps, but
        command capabilities must be runnable from an attempt directory alone.
        """
        command = record.definition.command
        if command is None:
            raise HostError(f"capability {record.id!r} has no dispatchable command")
        values = {"out": str(output_root), "run_root": str(attempt), "python_exec": sys.executable, **inputs}
        for port in record.definition.inputs:
            if port.name not in values and port.default is not None:
                values[port.name] = port.default
        for output in record.definition.outputs:
            if output.name not in values and output.name == "video":
                values["output_name"] = "hype.mp4"
        argv = [str(part) for part in command.argv]
        for index, part in enumerate(argv):
            for key, value in values.items():
                argv[index] = argv[index].replace("{" + key + "}", str(value))
        for input_arg in command.input_args:
            value = values.get(input_arg.input)
            if value in (None, "") or any("{" + input_arg.input + "}" in part for part in command.argv):
                continue
            items = value if input_arg.repeatable and isinstance(value, (list, tuple)) else (value,)
            for item in items:
                if input_arg.flag:
                    argv.extend((input_arg.flag, str(item)))
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in command.env.items()})
        process = subprocess.Popen(argv, cwd=str(command.cwd or attempt), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        while process.poll() is None:
            if cancelled is not None and cancelled():
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise HostCancelled(f"capability {record.id!r} cancelled")
            time.sleep(0.05)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise HostError(f"capability {record.id!r} exited {process.returncode}: {(stderr or stdout).strip()}")
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
        return type("CommandResult", (), {"outputs": outputs, "payload": {"returncode": process.returncode, "capability_digest": record.capability_digest}})()

    def run_task(
        self,
        task: Mapping[str, Any],
        *,
        lease_token: str,
        attempt_id: str | None = None,
        fence: int | None = None,
        keep_attempt: bool = False,
    ) -> Mapping[str, Any]:
        task_data = task.get("task", task)
        task_id = str(task_data["id"])
        capability_id = str(task_data["capability"])
        attempt_id = attempt_id or (str(task_data["attempt_id"]) if task_data.get("attempt_id") else None)
        fence = fence if fence is not None else (int(task_data["fence"]) if task_data.get("fence") is not None else None)
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
        settled = False
        try:
            inputs = self._materialize_inputs(spec, root)
            output_root = root / "outputs"
            output_root.mkdir(parents=True, exist_ok=True)
            cancel_signal = threading.Event()
            pump_stop = threading.Event()
            if self.client is not None and hasattr(self.client, "heartbeat"):
                try:
                    self.client.heartbeat(task_id, lease_token, attempt_id=attempt_id, fence=fence)
                except TypeError:
                    self.client.heartbeat(task_id, lease_token)

                def pump_lease():
                    while not pump_stop.wait(5.0):
                        try:
                            try:
                                self.client.heartbeat(task_id, lease_token, attempt_id=attempt_id, fence=fence)
                            except TypeError:
                                self.client.heartbeat(task_id, lease_token)
                            if hasattr(self.client, "task"):
                                current = self.client.task(task_id)
                                current_task = current.get("task", current) if isinstance(current, Mapping) else current
                                state = current_task.get("status") if isinstance(current_task, Mapping) else getattr(current_task, "state", None)
                                if state == "cancelled":
                                    cancel_signal.set()
                        except Exception:
                            # The daemon fences settlement if a heartbeat is
                            # lost; the subprocess is still cleaned up here.
                            cancel_signal.set()

                pump_thread = threading.Thread(target=pump_lease, name=f"astrid-heartbeat-{task_id}", daemon=True)
                pump_thread.start()
            else:
                pump_thread = None

            def cancelled():
                if cancel_signal.is_set():
                    return True
                if self.client is None or not hasattr(self.client, "task"):
                    return False
                current = self.client.task(task_id)
                current_task = current.get("task", current) if isinstance(current, Mapping) else current
                state = current_task.get("status") if isinstance(current_task, Mapping) else getattr(current_task, "state", None)
                return state == "cancelled"

            try:
                if record.definition.command is not None:
                    result = self._run_command_definition(record, inputs, output_root, root, cancelled=cancelled)
                else:
                    request = ExecutorRunRequest(executor_id=capability_id, out=output_root, inputs=inputs, project=task_data.get("project"), project_was_auto_resolved=True, python_exec=sys.executable, run_id=task_id, run_root=root, execution_mode="subprocess", invocation="runtime")
                    # Dispatch against the immutable definition selected at
                    # admission, rather than reloading a mutable global registry.
                    result = run_executor(request, ExecutorRegistry([record.definition]))
            finally:
                pump_stop.set()
                if pump_thread is not None:
                    pump_thread.join(timeout=2)
            if self.client is not None and hasattr(self.client, "task"):
                current = self.client.task(task_id)
                current_task = current.get("task", current) if isinstance(current, Mapping) else current
                state = current_task.get("status") if isinstance(current_task, Mapping) else getattr(current_task, "state", None)
                if state == "cancelled":
                    return {"task_id": task_id, "status": "cancelled", "cancelled": True}
            outputs = self._upload_outputs(self._typed_outputs(record, result, root))
            payload = {"adapter_family": record.adapter.family, **(getattr(result, "payload", {}) or {})}
            effect = task_data.get("expected_effect")
            if isinstance(effect, list):
                effect = effect[0] if effect else None
            if self.client is not None:
                try:
                    settlement = self.client.settle(
                        task_id,
                        lease_token,
                        result=payload,
                        outputs=outputs,
                        effect=effect,
                        attempt_id=attempt_id,
                        fence=fence,
                    )
                except TypeError:
                    settlement = self.client.settle(task_id, lease_token, result=payload, outputs=outputs, effect=effect)
            else:
                settlement = {"task_id": task_id, "result": payload, "output_objects": outputs, "effect": effect}
            settled = True
            return settlement
        except HostCancelled:
            return {"task_id": task_id, "status": "cancelled", "cancelled": True}
        except Exception as exc:
            if self.client is not None and hasattr(self.client, "fail"):
                self.client.fail(task_id, lease_token, str(exc), retryable=False)
            raise
        finally:
            if not keep_attempt and self.attempt_root is None and settled:
                shutil.rmtree(root, ignore_errors=True)

    def cancel_task(self, task_id: str) -> Any:
        """Propagate cancellation through the runtime client boundary."""
        if self.client is None or not hasattr(self.client, "cancel"):
            raise HostError("runtime client is required to cancel a task")
        return self.client.cancel(task_id)

    def claim_once(self) -> Mapping[str, Any] | None:
        """Claim and execute one queued task through the generated boundary."""
        if self.client is None or not hasattr(self.client, "claim_next"):
            raise HostError(
                "runtime client lacks canonical claim-next operation; "
                "use generated WorkspaceClient.claim_task"
            )
        claim = self.client.claim_next(
            executor_id=self.executor_id,
            capability_ids=sorted(self.capabilities),
            idempotency_key=f"claim:{self.executor_id}:{time.time_ns()}",
        )
        if claim is None:
            return None
        if not isinstance(claim, Mapping) or not claim.get("task_id"):
            raise HostError("generated claim operation returned no task_id")
        task_id = str(claim["task_id"])
        if not hasattr(self.client, "task"):
            raise HostError("runtime client lacks canonical task read operation")
        task = self.client.task(task_id)
        if isinstance(task, Mapping):
            task_data = dict(task.get("task", task))
        else:
            task_data = {
                "id": getattr(task, "task_id", task_id),
                "capability": getattr(task, "capability_id", ""),
                "spec": {},
            }
        task_data.update(
            {
                "id": task_id,
                "attempt_id": claim.get("attempt_id"),
                "fence": claim.get("fence"),
            }
        )
        return self.run_task(
            {"task": task_data},
            lease_token=str(claim.get("lease_id") or ""),
            attempt_id=str(claim["attempt_id"]),
            fence=int(claim["fence"]),
        )

    def run(self, *, once: bool = False, poll_seconds: float = 1.0, max_tasks: int | None = None) -> list[Mapping[str, Any]]:
        """Run the bounded worker claim loop; ``once`` is the test-friendly form."""
        results: list[Mapping[str, Any]] = []
        while max_tasks is None or len(results) < max_tasks:
            result = self.claim_once()
            if result is not None:
                results.append(result)
                if once:
                    break
                continue
            if once:
                break
            time.sleep(max(0.0, float(poll_seconds)))
        return results


def _cli() -> int:
    parser = argparse.ArgumentParser(prog="astrid-generic-host")
    parser.add_argument("command", nargs="?", choices=("run",), help="run the registered worker claim loop")
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
    parser.add_argument("--once", action="store_true", help="claim at most one task and exit")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--max-tasks", type=int)
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
    if args.command == "run":
        if client is None:
            parser.error("run requires --runtime-endpoint and --credential")
        if not args.register:
            host.register()
        print(json.dumps(host.run(once=args.once, poll_seconds=args.poll_seconds, max_tasks=args.max_tasks), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
