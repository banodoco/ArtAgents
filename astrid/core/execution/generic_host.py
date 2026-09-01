"""Process-isolated generic executor host for the local runtime protocol.

This module deliberately contains no runtime/database/storage imports.  It is a
pack-side process: discovery and execution happen here, while admission,
leases, reservations, and settlement remain protocol operations on the daemon.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import os
import shutil
import secrets as secrets_module
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping
from urllib.parse import urlsplit

from astrid.core.env_vars import ASTRID_INTERNAL_INVOCATION, ASTRID_PACKS_PATH
from astrid.core.execution.capability_ledger import load_capability_ledger
from astrid.core.subprocess_env import build_child_subprocess_env
from astrid.core.execution.process_group import (
    _process_snapshot,
    group_exists as _owned_group_exists,
    popen_owned_group,
    release_group as _release_owned_group,
    signal_group as _signal_owned_group,
    terminate_group as _terminate_owned_group,
)
from astrid.core.execution.provider_route_grant import (
    ProviderRouteGrantAuthority,
    ProviderRouteGrantError,
)
from astrid.sdk.workspace_client import WorkspaceClientError, validate_runtime_endpoint

if TYPE_CHECKING:
    from astrid.core.execution.executor.schema import ExecutorDefinition


class HostError(RuntimeError):
    """A controlled host-side error suitable for a worker diagnostic."""


class HostCancelled(HostError):
    """The runtime cancelled the attempt while the subprocess was running."""


@dataclass
class _NetworkBrokerContext:
    """Host-owned strict broker for one admitted network attempt."""

    broker: Any
    policy: dict[str, Any]
    evidence_key: str
    auth_token: str

    def stop(self) -> None:
        stop = getattr(self.broker, "stop", None)
        if callable(stop):
            stop()


@dataclass(frozen=True)
class AdapterSpec:
    family: str
    resource_keys: tuple[str, ...] = ()
    required_binaries: tuple[str, ...] = ()
    required_packages: tuple[str, ...] = ()
    requires_network: bool = False
    requires_remotion: bool = False


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
        base = cls._specs.get(family, AdapterSpec(family))
        return AdapterSpec(
            base.family,
            base.resource_keys,
            base.required_binaries,
            base.required_packages,
            base.requires_network,
            bool(metadata.get("requires_remotion", base.requires_remotion)),
        )

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
            bool(entry.get("requires_remotion", base.requires_remotion)),
        )


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _json_safe(value: Any) -> Any:
    """Convert request values to the small JSON wire format used by workers."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _signal_process_group(process: subprocess.Popen, sig: int) -> None:
    _signal_owned_group(process, sig)
    return


def _process_group_exists(process: subprocess.Popen) -> bool:
    return _owned_group_exists(process)


def _terminate_process_group(process: subprocess.Popen, *, grace_seconds: float = 2.0) -> None:
    """Terminate the complete child session and reap the direct child.

    The leader is allowed to exit cleanly on SIGTERM, so waiting only on
    ``process.wait()`` is insufficient: a SIGTERM-resistant descendant could
    otherwise survive after the leader has gone away.  Observe the process
    group independently, escalate the still-live group to SIGKILL, then reap
    the leader.  Descendants are not our children and therefore cannot be
    ``waitpid``-reaped here; killing the owned session is the relevant
    containment guarantee.
    """
    _terminate_owned_group(process, grace_seconds=grace_seconds)


def _confined_cwd(
    raw_cwd: str | Path | None,
    *,
    attempt: Path,
    source_root: Path | None = None,
    values: Mapping[str, Any] | None = None,
) -> Path:
    """Resolve a command cwd inside the attempt or admitted source tree."""
    value = str(raw_cwd or "")
    for key, replacement in (values or {}).items():
        value = value.replace("{" + str(key) + "}", str(replacement))
    candidate = Path(value) if value else attempt
    if not candidate.is_absolute():
        candidate = attempt / candidate
    resolved = candidate.expanduser().resolve()
    allowed = [attempt.resolve()]
    if source_root is not None:
        allowed.append(source_root.expanduser().resolve())
    if not any(resolved == root or resolved.is_relative_to(root) for root in allowed):
        raise HostError(
            f"command cwd escapes the attempt/source scope: {raw_cwd!r}"
        )
    return resolved


def _preflight_unavailable_reason(record: "CapabilityRecord") -> str:
    """Return a stable, secret-free reason for a failed capability preflight."""
    failures: list[str] = []
    for check_name in sorted(record.preflight):
        check = record.preflight[check_name]
        if not isinstance(check, Mapping) or check.get("ok") is not False:
            continue
        missing = check.get("missing")
        if isinstance(missing, (list, tuple)) and missing:
            values = ",".join(sorted(str(value) for value in missing))
            failures.append(f"{check_name}:missing={values}")
        elif check.get("reason"):
            failures.append(f"{check_name}:reason={check['reason']}")
        else:
            failures.append(f"{check_name}:failed")
    if failures:
        return ";".join(failures)
    return str(record.matrix.get("evidence_reason") or "capability preflight is not ready")


def _required_secret_names(record: "CapabilityRecord") -> tuple[str, ...]:
    """Return the manifest/matrix credential names admitted to one child.

    This is deliberately the one source of truth for both readiness and
    process injection.  In particular, an ambient ``OPENAI_API_KEY`` cannot
    cross the boundary merely because the parent happens to have one.
    """
    matrix_secret_names = tuple(
        str(name) for name in (record.matrix.get("required_env") or ())
        if str(name).upper().endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
    )
    return tuple(dict.fromkeys(
        str(name)
        for name in (
            *matrix_secret_names,
            *(record.definition.isolation.secrets_required or ()),
            *(record.definition.metadata.get("secrets_required") or ()),
        )
        if str(name)
    ))


def _required_env_names(record: "CapabilityRecord") -> tuple[str, ...]:
    """Return all manifest-declared environment inputs (public or secret)."""
    values: list[str] = []
    for raw in (
        record.matrix.get("required_env") or (),
        record.definition.metadata.get("required_env") or (),
        record.definition.metadata.get("env") or (),
        _required_secret_names(record),
    ):
        if isinstance(raw, str):
            raw = (raw,)
        values.extend(str(name) for name in raw if str(name))
    return tuple(dict.fromkeys(values))


def _network_policy(record: "CapabilityRecord") -> dict[str, Any] | None:
    """Read the optional bounded network policy from the manifest/matrix."""
    raw = record.definition.metadata.get("network_policy")
    if raw is None:
        raw = record.matrix.get("network_policy")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise HostError(f"network_policy for {record.id!r} must be an object")
    return {str(key): value for key, value in raw.items()}


def _provider_routes(record: "CapabilityRecord", inputs: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    """Resolve the exact upstream routes admitted for one provider task."""
    policy = _network_policy(record) or {}
    routes = policy.get("allowed_routes", policy.get("allowed_destinations", ()))
    if isinstance(routes, str):
        routes = (routes,)
    dynamic_names = policy.get("dynamic_url_inputs", ())
    if isinstance(dynamic_names, str):
        dynamic_names = (dynamic_names,)
    dynamic_routes: list[str] = []
    for name in dynamic_names or ():
        raw = (inputs or {}).get(str(name))
        if not isinstance(raw, str) or not raw:
            continue
        parsed = urlsplit(raw)
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            dynamic_routes.append(
                f"{parsed.scheme}://{parsed.hostname.lower()}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}"
            )
    return tuple(dict.fromkeys([*(str(route) for route in (routes or ())), *dynamic_routes]))


def _host_managed_broker(policy: Mapping[str, Any] | None) -> bool:
    """Whether a network policy has a broker owned and started by the host."""
    if not isinstance(policy, Mapping):
        return False
    descriptor = policy.get("broker")
    return isinstance(descriptor, Mapping) and bool(
        descriptor.get("host_managed", descriptor.get("managed", True))
    )


def _tcp_broker_supports(policy: Mapping[str, Any] | None) -> bool:
    """The built-in broker is HTTP/TCP only; datagrams are not advertised."""
    if not isinstance(policy, Mapping):
        return False
    protocols = policy.get("allowed_protocols", policy.get("protocols", ()))
    if isinstance(protocols, str):
        protocols = (protocols,)
    return not any(str(protocol).lower() in {"udp", "quic"} for protocol in (protocols or ()))


def _network_sandbox_argv(argv: list[str], attempt: Path, endpoint: str | None) -> list[str]:
    """Put broker children behind the host's OS network boundary on macOS."""
    if not endpoint:
        return argv
    if sys.platform != "darwin":
        raise HostError("host-managed provider broker requires an OS network sandbox")
    sandbox = shutil.which("sandbox-exec")
    if not sandbox:
        raise HostError("host-managed provider broker requires macOS sandbox-exec")
    parsed = urlsplit(endpoint)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port is None:
        raise HostError("host-managed provider broker endpoint must be loopback")
    # sandbox-exec receives the profile as an argument; escape only the paths
    # that are host-selected and never include provider input or credentials.
    def quote(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    profile = (
        '(version 1) (deny default) '
        '(allow process*) (allow file-read*) '
        f'(allow file-write* (subpath "{quote(str(attempt))}")) '
        '(allow file-write* (subpath "/tmp")) '
        f'(allow network-outbound (remote tcp "localhost:{parsed.port}"))'
    )
    return [sandbox, "-p", profile, *argv]


def _native_network_command(record: "CapabilityRecord") -> bool:
    """Whether a network-required manifest escapes Python hook observability."""
    if record.definition.command is None:
        return False
    metadata = record.definition.metadata
    if bool(metadata.get("native")) or str(metadata.get("execution_kind", "")).lower() == "native":
        return True
    first = str(record.definition.command.argv[0] if record.definition.command.argv else "").lower()
    return first not in {"{python_exec}", sys.executable.lower(), "python", "python3"} and not first.endswith("/python") and not first.endswith("/python3")


def _enforceable_network_gateway(policy: Mapping[str, Any] | None) -> bool:
    """Accept native traffic only when a proxy/broker proves enforcement + observation."""
    if not isinstance(policy, Mapping):
        return False
    enforcement = policy.get("enforcement")
    if isinstance(enforcement, Mapping):
        kind = str(enforcement.get("kind", "")).lower()
        if kind in {"proxy", "broker"} and bool(enforcement.get("enforced")) and bool(enforcement.get("observable")):
            return True
    for key in ("proxy", "broker"):
        value = policy.get(key)
        if isinstance(value, Mapping) and bool(value.get("enforced")) and bool(value.get("observable")):
            return True
    return bool(policy.get("proxy_enforced")) and bool(policy.get("proxy_observable")) and bool(policy.get("proxy"))


def _hivemind_source_preflight(record: "CapabilityRecord") -> dict[str, Any] | None:
    """Require Hivemind to come from a clean, revision-pinned checkout.

    Hivemind is an optional external provider pack.  Its public read key must
    not turn an arbitrary dirty install into an advertised capability.  Other
    external packs retain their own manifest/readiness semantics.
    """
    if str(record.definition.metadata.get("source_pack") or "") != "hivemind":
        return None
    raw_root = record.definition.metadata.get("pack_root")
    pack_root = Path(str(raw_root)).expanduser().resolve() if raw_root else None
    if pack_root is None or not pack_root.is_dir():
        return {"ok": False, "reason": "hivemind source root is unavailable"}
    checkout = next((candidate for candidate in (pack_root, *pack_root.parents) if (candidate / ".git").exists()), None)
    if checkout is None:
        return {"ok": False, "reason": "hivemind source is not a Git checkout"}
    try:
        status = subprocess.run(
            ["git", "-C", str(checkout), "status", "--porcelain=v1"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        revision = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return {"ok": False, "reason": "hivemind source pin could not be verified"}
    if status.stdout.strip():
        return {"ok": False, "reason": "hivemind source checkout is dirty"}
    if not revision:
        return {"ok": False, "reason": "hivemind source checkout has no pinned revision"}
    expected_revision = str(record.definition.metadata.get("commit_sha") or "")
    if expected_revision and revision != expected_revision:
        return {"ok": False, "reason": "hivemind source revision does not match pinned commit", "revision": revision, "expected_revision": expected_revision}
    return {"ok": True, "checkout": str(checkout), "revision": revision}


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


def source_checkout_digest(checkout: str | Path) -> str:
    """Return the source identity used by the generic-host boundary.

    The checkout itself can contain build artefacts and unrelated work.  The
    pack corpus is the executable input to this process, so hash that exact
    tree (using the same file hashing rules as capability admission).
    """
    pack_root = Path(checkout).expanduser().resolve() / "astrid" / "packs"
    if any(path.is_symlink() for path in pack_root.rglob("*")):
        raise ValueError("source checkout pack root contains a symlink")
    return _source_digest(pack_root)


def process_birth_identity(pid: int | None = None) -> str:
    """Return the OS birth token used to distinguish a reused PID."""
    info = _process_snapshot().get(int(pid if pid is not None else os.getpid()))
    return str(info.birth) if info is not None else ""


def _admitted_source_roots(root: Path, definition: Any) -> tuple[Path, ...]:
    """Return every executable root admitted for one capability."""
    roots: list[Path] = [root.resolve()]
    pack_root = _pack_root_for_executor(root)
    if pack_root is not None and str(definition.kind) == "external":
        roots.append(pack_root.resolve())
    return tuple(dict.fromkeys(roots))


def _admitted_python_roots(root: Path, definition: Any) -> tuple[Path, ...]:
    """Return explicit import roots for non-builtin source packs.

    A pack is itself the source root: its Python modules sit alongside the
    manifest-owned ``executors``/``orchestrators`` trees.  Passing the pack
    root (rather than an ancestor) keeps imports useful without admitting an
    unrelated checkout or ambient directory.
    """
    pack_root = _pack_root_for_executor(root)
    if pack_root is None or str(getattr(definition, "kind", "")) != "external":
        return ()
    builtin_packs = (Path(__file__).resolve().parents[3] / "astrid" / "packs").resolve()
    if pack_root == builtin_packs or pack_root.is_relative_to(builtin_packs):
        return ()
    return (pack_root.resolve(),)


def _source_digest_for_roots(roots: tuple[Path, ...] | list[Path]) -> str:
    return _canonical_digest([
        {"root": str(root.resolve()), "digest": _source_digest(root.resolve())}
        for root in roots
    ])


def _verify_admitted_source(admission: Mapping[str, Any]) -> None:
    """Revalidate the source fence immediately before command/provider execution."""
    expected = str(admission.get("source_digest") or "")
    if not expected:
        return
    raw_roots = admission.get("source_roots")
    if isinstance(raw_roots, (list, tuple)) and raw_roots:
        roots = tuple(Path(str(value)).expanduser().resolve() for value in raw_roots)
    elif admission.get("source_root"):
        roots = (Path(str(admission["source_root"])).expanduser().resolve(),)
    else:
        return
    if _source_digest_for_roots(roots) != expected:
        raise HostError("admitted capability source digest changed")


def _vcs_revision(root: Path) -> str:
    """Return the checked-out revision for source-epoch invalidation."""
    checkout = next((candidate for candidate in (root, *root.parents) if (candidate / ".git").exists()), None)
    if checkout is None:
        return "unversioned"
    try:
        result = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _dependency_digest(definition: ExecutorDefinition, records: Mapping[str, "CapabilityRecord"]) -> str:
    """Digest graph edges and declared package/runtime dependencies."""
    dependencies = {
        dependency: (records[dependency].capability_digest if dependency in records else "missing")
        for dependency in sorted(definition.graph.depends_on)
    }
    metadata = definition.metadata
    requirements = metadata.get("requirements", definition.isolation.requirements)
    if isinstance(requirements, str):
        requirements = [requirements]
    return _canonical_digest({
        "depends_on": dependencies,
        "requirements": sorted(str(value) for value in (requirements or ())),
        "requirements_source": str(metadata.get("requirements_source", "")),
    })


def _pack_root_for_executor(executor_root: Path) -> Path | None:
    """Find the manifest-owned pack root for a folder executor.

    The generic host discovers folder executors directly rather than importing
    the pack registry.  External pack metadata (especially the import root
    used by ``python -m`` commands) therefore has to be attached here.
    """
    for candidate in (executor_root, *executor_root.parents):
        if (candidate / "pack.yaml").is_file():
            return candidate.resolve()
    return None


def _attach_pack_metadata(definition: "ExecutorDefinition", executor_root: Path) -> "ExecutorDefinition":
    """Attach the source-pack identity used by the normal executor registry."""
    pack_root = _pack_root_for_executor(executor_root)
    if pack_root is None:
        return definition
    metadata = dict(definition.metadata)
    metadata.setdefault("source", "pack")
    # Read the manifest-owned id so the child receives the correct import
    # parent (and never infer identity from an arbitrary directory name).
    pack_id = pack_root.name
    try:
        from astrid.core.pack.loader import _load_manifest_payload

        payload = _load_manifest_payload(pack_root / "pack.yaml")
        if isinstance(payload, Mapping) and payload.get("id"):
            pack_id = str(payload["id"])
    except (ImportError, OSError, TypeError, ValueError):
        pass
    metadata.setdefault("source_pack", pack_id)
    metadata.setdefault("pack_root", str(pack_root))
    return replace(definition, metadata=metadata)


@dataclass(frozen=True)
class CapabilityRecord:
    definition: ExecutorDefinition
    capability_digest: str
    source_digest: str
    source_root: Path
    dependency_digest: str = ""
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
        source_roots = _admitted_source_roots(self.source_root, self.definition)
        return {
            "id": self.id,
            "definition": self.definition.to_dict(),
            "inputs": [port.__dict__ for port in self.definition.inputs],
            "outputs": [output.__dict__ for output in self.definition.outputs],
            "capability_digest": self.capability_digest,
            "source_digest": self.source_digest,
            "source_type": self.definition.metadata.get("source_type", "local"),
            "commit_sha": self.definition.metadata.get("commit_sha", ""),
            "dependency_digest": self.dependency_digest,
            "source_root": str(self.source_root),
            "source_roots": [str(root) for root in source_roots],
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

    Worker credentials are a distinct runtime boundary from the user-facing
    ``AstridClient`` handshake.  The runtime authorizes registration with
    ``worker:register``, claim/attempt operations with ``worker:execute``,
    task reads/writes with the task scopes, and CAS reads/writes with the
    object scopes.  The credential actor is bound to ``executor_id``. This
    adapter therefore never fabricates a user handshake; the runtime's
    worker-token contract is the sole identity check for this process.
    """

    WORKER_SCOPES = (
        "worker:register",
        "worker:execute",
        "tasks:read",
        "tasks:write",
        "objects:read",
        "objects:write",
    )

    def __init__(self, endpoint: str, credential: str, *, timeout: float = 30.0):
        try:
            self.endpoint = validate_runtime_endpoint(endpoint)
        except WorkspaceClientError as exc:
            raise HostError(f"runtime endpoint rejected: {exc}") from exc
        self.credential = credential
        self.timeout = timeout
        try:
            from banodoco_workspace_client import WorkspaceClient
            from banodoco_workspace_client.contract_metadata import SCHEMA_DIGEST
        except ImportError as exc:
            raise HostError(
                "generated banodoco_workspace_client is unavailable; reinstall the Astrid package"
            ) from exc
        self.schema_digest = SCHEMA_DIGEST
        self.generated = WorkspaceClient(self.endpoint, self.credential)
        self._runtime_epoch: int | None = None

    def health(self):
        """Read protocol/schema/runtime epoch through the generated client."""
        value = self.generated.health()
        epoch = value.get("runtime_epoch") if isinstance(value, Mapping) else getattr(value, "runtime_epoch", None)
        if epoch is not None:
            self._runtime_epoch = int(epoch)
        return value

    def _current_runtime_epoch(self) -> int:
        """Read the live bootstrap epoch before every mutating operation."""
        value = self.health()
        epoch = value.get("runtime_epoch") if isinstance(value, Mapping) else getattr(value, "runtime_epoch", None)
        if epoch is None:
            raise HostError("runtime health returned no runtime_epoch")
        return int(epoch)

    def register_executor(self, executor_id: str, *, capabilities: list[Mapping[str, Any]], max_concurrency: int, resource_keys: list[str], source_digest: str | None, dependency_digest: str | None = None, source_epoch: str | None = None, protocol_version: str = "workspace.v1", schema_digest: str | None = None, runtime_epoch: int | None = None):
        payload = {
            "executor_id": executor_id,
            "capabilities": capabilities,
            "max_concurrency": max_concurrency,
            "resource_keys": resource_keys,
            "protocol": protocol_version,
            "source_digest": source_digest,
            "source_epoch": source_epoch,
            "dependency_digest": dependency_digest,
            "schema_digest": schema_digest,
            "runtime_epoch": runtime_epoch,
        }
        return self.generated.register_executor(
            payload,
            idempotency_key=f"executor-{executor_id}-{_canonical_digest(payload)}",
        )

    def register_capability(
        self,
        capability_id: str,
        *,
        digest: str,
        required_resource_keys: list[str] | None = None,
        status: str = "ready",
        estimated_scratch_bytes: int = 0,
        estimated_output_bytes: int = 0,
        unavailable_reason: str | None = None,
    ):
        """Publish one capability through the generated runtime client."""
        registration = {
            "required_resource_keys": list(required_resource_keys or []),
            "status": status,
            "estimated_scratch_bytes": int(estimated_scratch_bytes),
            "estimated_output_bytes": int(estimated_output_bytes),
            "unavailable_reason": unavailable_reason,
        }
        return self.generated.register_capability(
            capability_id,
            digest,
            **registration,
            idempotency_key=(
                f"capability-{capability_id}-{digest}-"
                f"{_canonical_digest(registration)}"
            ),
        )

    def withdraw_capability(self, capability_id: str, *, digest: str, reason: str):
        """Mark a removed capability unavailable in the canonical registry."""
        return self.generated.register_capability(
            capability_id,
            digest,
            required_resource_keys=[],
            status="unavailable",
            unavailable_reason=reason,
            idempotency_key=f"capability-withdraw-{capability_id}-{digest}",
        )

    def heartbeat(self, task_id: str, lease_token: str, *, attempt_id: str | None = None, fence: int | None = None):
        if not attempt_id or fence is None:
            raise HostError("generated heartbeat requires attempt_id and fence")
        return self.generated.heartbeat_attempt(
            attempt_id,
            lease_id=lease_token,
            fence=int(fence),
            idempotency_key=f"heartbeat-{attempt_id}-{fence}",
            runtime_epoch=self._current_runtime_epoch(),
        )

    def claim(self, task_id: str, worker_id: str, lease_token: str):
        raise HostError("per-task claim is not a canonical operation; use claim_task")

    def claim_next(self, *, executor_id: str, capability_ids: list[str], idempotency_key: str):
        return self.generated.claim_task(
            executor_id=executor_id,
            capability_ids=capability_ids,
            idempotency_key=idempotency_key,
            runtime_epoch=self._current_runtime_epoch(),
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
            "runtime_epoch": self._current_runtime_epoch(),
        }
        return self.generated.settle_attempt(
            attempt_id,
            settlement,
            idempotency_key=f"settle-{attempt_id}-{fence}",
        )

    def fail(self, task_id: str, lease_token: str, error: str, *, retryable: bool = False, attempt_id: str | None = None, fence: int | None = None):
        if not attempt_id or fence is None:
            raise HostError("generated failure requires attempt_id and fence")
        payload: Any = {"message": str(error), "retryable": bool(retryable)}
        return self.generated.fail_attempt(
            attempt_id,
            lease_id=lease_token,
            fence=int(fence),
            error=payload,
            runtime_epoch=self._current_runtime_epoch(),
            idempotency_key=f"fail-{attempt_id}-{fence}",
        )

    def cancel(self, task_id: str):
        return self.generated.cancel_task(task_id, idempotency_key=f"cancel-{task_id}")

    def get_object(self, digest: str) -> bytes:
        response = self.generated.get_object(digest)
        return response.data

    def upload_object(self, path: Path, *, project_id: str, media_type: str, filename: str | None = None):
        if not isinstance(project_id, str) or not project_id.strip():
            raise HostError("project-scoped output upload requires project_id")
        with path.open("rb") as stream:
            data = stream.read()
            return self.generated.ingest_project_object(
                project_id,
                data,
                media_type=media_type,
                idempotency_key=(
                    f"output-{hashlib.sha256(project_id.encode()).hexdigest()}-"
                    f"{hashlib.sha256(data).hexdigest()}"
                ),
                filename=filename,
            )


class GenericPackHost:
    """Discover, register, preflight, and execute pack capabilities."""

    def __init__(self, *, pack_roots: list[str | Path], client: RuntimeProtocolClient | Any | None = None, executor_id: str = "astrid-pack-host", max_concurrency: int = 1, attempt_root: str | Path | None = None, capability_matrix: str | Path | None = None, credential_source: Mapping[str, str] | None = None):
        configured_roots = [Path(root).expanduser().resolve() for root in pack_roots]
        # ASTRID_PACKS_PATH is an explicit discovery input, never an implicit
        # directory. Keep it in the same admitted root set so env-only packs
        # receive identical discovery, digest, and child import treatment.
        for raw_root in os.environ.get(ASTRID_PACKS_PATH, "").split(os.pathsep):
            if raw_root:
                configured_roots.append(Path(raw_root).expanduser().resolve())
        self.pack_roots = tuple(dict.fromkeys(configured_roots))
        self.client = client
        self.executor_id = executor_id
        self.max_concurrency = max(1, int(max_concurrency))
        self.attempt_root = Path(attempt_root).expanduser().resolve() if attempt_root else None
        self.capabilities: dict[str, CapabilityRecord] = {}
        self._registered_digests: dict[str, str] = {}
        self._registered_state: dict[str, dict[str, str]] = {}
        self._registered_runtime_state: dict[str, Any] = {}
        self.capability_matrix_path = Path(capability_matrix).expanduser().resolve() if capability_matrix else self._default_matrix_path()
        # Keep the mapping live when the default is os.environ so test/runtime
        # credential rotation is observed without snapshotting secret values.
        self.credential_source = os.environ if credential_source is None else credential_source
        self.ledger = load_capability_ledger(self.capability_matrix_path) if self.capability_matrix_path else {"capabilities": [], "sources": {}}
        self.matrix: dict[str, dict[str, Any]] = self._load_matrix(self.capability_matrix_path)
        self.source_epoch = "uninitialized"
        self.runtime_state: dict[str, Any] = {}
        # Provider route grants are intentionally scoped to this host process;
        # their signing key never crosses into a child or runtime payload.
        self._provider_grants = ProviderRouteGrantAuthority()
        self._pending_provider_grants: dict[str, str] = {}
        self._active_processes: set[subprocess.Popen] = set()
        self._process_lock = threading.RLock()
        self._shutdown = threading.Event()

    def _track_process(self, process: subprocess.Popen) -> None:
        with self._process_lock:
            self._active_processes.add(process)
        # A signal can arrive between Popen and registration in the set.  Do
        # not let that small window leave an owned child running after host
        # shutdown has begun.
        if self._shutdown.is_set():
            _terminate_process_group(process)

    def _untrack_process(self, process: subprocess.Popen) -> None:
        with self._process_lock:
            self._active_processes.discard(process)

    def shutdown(self) -> None:
        """Stop the host and every currently owned capability process."""
        self._shutdown.set()
        with self._process_lock:
            active = tuple(self._active_processes)
        for process in active:
            try:
                _terminate_process_group(process, grace_seconds=1.0)
            except (OSError, subprocess.SubprocessError):
                # The process may have exited between the census and cleanup;
                # the group helper is deliberately best effort at shutdown.
                pass

    def _client_operation(self, name: str):
        if self.client is None:
            raise HostError(f"runtime client is required for {name}")
        operation = getattr(self.client, name, None)
        if not callable(operation):
            label = "claim-next" if name == "claim_next" else name
            raise HostError(f"runtime client lacks canonical {label} operation")
        return operation

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
            payload = load_capability_ledger(path)
        except ValueError as exc:
            raise HostError(str(exc)) from exc
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
        # Folder/schema modules are runtime discovery dependencies.  Keeping
        # them behind the discovery operation prevents their timeline/project
        # compatibility imports from leaking into the host process boundary.
        from astrid.core.execution.executor.folder import (
            discover_folder_executor_roots,
            load_folder_executor,
        )
        from astrid.core.execution.executor.schema import ExecutorValidationError

        records: dict[str, CapabilityRecord] = {}
        for root in self.pack_roots:
            for executor_root in discover_folder_executor_roots(root):
                try:
                    definition = load_folder_executor(executor_root)
                except (ExecutorValidationError, OSError, ValueError):
                    # A broken optional manifest is unavailable, but does not hide
                    # neighboring packs.  The manifest report records the reason.
                    continue
                definition = _attach_pack_metadata(definition, executor_root)
                manifest = next((executor_root / name for name in ("executor.yaml", "executor.yml", "executor.json") if (executor_root / name).is_file()), None)
                matrix_entry = self.matrix.get(definition.id, {})
                source_roots = _admitted_source_roots(executor_root, definition)
                record = CapabilityRecord(definition=definition, capability_digest=_canonical_digest(definition.to_dict()), source_digest=_source_digest_for_roots(source_roots), source_root=executor_root, manifest_path=manifest, matrix=matrix_entry)
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
        # Dependencies are digested after the full corpus is known so a graph
        # or dependency source change invalidates the next registration.
        records = {
            key: CapabilityRecord(**{**record.__dict__, "dependency_digest": _dependency_digest(record.definition, records)})
            for key, record in records.items()
        }
        self.capabilities = records
        root = self.pack_roots[0] if self.pack_roots else Path.cwd()
        self.source_epoch = _canonical_digest({
            "vcs_revision": _vcs_revision(root),
            "source_digest": _canonical_digest({key: record.source_digest for key, record in records.items()}),
            "matrix_digest": _canonical_digest(self.matrix),
        })
        return tuple(records[key] for key in sorted(records))

    def admit(self, capability_kind: str, capability_id: str) -> tuple[Mapping[str, Any], Mapping[str, str]]:
        """Capture the exact definition and source epoch used by a task child."""
        if capability_kind == "executor":
            if not self.capabilities:
                # Admission of an invocation-selected extra pack is scoped to
                # that pack; the global capability matrix is for registration
                # and must not reject an otherwise valid isolated definition.
                matrix = self.matrix
                self.matrix = {}
                try:
                    self.discover()
                finally:
                    self.matrix = matrix
            record = self.capabilities.get(capability_id)
            if record is None:
                raise HostError(f"capability not discovered: {capability_id}")
            return record.definition.to_dict(), {
                "capability_digest": record.capability_digest,
                "source_digest": record.source_digest,
                "dependency_digest": record.dependency_digest,
                "version": record.definition.version,
                "source_root": str(record.source_root),
                "source_roots": [str(root) for root in _admitted_source_roots(record.source_root, record.definition)],
                "python_path_roots": [
                    str(root) for root in _admitted_python_roots(record.source_root, record.definition)
                ],
            }
        if capability_kind == "orchestrator":
            from astrid.core.execution.orchestrator.folder import (
                discover_folder_orchestrator_roots,
                load_folder_orchestrator,
            )

            for root in self.pack_roots:
                for orchestrator_root in discover_folder_orchestrator_roots(root):
                    try:
                        definition = load_folder_orchestrator(orchestrator_root)
                    except (OSError, ValueError):
                        continue
                    if definition.id != capability_id:
                        continue
                    definition = _attach_pack_metadata(definition, orchestrator_root)
                    source_roots = _admitted_source_roots(orchestrator_root, definition)
                    source_digest = _source_digest_for_roots(source_roots)
                    capability_digest = _canonical_digest(definition.to_dict())
                    return definition.to_dict(), {
                        "capability_digest": capability_digest,
                        "source_digest": source_digest,
                        "dependency_digest": _canonical_digest({
                            "child_executors": definition.child_executors,
                            "child_orchestrators": definition.child_orchestrators,
                        }),
                        "version": definition.version,
                        "source_root": str(orchestrator_root),
                        "source_roots": [str(root) for root in source_roots],
                        "python_path_roots": [
                            str(root) for root in _admitted_python_roots(orchestrator_root, definition)
                        ],
                    }
            raise HostError(f"capability not discovered: {capability_id}")
        raise HostError(f"unsupported capability kind {capability_kind!r}")

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
            required_env = _required_env_names(record)
            missing_env = [name for name in required_env if not self.credential_source.get(name)]
            checks["credentials"] = {"ok": not missing_env, "missing": missing_env}
            required_packages = record.matrix.get("required_packages") or record.definition.metadata.get("required_packages", adapter.required_packages)
            missing_packages = [package for package in (required_packages or ()) if importlib.util.find_spec(str(package)) is None]
            checks["packages"] = {"ok": not missing_packages, "missing": missing_packages}
            # Only the final Remotion compositor needs the JavaScript render
            # tree. Other rendering-pack executors are offline Python/FFmpeg
            # work; the matrix must opt into this requirement explicitly.
            if adapter.requires_remotion:
                checkout = next((parent.parent for parent in (record.source_root, *record.source_root.parents) if parent.name == "astrid" and (parent.parent / "remotion").is_dir()), None)
                package_json = checkout / "remotion" / "package.json" if checkout else None
                lock_file = checkout / "remotion" / "package-lock.json" if checkout else None
                node_modules = checkout / "remotion" / "node_modules" if checkout else None
                checks["remotion"] = {"ok": bool(package_json and lock_file and node_modules and node_modules.is_dir()), "package_json": str(package_json) if package_json else None, "lock_file": str(lock_file) if lock_file else None, "dependencies": str(node_modules) if node_modules else None}
            policy = _network_policy(record)
            if adapter.requires_network and not record.definition.isolation.network:
                checks["network"] = {"ok": False, "reason": "adapter_requires_network"}
            elif record.definition.isolation.network and adapter.family == "provider" and policy is None:
                # Provider capabilities must declare their concrete egress
                # contract.  A boolean ``network: true`` is not an admission
                # policy: without destinations/protocols/redirect handling we
                # cannot observe or constrain the child honestly.
                checks["network"] = {"ok": False, "reason": "provider network_policy is missing"}
            elif record.definition.isolation.network and adapter.family == "provider" and not _host_managed_broker(policy):
                # A Python hook is diagnostic, not an authority boundary: a
                # child can recover native socket capabilities. Provider
                # network work is therefore admissible only through the
                # host-owned broker.
                checks["network"] = {"ok": False, "reason": "provider network requires a host-managed broker"}
            elif record.definition.isolation.network and adapter.family == "provider" and not _tcp_broker_supports(policy):
                checks["network"] = {"ok": False, "reason": "host-managed provider broker does not support UDP/QUIC"}
            elif _native_network_command(record) and record.definition.isolation.network and not _enforceable_network_gateway(policy):
                checks["network"] = {"ok": False, "reason": "native network requires an enforceable observable proxy or broker"}
            else:
                checks["network"] = {"ok": True}
            if record.definition.isolation.network and adapter.family == "provider" and _host_managed_broker(policy):
                sandbox_available = sys.platform == "darwin" and shutil.which("sandbox-exec") is not None
                checks["sandbox"] = {
                    "ok": sandbox_available,
                    **({} if sandbox_available else {"reason": "host-managed provider broker requires an OS network sandbox"}),
                }
            pack_source = _hivemind_source_preflight(record)
            if pack_source is not None:
                checks["pack_source"] = pack_source
            ready = all(value is True or (isinstance(value, dict) and value.get("ok") is True) for value in checks.values())
            updated[record.id] = CapabilityRecord(**{**record.__dict__, "preflight": checks, "ready": ready})
        self.capabilities = updated
        return tuple(updated[key] for key in sorted(updated) if capability_id is None or key == capability_id)

    def register(self, *, deliberate: bool = False) -> dict[str, Any]:
        if not self.capabilities:
            self.discover()
        self.preflight()
        state = {
            key: {
                "capability_digest": record.capability_digest,
                "source_digest": record.source_digest,
                "dependency_digest": record.dependency_digest,
            }
            for key, record in self.capabilities.items()
        }
        invalidations: list[str] = []
        removed = sorted(set(self._registered_state) - set(state))
        invalidations.extend(f"capability removed: {key}" for key in removed)
        for key in sorted(set(state) & set(self._registered_state)):
            for digest_name, label in (("capability_digest", "capability"), ("source_digest", "source"), ("dependency_digest", "dependency")):
                if self._registered_state[key].get(digest_name) != state[key][digest_name]:
                    invalidations.append(f"{label} digest changed: {key}")
        runtime_state = self._runtime_compatibility()
        self.runtime_state = runtime_state
        if self._registered_runtime_state:
            if self._registered_runtime_state.get("protocol") != runtime_state.get("protocol"):
                invalidations.append("runtime protocol changed")
            if self._registered_runtime_state.get("schema_digest") != runtime_state.get("schema_digest"):
                invalidations.append("runtime schema digest changed")
            if self._registered_runtime_state.get("runtime_epoch") != runtime_state.get("runtime_epoch"):
                invalidations.append("runtime epoch changed")
            if self._registered_runtime_state.get("source_epoch") != self.source_epoch:
                invalidations.append("source epoch changed")
        if invalidations and not deliberate:
            raise HostError("registration invalidated; " + "; ".join(invalidations) + "; deliberate re-registration required")
        if self.client is None:
            self._registered_digests = {key: record.capability_digest for key, record in self.capabilities.items()}
            self._registered_state = state
            self._registered_runtime_state = {**runtime_state, "source_epoch": self.source_epoch}
            return {"executor_id": self.executor_id, "capabilities": [r.manifest() for r in self.capabilities.values()], "ready": [r.id for r in self.capabilities.values() if r.ready], "withdrawn_capabilities": removed}
        if removed:
            self._withdraw_removed_capabilities(removed)
        # Publish capability admission metadata before advertising the executor.
        # A real runtime must be able to validate a task against the exact
        # definition digest/source-derived readiness before it can claim work.
        register_capability = getattr(self.client, "register_capability", None)
        if not callable(register_capability):
            raise HostError("runtime client lacks canonical capability registration operation")
        executor_capabilities: list[dict[str, Any]] = []
        for record in self.capabilities.values():
            disposition = str(record.matrix.get("disposition", ""))
            if disposition in {"unsupported", "retired"}:
                # A declared disposition is authoritative even when the
                # source happens to fail another preflight check; preserve its
                # human-readable reason rather than an incidental local error.
                status = disposition
                unavailable_reason = str(record.matrix.get("evidence_reason") or disposition)
            else:
                status = "ready" if record.ready else "unavailable"
                unavailable_reason = None if record.ready else _preflight_unavailable_reason(record)
            register_capability(
                record.id,
                digest=record.capability_digest,
                required_resource_keys=list(record.resource_keys),
                status=status,
                estimated_scratch_bytes=record.estimated_scratch_bytes,
                estimated_output_bytes=record.estimated_output_bytes,
                unavailable_reason=unavailable_reason,
            )
            executor_capabilities.append(
                {
                    "capability_id": record.id,
                    "definition_digest": record.capability_digest,
                    "status": status,
                    "required_resource_keys": list(record.resource_keys),
                    "estimated_scratch_bytes": record.estimated_scratch_bytes,
                    "estimated_output_bytes": record.estimated_output_bytes,
                    "unavailable_reason": unavailable_reason,
                }
            )
        all_keys = sorted({key for record in self.capabilities.values() for key in record.resource_keys})
        dependency_digests = {key: record.dependency_digest for key, record in self.capabilities.items()}
        registration_kwargs = {
            "capabilities": sorted(
                executor_capabilities,
                key=lambda item: str(item["capability_id"]),
            ),
            "max_concurrency": self.max_concurrency,
            "resource_keys": all_keys,
            "source_digest": _canonical_digest({key: record.source_digest for key, record in self.capabilities.items()}),
            "dependency_digest": _canonical_digest(dependency_digests),
            "source_epoch": self.source_epoch,
            "protocol_version": runtime_state.get("protocol", "workspace.v1"),
            "schema_digest": runtime_state.get("schema_digest"),
            "runtime_epoch": runtime_state.get("runtime_epoch"),
        }
        registration = self.client.register_executor(self.executor_id, **registration_kwargs)
        self._registered_digests = {key: record.capability_digest for key, record in self.capabilities.items()}
        self._registered_state = state
        self._registered_runtime_state = {**runtime_state, "source_epoch": self.source_epoch}
        return {"registration": registration, "capabilities": [r.manifest() for r in self.capabilities.values()], "withdrawn_capabilities": removed}

    def _withdraw_removed_capabilities(self, capability_ids: list[str]) -> None:
        """Make removed capabilities unavailable before publishing new state."""
        for capability_id in capability_ids:
            prior = self._registered_state[capability_id]
            reason = "capability removed from source checkout"
            withdraw = getattr(self.client, "withdraw_capability", None)
            if not callable(withdraw):
                raise HostError(f"runtime cannot withdraw removed capability: {capability_id}")
            withdraw(
                capability_id,
                digest=prior.get("capability_digest", ""),
                reason=reason,
            )

    def refresh(self) -> tuple[CapabilityRecord, ...]:
        """Re-scan source and report digest changes; callers must register again."""
        old = self.capabilities
        self.discover()
        removed = set(old) - set(self.capabilities)
        changed = sorted(removed)
        for key, record in self.capabilities.items():
            if key in old and (
                old[key].capability_digest != record.capability_digest
                or old[key].source_digest != record.source_digest
                or old[key].dependency_digest != record.dependency_digest
            ):
                changed.append(key)
        return tuple(old[key] if key in removed else self.capabilities[key] for key in changed)

    def _runtime_compatibility(self) -> dict[str, Any]:
        """Read and validate the exact runtime protocol/schema/epoch."""
        from banodoco_workspace_client.contract_metadata import PROTOCOL

        expected_protocol = PROTOCOL
        if self.client is None:
            return {
                "protocol": expected_protocol,
                "schema_digest": None,
                "runtime_epoch": None,
            }
        expected_schema = getattr(self.client, "schema_digest", None)
        if not isinstance(expected_schema, str) or not expected_schema:
            raise HostError("runtime client lacks generated schema digest metadata")
        health_operation = getattr(self.client, "health", None)
        if not callable(health_operation):
            raise HostError("runtime client lacks canonical health operation")
        health: Any = health_operation()
        if health is None:
            raise HostError("runtime health returned no protocol document")
        value = dict(health) if isinstance(health, Mapping) else {
            "protocol": getattr(health, "protocol", None),
            "schema_digest": getattr(health, "schema_digest", None),
            "runtime_epoch": getattr(health, "runtime_epoch", None),
        }
        actual_protocol = str(value.get("protocol", ""))
        actual_schema = str(value.get("schema_digest", ""))
        mismatches = []
        if actual_protocol != expected_protocol:
            mismatches.append(f"protocol expected={expected_protocol} actual={actual_protocol or 'missing'}")
        if expected_schema and actual_schema != expected_schema:
            mismatches.append(f"schema_digest expected={expected_schema} actual={actual_schema or 'missing'}")
        runtime_epoch = value.get("runtime_epoch")
        if isinstance(runtime_epoch, bool) or not isinstance(runtime_epoch, int) or runtime_epoch < 1:
            mismatches.append("runtime_epoch must be a positive integer")
        if mismatches:
            raise HostError("runtime compatibility blocked: " + "; ".join(mismatches))
        return {
            "protocol": actual_protocol,
            "schema_digest": actual_schema,
            "runtime_epoch": runtime_epoch,
            "runtime_instance_id": value.get("runtime_instance_id") or value.get("instance_id"),
            "coordinator_epoch": value.get("coordinator_epoch"),
        }

    def _materialize_inputs(
        self,
        spec: Mapping[str, Any],
        attempt: Path,
        *,
        authorized_input_object_ids: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Materialize digest inputs and managed registry objects in *attempt*.

        Runtime object ids/digests are the only authority for live media.  A
        registry supplied as an input is read only to discover those identities;
        every object is fetched through the runtime, hash-checked, and copied
        below ``attempt/managed-objects``.  Renderers receive a derived private
        registry whose ``file`` values point at those attempt-local copies.
        """
        # Runtime admission wraps the immutable capability input document in
        # the task envelope alongside input_object_ids/schema metadata. The
        # nested document is the one canonical managed-input shape shared by
        # task admission and this host.
        raw_authorized = authorized_input_object_ids
        if raw_authorized is None:
            raw_authorized = spec.get("input_object_ids", ())
        if not isinstance(raw_authorized, (list, tuple)):
            raise HostError("runtime task input_object_ids must be a list")
        authorized_digests: set[str] = set()
        for object_id in raw_authorized:
            if not isinstance(object_id, str):
                raise HostError("runtime task input_object_ids must contain strings")
            normalized = object_id.removeprefix("sha256:")
            if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
                raise HostError("runtime task input_object_ids must contain sha256 object IDs")
            if normalized in authorized_digests:
                raise HostError("runtime task input_object_ids must be unique")
            authorized_digests.add(normalized)

        def require_authorized(digest: str, name: str) -> str:
            normalized = str(digest).removeprefix("sha256:")
            if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
                raise HostError(f"invalid managed digest for {name}")
            if normalized not in authorized_digests:
                raise HostError(f"managed input {name!r} is not authorized by task input_object_ids")
            return normalized

        admitted = spec.get("spec")
        if not isinstance(admitted, Mapping):
            raise HostError("runtime task is missing its immutable spec envelope")
        input_spec = admitted
        values = dict(input_spec.get("inputs", {})) if isinstance(input_spec.get("inputs", {}), Mapping) else {}
        # Timeline visualization tasks carry their canonical registry inside
        # the immutable snapshot rather than as a separate input file. Expose
        # it to the same host-only materialization path used by render tasks.
        snapshot = input_spec.get("timeline_snapshot")
        if not isinstance(snapshot, Mapping):
            # Managed render admission carries the frozen snapshot inside the
            # immutable inputs document.  Materialize it here, under this
            # attempt, rather than allowing SDK code to write a project-side
            # snapshot.
            candidate = values.get("timeline_snapshot")
            snapshot = candidate if isinstance(candidate, Mapping) else None
        # The snapshot is an admission envelope, not a renderer input port.
        # Once its derived files are created, do not forward the authoring
        # document as an undeclared child argument.
        values.pop("timeline_snapshot", None)
        snapshot_registry = snapshot.get("registry") if isinstance(snapshot, Mapping) else None
        snapshot_config = snapshot.get("config") if isinstance(snapshot, Mapping) else None
        if isinstance(snapshot_config, Mapping) and "timeline" not in values:
            snapshot_timeline_path = Path(attempt).resolve() / "inputs" / "timeline.json"
            snapshot_timeline_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_timeline_path.write_text(
                json.dumps(snapshot_config, sort_keys=True), encoding="utf-8"
            )
            values["timeline"] = str(snapshot_timeline_path)
        if "assets_registry" not in values and isinstance(snapshot_registry, Mapping):
            snapshot_registry_path = Path(attempt).resolve() / "inputs" / "snapshot-assets.json"
            snapshot_registry_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_registry_path.write_text(json.dumps(snapshot_registry, sort_keys=True), encoding="utf-8")
            values["assets_registry"] = str(snapshot_registry_path)
        if "materialized_root" in values or "materialized_objects" in values:
            raise HostError("materialized media handoff is host-owned and cannot be caller supplied")
        input_digests = input_spec.get("input_digests", ())
        for item in input_digests if isinstance(input_digests, list) else ():
            if isinstance(item, Mapping) and item.get("name") and item.get("digest"):
                values.setdefault(str(item["name"]), {"digest": str(item["digest"])})
        for name in values:
            input_name = Path(str(name))
            if not str(name) or input_name.is_absolute() or ".." in input_name.parts:
                raise HostError(f"input name escapes the attempt directory: {name!r}")
        attempt = Path(attempt).resolve()
        managed_root = attempt / "managed-objects"
        managed_root.mkdir(parents=True, exist_ok=True)
        materialized_objects: dict[str, str] = {}
        fetched_objects: dict[tuple[str, str], Path] = {}

        def fetch_object(reference: str, digest: str, name: str, *, filename: str | None = None) -> Path:
            if self.client is None:
                raise HostError(f"runtime client is required to materialize managed input {name}")
            normalized = require_authorized(digest, name)
            cache_key = (str(reference), normalized)
            cached = fetched_objects.get(cache_key)
            if cached is not None:
                return cached
            data = self._client_operation("get_object")(normalized)
            if not isinstance(data, (bytes, bytearray)):
                data = getattr(data, "data", None)
            if not isinstance(data, (bytes, bytearray)):
                raise HostError(f"runtime object fetch returned no bytes for {name}")
            payload = bytes(data)
            if hashlib.sha256(payload).hexdigest() != normalized:
                raise HostError(f"input object hash mismatch for {name}")
            destination = managed_root / (
                filename
                if filename is not None
                else f"{len(list(managed_root.iterdir())):04d}-{hashlib.sha256(reference.encode()).hexdigest()[:16]}"
            )
            destination.write_bytes(payload)
            fetched_objects[cache_key] = destination
            return destination

        registry_input_names = {
            "assets_registry",
            "assets_registry_path",
            "assets",
            "hype_assets",
        }
        for name, value in list(values.items()):
            digest = value.get("digest") if isinstance(value, Mapping) else (value if isinstance(value, str) and len(value) == 64 else None)
            if digest:
                if self.client is None or not callable(getattr(self.client, "get_object", None)):
                    raise HostError(
                        f"runtime client is required to materialize digest input {name}"
                    )
                normalized = require_authorized(str(digest), str(name))
                if str(name) == "theme":
                    destination = fetch_object(
                        str(value.get("object_id") or "theme"),
                        str(digest),
                        "theme",
                        filename="theme.json",
                    )
                    values[name] = str(destination)
                    materialized_objects["theme"] = str(destination)
                    materialized_objects[str(digest).removeprefix("sha256:")] = str(destination)
                    continue
                input_name = Path("theme.json") if str(name) == "theme" else Path(str(name))
                input_root = (attempt / "inputs").resolve()
                path = (input_root / input_name).resolve()
                if not path.is_relative_to(input_root):
                    raise HostError(f"input name escapes the attempt directory: {name!r}")
                data = self.client.get_object(normalized)
                if not isinstance(data, (bytes, bytearray)):
                    data = getattr(data, "data", None)
                if not isinstance(data, (bytes, bytearray)) or hashlib.sha256(bytes(data)).hexdigest() != normalized:
                    raise HostError(f"input object hash mismatch for {name}")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(bytes(data))
                values[name] = str(path)

            if name not in registry_input_names:
                continue
            registry_path = Path(str(values[name])).expanduser()
            if not registry_path.is_absolute():
                registry_path = (attempt / registry_path).resolve()
            try:
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise HostError(f"managed asset registry cannot be read for {name}: {exc}") from exc
            if not isinstance(registry, Mapping) or not isinstance(registry.get("assets"), Mapping):
                raise HostError(f"managed asset registry for {name} is invalid")
            derived = dict(registry)
            derived_assets: dict[str, Any] = {}
            for key, raw in registry["assets"].items():
                if not isinstance(raw, Mapping):
                    raise HostError(f"managed asset {key!r} is invalid")
                forbidden = {"url", "uri", "path", "source_path", "locator", "realm", "file"}
                if forbidden.intersection(raw):
                    raise HostError(f"managed asset {key!r} contains an unmanaged locator")
                object_id = raw.get("object_id") or raw.get("media_id")
                raw_digest = raw.get("digest") or raw.get("content_sha256") or raw.get("sha256") or raw.get("hash")
                if not isinstance(object_id, str) or not object_id.strip() or not isinstance(raw_digest, str):
                    raise HostError(f"managed asset {key!r} requires object_id and digest")
                digest_hex = raw_digest.removeprefix("sha256:")
                destination = fetch_object(object_id, digest_hex, str(key))
                materialized_objects[object_id] = str(destination)
                materialized_objects[digest_hex] = str(destination)
                entry = dict(raw)
                entry["file"] = str(destination)
                derived_assets[str(key)] = entry
            derived["assets"] = derived_assets
            derived_path = attempt / "inputs" / f"{Path(str(name)).name}.materialized.json"
            derived_path.parent.mkdir(parents=True, exist_ok=True)
            derived_path.write_text(json.dumps(derived, sort_keys=True), encoding="utf-8")
            values[name] = str(derived_path)
        if materialized_objects:
            values["materialized_root"] = str(managed_root)
            values["materialized_objects"] = materialized_objects
        return values

    def _start_network_broker(
        self,
        record: CapabilityRecord,
        attempt: Path,
        admission: Mapping[str, Any],
        inputs: Mapping[str, Any] | None = None,
    ) -> _NetworkBrokerContext | None:
        """Start a strict host-owned broker when the manifest requests one.

        A broker descriptor is deliberately declarative: the child never gets
        to choose its endpoint or admission.  The host creates the loopback
        listener, binds the exact admission/route set, and supplies its
        endpoint only through the child environment.
        """
        policy = _network_policy(record)
        descriptor = policy.get("broker") if isinstance(policy, Mapping) else None
        if not isinstance(descriptor, Mapping):
            return None
        if not bool(descriptor.get("host_managed", descriptor.get("managed", True))):
            return None
        from astrid.core.execution.network_broker import ObservableNetworkBroker

        evidence_key = secrets_module.token_hex(32)
        auth_token = secrets_module.token_urlsafe(32)
        evidence_path = attempt / "broker-evidence.json"
        routes = _provider_routes(record, inputs)
        # Bind the concrete dynamic destinations into the signed admission so
        # route evidence cannot be replayed under a different URL input.
        admission["allowed_routes"] = list(routes)
        broker = ObservableNetworkBroker(response_body=None)
        broker.register_admission(
            admission,
            allowed_routes=[str(route) for route in (routes or ())],
            evidence_path=evidence_path,
            evidence_key=evidence_key,
            auth_token=auth_token,
        ).start()
        effective = dict(policy)
        # The loopback endpoint is the only network destination the child
        # needs to reach; the broker itself enforces the upstream route set.
        effective["proxy"] = broker.endpoint
        # The child is allowed to connect only to the host-owned loopback
        # broker.  The upstream route set belongs to the broker, not to the
        # provider process: retaining it here would let a Python provider
        # connect directly to an allowlisted upstream and still pass the
        # application socket hook.  The broker separately enforces
        # ``routes`` and signs the observed route evidence.
        effective["allowed_destinations"] = [broker.endpoint]
        effective["broker"] = {**dict(descriptor), "evidence_path": str(evidence_path)}
        return _NetworkBrokerContext(broker=broker, policy=effective, evidence_key=evidence_key, auth_token=auth_token)

    def request_provider_route_grant(
        self,
        task: Mapping[str, Any],
        *,
        ttl_seconds: int = 60,
    ) -> str:
        """Request one short-lived, task-bound provider egress grant.

        This is the explicit actor-facing step.  ``run_task`` consumes the
        returned opaque handle exactly once immediately before broker launch.
        """
        task_data = task.get("task", task)
        task_id = str(task_data.get("id") or task_data.get("task_id") or "")
        capability_id = str(task_data.get("capability") or task_data.get("capability_id") or "")
        if not task_id or not capability_id:
            raise ProviderRouteGrantError("provider route grant requires task and capability identity")
        record = self.capabilities.get(capability_id)
        if record is None:
            self.discover()
            record = self.capabilities.get(capability_id)
        if record is None:
            raise ProviderRouteGrantError(f"capability not discovered: {capability_id}")
        self.preflight(capability_id)
        record = self.capabilities[capability_id]
        policy = _network_policy(record)
        if not record.ready or record.adapter.family != "provider" or not record.definition.isolation.network:
            raise ProviderRouteGrantError("provider route grant requires a ready network provider")
        if not _host_managed_broker(policy) or not _tcp_broker_supports(policy):
            raise ProviderRouteGrantError("provider route grant requires a supported host-managed TCP broker")
        spec = task_data.get("spec") if isinstance(task_data.get("spec"), Mapping) else {}
        inputs = spec.get("inputs") if isinstance(spec.get("inputs"), Mapping) else {}
        routes = _provider_routes(record, inputs)
        descriptor = (policy or {}).get("broker", {})
        binding = ProviderRouteGrantAuthority.binding(
            capability_id=record.id,
            capability_digest=record.capability_digest,
            broker=descriptor,
        )
        token = self._provider_grants.issue(
            task_id=task_id,
            capability_id=record.id,
            capability_digest=record.capability_digest,
            routes=routes,
            broker_binding=binding,
            ttl_seconds=ttl_seconds,
        )
        self._pending_provider_grants[task_id] = token
        return token

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

    def _child_environment(
        self,
        record: CapabilityRecord,
        attempt: Path,
        *,
        explicit_env: Mapping[str, str] | None = None,
        admission: Mapping[str, Any] | None = None,
        network_broker: _NetworkBrokerContext | None = None,
        network_policy: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Build a redacted, manifest-scoped child environment.

        The second return value is the temporary secret map held by the host;
        callers clear it in their ``finally`` block.  No credential is placed
        in request JSON, evidence, or diagnostics.
        """
        declared = _required_secret_names(record)
        all_declared = _required_env_names(record)
        secrets = {name: str(self.credential_source[name]) for name in declared if self.credential_source.get(name)}
        explicit = dict(explicit_env or {})
        explicit.update({name: str(self.credential_source[name]) for name in all_declared if name not in declared and self.credential_source.get(name)})
        # A manifest may set ordinary fixed environment values, but secret
        # values are always sourced by the host and never trusted from YAML.
        for name in tuple(explicit):
            if name in declared:
                explicit.pop(name, None)
            elif name.upper().endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD")):
                raise HostError(f"undeclared secret environment variable {name!r}")
        env = build_child_subprocess_env(
            explicit_env=explicit,
            passthrough=record.definition.isolation.env_passthrough,
            declared_passthrough=record.definition.isolation.env_passthrough,
            secret_values=secrets,
            declared_secrets=declared,
        )
        policy = network_broker.policy if network_broker is not None else (dict(network_policy) if network_policy is not None else _network_policy(record))
        if policy is not None:
            hook_root = attempt / ".astrid-network-hook"
            hook_root.mkdir(parents=True, exist_ok=True)
            (hook_root / "sitecustomize.py").write_text(
                "from astrid.core.execution.network_policy import install_from_environment\ninstall_from_environment()\n",
                encoding="utf-8",
            )
            evidence_path = attempt / "network-evidence.json"
            env["ASTRID_NETWORK_POLICY"] = json.dumps(policy, sort_keys=True, separators=(",", ":"))
            env["ASTRID_NETWORK_EVIDENCE"] = str(evidence_path)
            # Only the broker authentication token crosses the process
            # boundary.  The host/broker evidence signing key never does.
            if network_broker is not None:
                env["ASTRID_NETWORK_BROKER_TOKEN"] = network_broker.auth_token
            env["ASTRID_NETWORK_ADMISSION"] = json.dumps(dict(admission or {}), sort_keys=True, separators=(",", ":"))
            env["PYTHONPATH"] = str(hook_root) + os.pathsep + env.get("PYTHONPATH", "")
            proxy = policy.get("proxy")
            if isinstance(proxy, str) and proxy:
                parsed_proxy = urlsplit(proxy)
                if parsed_proxy.username or parsed_proxy.password:
                    raise HostError("network policy proxy URL must not contain credentials")
                # Ambient proxy settings are not inherited; only an admitted
                # manifest proxy may be used by the child.
                for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                    env[key] = proxy
                no_proxy = policy.get("no_proxy")
                if no_proxy:
                    env["NO_PROXY"] = str(no_proxy)
                # Native provider wrappers consume an explicit, host-issued
                # name rather than trusting ambient proxy variables.
                env["ASTRID_BROKER_PROXY"] = proxy
            broker = policy.get("broker")
            if isinstance(broker, Mapping) and broker.get("evidence_path"):
                env["ASTRID_NETWORK_BROKER_EVIDENCE"] = str(broker["evidence_path"])
        return env, secrets

    @staticmethod
    def _scrub_secret_text(value: str, secrets: Mapping[str, str]) -> str:
        result = str(value)
        for secret in secrets.values():
            if secret:
                result = result.replace(secret, "<redacted>")
        return result

    @staticmethod
    def _network_evidence(attempt: Path, *, evidence_key: str | None = None, admission: Mapping[str, Any] | None = None, required: bool = False, broker_required: bool = False, broker_context: _NetworkBrokerContext | None = None) -> Mapping[str, Any] | None:
        del evidence_key  # Child evidence keys were retired; only host keys are trusted.
        if not broker_required:
            if required:
                raise HostError("network-required task has no host broker context")
            return None
        if broker_context is None:
            raise HostError("network-required task has no host broker context")
        if broker_required:
            # Re-materialize from broker-owned memory after child exit.  This
            # closes the path-overwrite attack: the child knows the path but
            # never knows the signing secret.
            finalize = getattr(broker_context.broker, "finalize_evidence", None)
            if callable(finalize):
                finalize()
            broker_path = getattr(broker_context.broker, "evidence_path", None)
            try:
                broker = json.loads(Path(broker_path).read_text(encoding="utf-8")) if broker_path else None
            except (OSError, ValueError):
                broker = None
            if not isinstance(broker, Mapping):
                raise HostError("network-required task produced no signed broker route evidence")
            broker_unsigned = {key: item for key, item in broker.items() if key not in {"signature", "signature_algorithm"}}
            broker_canonical = json.dumps(broker_unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
            broker_signature = hmac.new(broker_context.evidence_key.encode(), broker_canonical, hashlib.sha256).hexdigest()
            if broker.get("signature_algorithm") != "hmac-sha256" or not hmac.compare_digest(str(broker.get("signature", "")), broker_signature):
                raise HostError("network-required task broker evidence signature is invalid")
            if dict(broker.get("admission") or {}) != dict(admission or {}):
                raise HostError("network-required task broker evidence admission binding is invalid")
            broker_events = broker.get("events")
            if not isinstance(broker_events, list):
                raise HostError("network-required task produced no signed broker route evidence")
            observed = {
                str(event.get("kind"))
                for event in broker_events
                if isinstance(event, Mapping) and str(event.get("detail", "")).endswith("|allowed=true")
            }
            required_events = {"handshake"}
            if broker_context.broker.allowed_routes:
                required_events.add("route")
            if not required_events.issubset(observed):
                raise HostError("network-required task produced incomplete broker route evidence")
            for event in broker_events:
                if not isinstance(event, Mapping) or event.get("kind") != "route" or not str(event.get("detail", "")).endswith("|allowed=true"):
                    continue
                target = str(event.get("detail", "")).rsplit("|allowed=", 1)[0]
                if not any(broker_context.broker._route_allowed(target) for _ in (0,)):
                    raise HostError("network-required task broker evidence contains an unregistered route")
            # Materialize a host-signed envelope from broker-owned events. The
            # child evidence path is deliberately ignored, so a child cannot
            # forge either the signature or the observations in settlement.
            value = {
                "schema_version": 1,
                "admission": dict(broker.get("admission") or {}),
                "events": [
                    {
                        "kind": "broker_handshake" if event.get("kind") == "handshake" else "broker_route",
                        "detail": event.get("detail", ""),
                        "allowed": str(event.get("detail", "")).endswith("|allowed=true"),
                    }
                    for event in broker_events
                    if isinstance(event, Mapping)
                ],
                "broker_evidence": broker,
            }
            unsigned = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
            value["signature_algorithm"] = "hmac-sha256"
            value["signature"] = hmac.new(broker_context.evidence_key.encode(), unsigned, hashlib.sha256).hexdigest()
            (attempt / "network-evidence.json").write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
            return value

    def _upload_outputs(self, outputs: list[dict[str, Any]], *, project_id: str) -> list[dict[str, Any]]:
        """Publish staged outputs and return settlement-safe object refs."""
        upload_object = getattr(self.client, "upload_object", None)
        if not callable(upload_object):
            raise HostError(
                "runtime client must provide canonical upload_object for output publication"
            )
        uploaded: list[dict[str, Any]] = []
        for descriptor in outputs:
            descriptor = dict(descriptor)
            raw_path = descriptor.pop("path", None)
            if not raw_path:
                raise HostError("generated output is missing its staged path")
            path = Path(str(raw_path))
            media_type = str(descriptor.get("artifact_type") or "application/octet-stream")
            object_row = upload_object(
                path,
                project_id=project_id,
                media_type=media_type,
                filename=path.name,
            )
            digest = getattr(object_row, "digest", None)
            if not digest:
                raise HostError("generated object upload returned no canonical digest")
            uploaded.append({
                "name": descriptor.get("name"),
                "kind": "object",
                "media_type": media_type,
                "digest": digest,
                "size": int(getattr(object_row, "size", descriptor.get("size", 0))),
            })
        return uploaded

    def _run_command_definition(self, record: CapabilityRecord, inputs: Mapping[str, Any], output_root: Path, attempt: Path, *, cancelled=None, admission: Mapping[str, Any] | None = None, network_broker: _NetworkBrokerContext | None = None) -> Any:
        """Run a manifest command without importing Astrid's project authority.

        Built-in pipeline steps and command capabilities are both runnable from
        an attempt directory alone.
        """
        command = record.definition.command
        if command is None:
            raise HostError(f"capability {record.id!r} has no dispatchable command")
        if admission is not None:
            _verify_admitted_source(admission)
        values = {"out": str(output_root), "run_root": str(attempt), "python_exec": sys.executable, **inputs}
        for port in record.definition.inputs:
            if port.name not in values and port.default is not None:
                values[port.name] = port.default
        for output in record.definition.outputs:
            if output.name == "video" and "output_name" not in values:
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
                    port = next((candidate for candidate in record.definition.inputs if candidate.name == input_arg.input), None)
                    if port is not None and str(port.type).lower() in {"boolean", "bool"}:
                        # Store-true CLI options are presence flags, not
                        # ``--flag True`` value options.  A false admitted
                        # value is intentionally omitted.
                        if bool(item):
                            argv.append(input_arg.flag)
                    else:
                        argv.extend((input_arg.flag, str(item)))
        # Start from the canonical child environment: only safe process
        # variables and manifest-declared provider configuration cross the
        # boundary.  In particular, an unrelated ambient API key must never
        # leak into a provider subprocess.
        package_parent = str(Path(__file__).resolve().parents[3])
        env, secrets = self._child_environment(
            record,
            attempt,
            admission=admission,
            network_broker=network_broker,
            explicit_env={
                "PYTHONPATH": package_parent,
                ASTRID_INTERNAL_INVOCATION: "1",
                **{str(key): str(value) for key, value in command.env.items()},
            },
        )
        # Pack runtime modules reserve their direct module entry points for
        # the canonical runner.  GenericPackHost is that runner's process
        # boundary, so mark the child invocation just as executor_runner does.
        # An external pack's ``python -m`` command executes directly in this
        # host path (command manifests do not go through the registry runner).
        # Carry the pinned pack parent explicitly so the child can import the
        # admitted module without falling back to ambient site-packages.
        source_pack = str(record.definition.metadata.get("source_pack") or "")
        pack_root_raw = record.definition.metadata.get("pack_root")
        if source_pack and isinstance(pack_root_raw, str) and pack_root_raw:
            pack_root = Path(pack_root_raw).expanduser().resolve()
            builtin_root = (Path(__file__).resolve().parents[3] / "astrid" / "packs" / source_pack).resolve()
            if pack_root != builtin_root:
                pack_parent = str(pack_root.parent)
                existing_pythonpath = env.get("PYTHONPATH")
                env["PYTHONPATH"] = (
                    pack_parent
                    if not existing_pythonpath
                    else os.pathsep.join((pack_parent, existing_pythonpath))
                )
        cwd = _confined_cwd(
            command.cwd,
            attempt=attempt,
            source_root=record.source_root,
            values=values,
        )
        broker_endpoint = network_broker.policy.get("proxy") if network_broker is not None else None
        process = popen_owned_group(
            _network_sandbox_argv(argv, attempt, broker_endpoint),
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._track_process(process)
        try:
            while process.poll() is None:
                if cancelled is not None and cancelled():
                    _terminate_process_group(process)
                    raise HostCancelled(f"capability {record.id!r} cancelled")
                time.sleep(0.05)
            stdout, stderr = process.communicate()
            if cancelled is not None and cancelled():
                raise HostCancelled(f"capability {record.id!r} cancelled")
            if process.returncode != 0:
                detail = self._scrub_secret_text((stderr or stdout).strip(), secrets)
                raise HostError(f"capability {record.id!r} exited {process.returncode}: {detail}")
            outputs = {}
            for output in record.definition.outputs:
                template = output.path_template or output.placeholder
                if template:
                    path = str(template)
                    for key, value in values.items():
                        path = path.replace("{" + key + "}", str(value))
                else:
                    path = str(output_root / output.name)
                candidate = Path(path)
                if candidate.is_file():
                    outputs[output.name] = str(candidate)
            return type("CommandResult", (), {"outputs": outputs, "payload": {"returncode": process.returncode, "capability_digest": record.capability_digest, "process_id": process.pid}})()
        finally:
            self._untrack_process(process)
            _release_owned_group(process)
            env.clear()
            secrets.clear()

    def invoke_capability(
        self,
        *,
        capability_kind: str,
        capability_id: str,
        request: Mapping[str, Any],
        attempt: str | Path,
        cancelled=None,
        definition: Mapping[str, Any] | None = None,
        admission: Mapping[str, Any] | None = None,
        child_env: Mapping[str, str] | None = None,
    ) -> Any:
        """Run one pack capability in a dedicated child process.

        The host is deliberately the only process that launches pack runtime
        code.  In particular, callers must not import an executor/orchestrator
        runner and then rely on ambient process state: that leaves mutable
        Python state, monkeypatches, and ledger authority in the caller.  The
        child receives a JSON request, marks itself as an internal invocation,
        and writes a small process-like result beside the request.
        """
        if capability_kind not in {"executor", "orchestrator"}:
            raise HostError(f"unsupported capability kind {capability_kind!r}")
        attempt_path = Path(attempt).expanduser().resolve()
        attempt_path.mkdir(parents=True, exist_ok=True)
        if definition is not None:
            command_data: Mapping[str, Any] | None = None
            if capability_kind == "executor":
                candidate = definition.get("command")
                command_data = candidate if isinstance(candidate, Mapping) else None
            else:
                runtime_data = definition.get("runtime")
                if isinstance(runtime_data, Mapping):
                    candidate = runtime_data.get("command")
                    command_data = candidate if isinstance(candidate, Mapping) else None
            if command_data is not None and command_data.get("cwd"):
                source_root = None
                if isinstance(admission, Mapping) and admission.get("source_root"):
                    source_root = Path(str(admission["source_root"]))
                _confined_cwd(
                    str(command_data["cwd"]),
                    attempt=attempt_path,
                    source_root=source_root,
                    values=request,
                )
        if admission is not None:
            _verify_admitted_source(admission)
        request_path = attempt_path / ".astrid-capability-request.json"
        result_path = attempt_path / ".astrid-capability-result.json"
        payload = {
            "capability_kind": capability_kind,
            "capability_id": capability_id,
            "request": _json_safe(request),
            "definition": _json_safe(definition) if definition is not None else None,
            "admission": _json_safe(admission) if admission is not None else None,
            "result_path": str(result_path),
        }
        request_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        env = dict(child_env or build_child_subprocess_env(
            explicit_env={ASTRID_INTERNAL_INVOCATION: "1"},
        ))
        env[ASTRID_INTERNAL_INVOCATION] = "1"
        # The attempt directory is the child cwd; the host worker itself uses
        # this checkout, while external source-pack imports use only the
        # explicitly admitted import parents validated against source roots.
        package_parent = str(Path(__file__).resolve().parents[3])
        import_roots: list[str] = []
        if isinstance(admission, Mapping):
            raw_import_roots = admission.get("python_path_roots")
            if isinstance(raw_import_roots, (list, tuple)):
                source_roots = tuple(
                    Path(str(value)).expanduser().resolve()
                    for value in admission.get("source_roots", ())
                    if value
                )
                for raw_root in raw_import_roots:
                    import_root = Path(str(raw_root)).expanduser().resolve()
                    if not import_root.is_dir() or (
                        source_roots
                        and not any(source_root.is_relative_to(import_root) for source_root in source_roots)
                    ):
                        raise HostError("admitted Python import root is outside the source fence")
                    import_roots.append(str(import_root))
        env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys((package_parent, *import_roots)))
        env[ASTRID_PACKS_PATH] = os.pathsep.join(str(root) for root in self.pack_roots)
        broker_endpoint = str((child_env or {}).get("ASTRID_BROKER_PROXY") or "")
        process = popen_owned_group(
            _network_sandbox_argv([sys.executable, "-m", "astrid.core.execution.generic_host_worker", str(request_path)], attempt_path, broker_endpoint),
            cwd=str(attempt_path),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._track_process(process)
        try:
            while process.poll() is None:
                if cancelled is not None and cancelled():
                    _terminate_process_group(process)
                    raise HostCancelled(f"capability {capability_id!r} cancelled")
                time.sleep(0.05)
            stdout, stderr = process.communicate()
            if cancelled is not None and cancelled():
                raise HostCancelled(f"capability {capability_id!r} cancelled")
            if process.returncode != 0:
                secret_values = {
                    key: value for key, value in env.items()
                    if key.upper().endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
                }
                detail = self._scrub_secret_text((stderr or stdout).strip(), secret_values)
                raise HostError(
                    f"capability {capability_id!r} child exited {process.returncode}"
                    + (f": {detail[-3500:]}" if detail else "")
                )
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise HostError(
                    f"capability {capability_id!r} child returned no result"
                ) from exc
            if not isinstance(result, Mapping):
                raise HostError(f"capability {capability_id!r} child result is not an object")
            if not result.get("ok", False):
                raise HostError(str(result.get("error") or f"capability {capability_id!r} failed"))
            return SimpleNamespace(
                ok=True,
                returncode=result.get("returncode"),
                outputs=dict(result.get("outputs") or {}),
                payload=dict(result.get("payload") or {}),
                stdout=self._scrub_secret_text(stdout, {
                    key: value for key, value in env.items()
                    if key.upper().endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
                }),
                stderr=self._scrub_secret_text(stderr, {
                    key: value for key, value in env.items()
                    if key.upper().endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
                }),
                process_id=process.pid,
            )
        finally:
            self._untrack_process(process)
            _release_owned_group(process)
            env.clear()
            request_path.unlink(missing_ok=True)
            result_path.unlink(missing_ok=True)

    def run_task(
        self,
        task: Mapping[str, Any],
        *,
        lease_token: str,
        attempt_id: str | None = None,
        fence: int | None = None,
        keep_attempt: bool = False,
        provider_route_grant: str | None = None,
    ) -> Mapping[str, Any]:
        if self.client is None:
            raise HostError("runtime client is required to execute a task")
        if self._shutdown.is_set():
            raise HostCancelled("generic host is shutting down")
        for operation in ("heartbeat", "task", "settle", "fail", "upload_object"):
            if not callable(getattr(self.client, operation, None)):
                raise HostError(
                    f"runtime client lacks canonical {operation} operation"
                )
        task_data = task.get("task", task)
        task_id = str(task_data["id"])
        capability_id = str(task_data["capability"])
        attempt_id = attempt_id or (str(task_data["attempt_id"]) if task_data.get("attempt_id") else None)
        fence = fence if fence is not None else (int(task_data["fence"]) if task_data.get("fence") is not None else None)
        if not attempt_id or fence is None:
            raise HostError("runtime task execution requires attempt_id and fence")
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
        authorized_input_object_ids = task_data.get("input_object_ids")
        root = self.attempt_root or Path(tempfile.mkdtemp(prefix=f"astrid-attempt-{task_id}-")).resolve()
        root.mkdir(parents=True, exist_ok=True)
        settled = False
        network_broker: _NetworkBrokerContext | None = None
        # Every network attempt gets a fresh host-issued nonce.  It is part of
        # the immutable admission presented to an observable broker, so a
        # handshake captured from another task cannot be replayed.
        network_admission = {
            "capability_digest": record.capability_digest,
            "source_digest": record.source_digest,
            "dependency_digest": record.dependency_digest,
            "version": record.definition.version,
            "source_root": str(record.source_root),
            "source_roots": [str(root) for root in _admitted_source_roots(record.source_root, record.definition)],
            "network_nonce": secrets_module.token_urlsafe(24),
            "allowed_routes": list((_network_policy(record) or {}).get("allowed_routes", (_network_policy(record) or {}).get("allowed_destinations", ()))),
        }
        try:
            inputs = self._materialize_inputs(
                spec,
                root,
                authorized_input_object_ids=authorized_input_object_ids,
            )
            if record.adapter.family == "provider" and record.definition.isolation.network:
                policy = _network_policy(record)
                descriptor = (policy or {}).get("broker", {})
                binding = ProviderRouteGrantAuthority.binding(
                    capability_id=record.id,
                    capability_digest=record.capability_digest,
                    broker=descriptor,
                )
                token = provider_route_grant or task_data.get("provider_route_grant") or (
                    spec.get("provider_route_grant") if isinstance(spec, Mapping) else None
                )
                try:
                    self._provider_grants.consume(
                        token,
                        task_id=task_id,
                        capability_id=record.id,
                        capability_digest=record.capability_digest,
                        routes=_provider_routes(record, inputs),
                        broker_binding=binding,
                    )
                    self._pending_provider_grants.pop(task_id, None)
                except ProviderRouteGrantError as exc:
                    raise HostError(str(exc)) from exc
            network_broker = self._start_network_broker(record, root, network_admission, inputs)
            output_root = root / "outputs"
            output_root.mkdir(parents=True, exist_ok=True)
            cancel_signal = threading.Event()
            pump_stop = threading.Event()
            self.client.heartbeat(
                task_id,
                lease_token,
                attempt_id=attempt_id,
                fence=fence,
            )

            def pump_lease():
                while not pump_stop.wait(5.0):
                    try:
                        self.client.heartbeat(
                            task_id,
                            lease_token,
                            attempt_id=attempt_id,
                            fence=fence,
                        )
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

            def cancelled():
                if self._shutdown.is_set() or cancel_signal.is_set():
                    return True
                current = self.client.task(task_id)
                current_task = current.get("task", current) if isinstance(current, Mapping) else current
                state = current_task.get("status") if isinstance(current_task, Mapping) else getattr(current_task, "state", None)
                return state == "cancelled"

            try:
                if record.definition.command is not None:
                    result = self._run_command_definition(
                        record,
                        inputs,
                        output_root,
                        root,
                        cancelled=cancelled,
                        admission=network_admission,
                        network_broker=network_broker,
                    )
                else:
                    # Dispatch through the process boundary.  The immutable
                    # admitted definition is serialized for the child so a
                    # registry reload cannot silently select a different pack.
                    worker_admission = network_admission
                    worker_env, worker_secrets = self._child_environment(record, root, admission=worker_admission, network_broker=network_broker)
                    try:
                        result = self.invoke_capability(
                            capability_kind="executor",
                            capability_id=capability_id,
                            request={
                                "out": str(output_root),
                                "inputs": inputs,
                                "project": task_data.get("project_id"),
                                "project_was_auto_resolved": True,
                                "python_exec": sys.executable,
                                "run_id": task_id,
                                "run_root": str(root),
                                "invocation": "runtime",
                            },
                            attempt=root,
                            cancelled=cancelled,
                            definition=record.definition.to_dict(),
                            admission=worker_admission,
                            child_env=worker_env,
                        )
                    finally:
                        worker_env.clear()
                        worker_secrets.clear()
            finally:
                pump_stop.set()
                if pump_thread is not None:
                    pump_thread.join(timeout=2)
            current = self.client.task(task_id)
            current_task = current.get("task", current) if isinstance(current, Mapping) else current
            state = current_task.get("status") if isinstance(current_task, Mapping) else getattr(current_task, "state", None)
            if state == "cancelled":
                return {"task_id": task_id, "status": "cancelled", "cancelled": True}
            typed_outputs = self._typed_outputs(record, result, root)
            project_id = task_data.get("project_id")
            if typed_outputs and (not isinstance(project_id, str) or not project_id.strip()):
                raise HostError(
                    "runtime task is missing project_id for project-scoped output publication"
                )
            outputs = self._upload_outputs(typed_outputs, project_id=project_id) if typed_outputs else []
            payload = {"adapter_family": record.adapter.family, **(getattr(result, "payload", {}) or {})}
            network_evidence = self._network_evidence(
                root,
                admission=worker_admission if record.definition.command is None else network_admission,
                # Every network-required settlement needs signed evidence. A
                # Python child emits it through the hook; a native child must
                # have its admitted proxy/broker emit the same contract.
                required=bool(record.adapter.requires_network or record.definition.isolation.network),
                broker_required=network_broker is not None,
                broker_context=network_broker,
            )
            if network_evidence is not None:
                payload["network_evidence"] = network_evidence
            payload["process_evidence"] = {
                "capability_id": capability_id,
                "attempt_id": attempt_id,
                "fence": fence,
                "child_boundary": "subprocess",
                "process_id": getattr(result, "process_id", None),
                "returncode": getattr(result, "returncode", None),
            }
            effect = task_data.get("expected_effect")
            if isinstance(effect, list):
                effect = effect[0] if effect else None
            settlement = self.client.settle(
                task_id,
                lease_token,
                result=payload,
                outputs=outputs,
                effect=effect,
                attempt_id=attempt_id,
                fence=fence,
            )
            settled = True
            return settlement
        except HostCancelled:
            return {"task_id": task_id, "status": "cancelled", "cancelled": True}
        except Exception as exc:
            self.client.fail(
                task_id,
                lease_token,
                str(exc),
                retryable=False,
                attempt_id=attempt_id,
                fence=fence,
            )
            raise
        finally:
            if network_broker is not None:
                network_broker.stop()
            if not keep_attempt and self.attempt_root is None and settled:
                shutil.rmtree(root, ignore_errors=True)

    def cancel_task(self, task_id: str) -> Any:
        """Propagate cancellation through the runtime client boundary."""
        return self._client_operation("cancel")(task_id)

    def claim_once(self) -> Mapping[str, Any] | None:
        """Claim and execute one queued task through the generated boundary."""
        if self._shutdown.is_set():
            return None
        claim_next = self._client_operation("claim_next")
        # Readiness is an admission predicate, not merely registration
        # metadata.  Credentials, binaries, and external-pack provenance can
        # change while a host is running, so refresh the local preflight before
        # every claim and never ask the runtime to consider rows this process
        # cannot execute.  The runtime repeats this check against its own
        # capability status; keeping the candidate set aligned avoids claiming
        # an unavailable task only to fail it after lease acquisition.
        if not self.capabilities:
            self.discover()
        ready_records = self.preflight()
        capability_ids = sorted(
            record.id
            for record in ready_records
            if record.ready
            and str(record.matrix.get("disposition", ""))
            not in {"unsupported", "retired"}
        )
        if not capability_ids:
            return None
        claim = claim_next(
            executor_id=self.executor_id,
            capability_ids=capability_ids,
            idempotency_key=f"claim-{self.executor_id}-{time.time_ns()}",
        )
        if claim is None:
            return None
        if getattr(claim, "waiting_reason", None) and not getattr(claim, "attempt_id", None):
            return None
        claim_data = dict(claim) if isinstance(claim, Mapping) else {
            "attempt_id": getattr(claim, "attempt_id", None),
            "task_id": getattr(claim, "task_id", None),
            "lease_id": getattr(claim, "lease_id", None),
            "fence": getattr(claim, "fence", None),
            "runtime_epoch": getattr(claim, "runtime_epoch", None),
            "input_object_ids": list(getattr(claim, "input_object_ids", ()) or ()),
            "spec": getattr(claim, "spec", None),
            "project_id": getattr(claim, "project_id", None),
        }
        if not claim_data.get("task_id"):
            raise HostError("generated claim operation returned no task_id")
        task_id = str(claim_data["task_id"])
        task = self._client_operation("task")(task_id)
        if isinstance(task, Mapping):
            task_data = dict(task.get("task", task))
        else:
            task_data = {
                "id": getattr(task, "task_id", task_id),
                "capability": getattr(task, "capability_id", ""),
                "project_id": getattr(task, "project_id", None),
                "spec": {},
            }
        task_data.update(
            {
                "id": task_id,
                "attempt_id": claim_data.get("attempt_id"),
                "fence": claim_data.get("fence"),
            }
        )
        if claim_data.get("project_id") is not None:
            task_data["project_id"] = claim_data["project_id"]
        if claim_data.get("input_object_ids") is not None:
            task_data["input_object_ids"] = claim_data["input_object_ids"]
        # The claim response is the execution snapshot.  Preserve it over
        # the convenience task read so a worker cannot accidentally execute a
        # later/forked spec (and so claim-to-execute is a single immutable
        # handoff).
        if claim_data.get("spec") is not None:
            task_data["spec"] = claim_data["spec"]
        return self.run_task(
            {"task": task_data},
            lease_token=str(claim_data.get("lease_id") or ""),
            attempt_id=str(claim_data["attempt_id"]),
            fence=int(claim_data["fence"]),
            provider_route_grant=(
                task_data.get("provider_route_grant")
                or (task_data.get("spec", {}).get("provider_route_grant") if isinstance(task_data.get("spec"), Mapping) else None)
                or self._pending_provider_grants.pop(task_id, None)
                or (
                    self.request_provider_route_grant({"task": task_data})
                    if (
                        self.capabilities.get(str(task_data.get("capability"))) is not None
                        and self.capabilities[str(task_data.get("capability"))].adapter.family == "provider"
                        and self.capabilities[str(task_data.get("capability"))].definition.isolation.network
                    )
                    else None
                )
            ),
        )

    def run(self, *, once: bool = False, poll_seconds: float = 1.0, max_tasks: int | None = None) -> list[Mapping[str, Any]]:
        """Run the bounded worker claim loop; ``once`` is the test-friendly form."""
        results: list[Mapping[str, Any]] = []
        while not self._shutdown.is_set() and (max_tasks is None or len(results) < max_tasks):
            result = self.claim_once()
            if result is not None:
                results.append(result)
                if once:
                    break
                continue
            if once:
                break
            self._shutdown.wait(max(0.0, float(poll_seconds)))
        return results


def _cli() -> int:
    parser = argparse.ArgumentParser(prog="astrid-generic-host")
    parser.add_argument("command", nargs="?", choices=("run",), help="run the registered worker claim loop")
    parser.add_argument("--pack-root", action="append", required=True, help="pack/executor root to discover")
    parser.add_argument("--runtime-endpoint")
    parser.add_argument("--credential-file", help="owner-only file containing the worker bearer credential")
    parser.add_argument("--executor-id", default="astrid-pack-host")
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--attempt-root")
    parser.add_argument("--capability-matrix")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--run-task")
    parser.add_argument("--lease-token")
    parser.add_argument("--keep-attempt", action="store_true")
    parser.add_argument("--once", action="store_true", help="claim at most one task and exit")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--max-tasks", type=int)
    parser.add_argument("--ready-file", help="write host registration/readiness metadata before entering the claim loop")
    parser.add_argument("--source-checkout", help="absolute source checkout bound to this host")
    parser.add_argument("--support-root", help="absolute runtime support directory bound to this host")
    parser.add_argument("--runtime-instance-id", help="runtime instance identity bound to this host")
    args = parser.parse_args()
    credential = None
    credential_path = None
    if args.credential_file:
        credential_path = Path(args.credential_file).expanduser()
        try:
            if (not credential_path.is_absolute() or credential_path.is_symlink()
                    or not credential_path.is_file()
                    or credential_path.stat().st_mode & 0o777 != 0o600):
                raise OSError("credential file must be an absolute owner-only regular file")
            credential = credential_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            parser.error(str(exc))
        if not credential:
            parser.error("credential file is empty")
    client = RuntimeProtocolClient(args.runtime_endpoint, credential) if args.runtime_endpoint else None
    host = GenericPackHost(pack_roots=args.pack_root, client=client, executor_id=args.executor_id, max_concurrency=args.max_concurrency, attempt_root=args.attempt_root, capability_matrix=args.capability_matrix)
    host.discover()
    host.preflight()
    if args.source_checkout:
        source_checkout = Path(args.source_checkout).expanduser()
        if not source_checkout.is_absolute() or source_checkout.is_symlink() or not source_checkout.is_dir():
            parser.error("--source-checkout must be an absolute non-symlink directory")
    else:
        source_checkout = None
    if args.support_root:
        support_root = Path(args.support_root).expanduser()
        if not support_root.is_absolute() or support_root.is_symlink() or not support_root.is_dir():
            parser.error("--support-root must be an absolute non-symlink directory")
    else:
        support_root = None

    def handle_shutdown(_signum, _frame):
        host.shutdown()

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    registration = None
    if args.register or not args.run_task:
        registration = host.register() if args.register else {"capabilities": [record.manifest() for record in host.capabilities.values()]}
        print(json.dumps(registration, indent=2, sort_keys=True, default=_json_safe))
    if args.ready_file:
        ready_path = Path(args.ready_file).expanduser()
        if not ready_path.is_absolute() or ready_path.is_symlink():
            parser.error("--ready-file must be an absolute non-symlink path")
        ready_path.parent.mkdir(parents=True, exist_ok=True)
        ready_payload = {
            "status": "ready",
            "pid": os.getpid(),
            "process_birth_id": process_birth_identity(),
            "endpoint": str(args.runtime_endpoint).rstrip("/") if args.runtime_endpoint else None,
            "executor_id": host.executor_id,
            "capability_count": len(host.capabilities),
            "ready_capabilities": sorted(record.id for record in host.capabilities.values() if record.ready),
            "unready_capabilities": sorted(record.id for record in host.capabilities.values() if not record.ready),
            "registration": registration,
            "ready_file": str(ready_path),
            "credential_file": str(credential_path) if credential_path else None,
            "support_root": str(support_root) if support_root else None,
            "source_checkout": str(source_checkout) if source_checkout else None,
            "source_checkout_digest": source_checkout_digest(source_checkout) if source_checkout else None,
            "source_epoch": host.source_epoch,
            "runtime_instance_id": args.runtime_instance_id,
            "runtime_epoch": host.runtime_state.get("runtime_epoch"),
            "schema_digest": host.runtime_state.get("schema_digest"),
        }
        temporary = ready_path.with_name(f".{ready_path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(ready_payload, sort_keys=True, default=_json_safe), encoding="utf-8")
        temporary.replace(ready_path)
    if args.run_task:
        if client is None or not args.lease_token:
            parser.error("--run-task requires --runtime-endpoint, --credential-file, and --lease-token")
        task = client.task(args.run_task)
        print(json.dumps(host.run_task(task, lease_token=args.lease_token, keep_attempt=args.keep_attempt), indent=2, sort_keys=True))
    if args.command == "run":
        if client is None:
            parser.error("run requires --runtime-endpoint and --credential-file")
        if not args.register:
            host.register()
        print(json.dumps(host.run(once=args.once, poll_seconds=args.poll_seconds, max_tasks=args.max_tasks), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
