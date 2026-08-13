"""Failure replay bundles for backend renders.

A replay bundle snapshots every input and side effect needed to reproduce a
failed backend render offline: the qualified renderer id, the request and
manifest digests, the exact command argv, localized hashed copies of the
timeline/assets/theme inputs, redacted logs, any partial result the backend
wrote before failing, and structured failure metadata.

:class:`ReplayBundle` is the in-memory record.  :func:`write_replay_bundle`
persists one bundle directory that is self-contained and host-path-free:

* ``bundle.json`` — the manifest (digests, localized argv, input descriptors,
  redacted logs, redacted metadata, support report, backend configuration,
  partial-result descriptor);
* ``request.json`` — the exact wire request the backend received, with
  ``timeline_path``/``assets_registry_path`` rewritten to the bundle-local
  hashed input copies, redacted, and pinned by ``request_digest``;
* ``inputs/<sha256>`` — byte-for-byte copies of every localized input file,
  named by their SHA-256 digest (JSON inputs are rewritten so absolute host
  paths become bundle-relative references to captured inputs or the
  ``<host-path>`` placeholder);
* ``partial/<sha256>`` — the redacted partial result, when the backend wrote
  one before failing, named by the SHA-256 of its redacted content.

Credential and URL redaction reuses the transport's log redaction helpers so
the bundle can never reintroduce secrets the command transport already
stripped from diagnostics.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.paths import REPO_ROOT

from .contracts import compute_request_digest
from .transport import _redact_log, _secret_environment_values

BUNDLE_SCHEMA_VERSION = 1
BUNDLE_FILENAME = "bundle.json"
REQUEST_FILENAME = "request.json"
RESULT_FILENAME = "result.json"
INPUTS_DIRNAME = "inputs"
PARTIAL_DIRNAME = "partial"

#: Roles whose payload path keys are localized to the hashed input copies.
_PAYLOAD_PATH_ROLES: tuple[tuple[str, str], ...] = (
    ("timeline_path", "timeline"),
    ("assets_registry_path", "assets_registry"),
)

#: Marker used when an absolute host path inside a copied JSON input refers to
#: a file that was not itself captured (or would be a self/cycle reference).
_HOST_PATH_PLACEHOLDER = "<host-path>"


@dataclass
class ReplayBundle:
    """Everything needed to reproduce one backend invocation.

    ``inputs`` maps an input role (``timeline``, ``assets_registry``,
    ``theme``) to the *source* file the backend was given.  Persisting a
    bundle hashes each source with SHA-256, copies it under ``inputs/`` using
    its digest as the file name, and records only bundle-relative paths in
    ``bundle.json`` so no absolute host paths leak into the artifact.

    ``argv`` is the exact command the transport executed; the request and
    result paths are localized to the bundle at write time.

    ``support_report`` and ``backend_config`` are additive capture fields
    (the request-sensitive support evidence and the selected backend's
    configuration namespace).  ``result_path`` is the host path of the
    backend's authoritative result file when one was written; the bundle
    copies its redacted content under ``partial/<sha256>`` and records only
    the bundle-relative descriptor plus ``result_sha256``.
    """

    renderer_id: str
    request_digest: str
    manifest_digest: str
    argv: list[str]
    inputs: dict[str, str] = field(default_factory=dict)
    logs: dict[str, str] = field(default_factory=dict)
    partial_result: Any = None
    payload: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Batch 7 rework (T7.3/T7.4): additive capture fields.
    support_report: Any = None
    backend_config: dict[str, Any] | None = None
    result_path: str | None = None
    result_sha256: str | None = None


def write_replay_bundle(bundle: ReplayBundle, dest: str | Path) -> Path:
    """Persist *bundle* under *dest* and return the bundle directory.

    The directory contains ``bundle.json`` plus the localized hashed input
    files and the localized wire request.  Credentials and URLs are redacted
    from logs, metadata, the localized request, and the partial result using
    the transport's redaction helpers.

    ``request_digest`` is (re)computed from the localized, redacted request
    payload — exactly what ``replay`` verifies against the on-disk
    ``request.json`` — so a captured bundle always replays without a spurious
    tamper refusal.
    """

    dest_path = Path(dest)
    inputs_dir = dest_path / INPUTS_DIRNAME
    inputs_dir.mkdir(parents=True, exist_ok=True)
    secret_values = _secret_environment_values(os.environ, None)

    input_descriptors = _copy_inputs(bundle.inputs, inputs_dir=inputs_dir)
    localized_request = _localize_payload(bundle.payload, input_descriptors)
    if localized_request is not None:
        localized_request = _redact_metadata(
            localized_request, secret_values=secret_values
        )
        write_json_atomic(dest_path / REQUEST_FILENAME, localized_request)
        request_digest = compute_request_digest(localized_request)
    else:
        request_digest = bundle.request_digest

    partial_descriptor = _write_partial_result(
        bundle, dest_path=dest_path, secret_values=secret_values
    )

    payload = {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "renderer_id": bundle.renderer_id,
        "request_digest": request_digest,
        "manifest_digest": bundle.manifest_digest,
        "argv": _localized_argv(bundle.argv),
        "inputs": input_descriptors,
        "logs": {
            str(stream): _redact_log(str(text), secret_values=secret_values)
            for stream, text in bundle.logs.items()
        },
        "partial_result": (
            partial_descriptor if partial_descriptor is not None else None
        ),
        "result_sha256": (
            partial_descriptor["sha256"] if partial_descriptor is not None else None
        ),
        "result_path": (
            partial_descriptor["path"] if partial_descriptor is not None else None
        ),
        "backend_config": _redact_metadata(
            dict(bundle.backend_config or {}), secret_values=secret_values
        ),
        "support_report": (
            _redact_metadata(bundle.support_report, secret_values=secret_values)
            if bundle.support_report is not None
            else None
        ),
        "metadata": {
            str(key): _redact_metadata(value, secret_values=secret_values)
            for key, value in bundle.metadata.items()
        },
    }
    write_json_atomic(dest_path / BUNDLE_FILENAME, payload)
    return dest_path


def _copy_inputs(
    inputs: Mapping[str, str], *, inputs_dir: Path
) -> dict[str, dict[str, str]]:
    """Copy each input file under ``inputs/<sha256>`` and describe it.

    Files are named by the SHA-256 of their *final* content so the descriptors
    contain no absolute host paths.  JSON inputs are rewritten so absolute
    host paths become bundle-relative references to captured inputs or the
    ``<host-path>`` placeholder; non-JSON inputs and JSON without host paths
    are copied byte-for-byte.  Missing sources are skipped (the
    backend-visible file may already have been cleaned up).
    """

    sources: dict[str, Path] = {}
    for role, source in inputs.items():
        source_path = Path(source)
        try:
            if not source_path.is_file():
                continue
        except OSError:
            continue
        sources[str(role)] = source_path

    role_by_resolved = {
        _safe_resolve(str(source_path)): role for role, source_path in sources.items()
    }
    final_content: dict[str, bytes] = {}
    visiting: set[str] = set()

    def final_bytes(role: str) -> bytes:
        """Return the bytes that will be persisted for one input role."""
        if role in final_content:
            return final_content[role]
        source = sources[role]
        try:
            raw = source.read_bytes()
        except OSError:
            return b""
        visiting.add(role)
        try:
            content = _localize_json_input(
                raw,
                role=role,
                role_by_resolved=role_by_resolved,
                final_bytes=final_bytes,
                visiting=visiting,
            )
        finally:
            visiting.discard(role)
        final_content[role] = content
        return content

    descriptors: dict[str, dict[str, str]] = {}
    for role, source in sources.items():
        content = final_bytes(role)
        if not content:
            continue
        digest = hashlib.sha256(content).hexdigest()
        target = inputs_dir / digest
        if not target.exists():
            try:
                target.write_bytes(content)
            except OSError:
                continue
        descriptors[str(role)] = {
            "sha256": digest,
            "path": f"{INPUTS_DIRNAME}/{digest}",
        }
    return descriptors


def _localize_json_input(
    raw: bytes,
    *,
    role: str,
    role_by_resolved: Mapping[str, str],
    final_bytes: Any,
    visiting: set[str],
) -> bytes:
    """Rewrite absolute host paths inside one JSON input, preserving bytes
    when nothing needs to change."""

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return raw
    if not isinstance(data, (dict, list)):
        return raw
    rewritten = _rewrite_host_paths(
        data,
        role=role,
        role_by_resolved=role_by_resolved,
        final_bytes=final_bytes,
        visiting=visiting,
    )
    if rewritten is data:
        return raw
    return json.dumps(rewritten, ensure_ascii=False, indent=2).encode("utf-8")


def _rewrite_host_paths(
    node: Any,
    *,
    role: str,
    role_by_resolved: Mapping[str, str],
    final_bytes: Any,
    visiting: set[str],
) -> Any:
    """Deep-walk a JSON value and rewrite absolute host path strings.

    Only strings that are absolute paths are touched; every other string is
    returned unchanged.  A path that resolves to another captured input
    becomes a bundle-relative ``inputs/<sha256>`` reference; a path under the
    repository or home root that was not captured becomes ``<host-path>``;
    any other absolute path is left as-is.
    """

    if isinstance(node, dict):
        changed = False
        out: dict[str, Any] = {}
        for key, value in node.items():
            new_value = _rewrite_host_paths(
                value,
                role=role,
                role_by_resolved=role_by_resolved,
                final_bytes=final_bytes,
                visiting=visiting,
            )
            if new_value is not value:
                changed = True
            out[str(key)] = new_value
        return out if changed else node
    if isinstance(node, list):
        changed = False
        out = []
        for value in node:
            new_value = _rewrite_host_paths(
                value,
                role=role,
                role_by_resolved=role_by_resolved,
                final_bytes=final_bytes,
                visiting=visiting,
            )
            if new_value is not value:
                changed = True
            out.append(new_value)
        return out if changed else node
    if isinstance(node, str):
        return _rewrite_path_string(
            node,
            role=role,
            role_by_resolved=role_by_resolved,
            final_bytes=final_bytes,
            visiting=visiting,
        )
    return node


def _rewrite_path_string(
    value: str,
    *,
    role: str,
    role_by_resolved: Mapping[str, str],
    final_bytes: Any,
    visiting: set[str],
) -> str:
    """Rewrite one absolute path string, or return it unchanged."""

    if not value or not os.path.isabs(value):
        return value
    resolved = _safe_resolve(value)
    target_role = role_by_resolved.get(resolved)
    if target_role is not None and target_role != role and target_role not in visiting:
        return f"{INPUTS_DIRNAME}/{hashlib.sha256(final_bytes(target_role)).hexdigest()}"
    if target_role is not None:
        # Self-reference or a rewrite cycle cannot be expressed as a stable
        # hashed copy; redact rather than embed the host path.
        return _HOST_PATH_PLACEHOLDER
    if _under_root(resolved, REPO_ROOT) or _under_root(resolved, Path.home()):
        return _HOST_PATH_PLACEHOLDER
    return value


def _safe_resolve(value: str) -> str:
    try:
        return str(Path(value).expanduser().resolve(strict=False))
    except (OSError, RuntimeError):
        return value


def _under_root(path: str, root: Path) -> bool:
    root_text = str(root)
    return path == root_text or path.startswith(root_text + os.sep)


def _write_partial_result(
    bundle: ReplayBundle,
    *,
    dest_path: Path,
    secret_values: Sequence[str],
) -> dict[str, str] | None:
    """Persist the redacted partial result under ``partial/<sha256>``.

    Prefers the backend's own result file (byte-exact when nothing needs
    redaction), falling back to the parsed ``partial_result`` value.  Returns
    the bundle-relative descriptor, or ``None`` when no partial result exists.
    """

    raw: str | None = None
    if bundle.result_path:
        try:
            source = Path(bundle.result_path)
            if source.is_file():
                raw = source.read_text(encoding="utf-8")
        except OSError:
            raw = None
    if raw is None and bundle.partial_result is not None:
        if isinstance(bundle.partial_result, str):
            raw = bundle.partial_result
        else:
            raw = json.dumps(bundle.partial_result, ensure_ascii=False)
    if raw is None or not raw.strip():
        return None

    try:
        parsed = json.loads(raw)
        redacted = _redact_metadata(parsed, secret_values=secret_values)
        if redacted == parsed:
            text = raw
        else:
            text = json.dumps(redacted, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        text = _redact_log(raw, secret_values=secret_values)
    if not text.strip():
        return None

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    partial_dir = dest_path / PARTIAL_DIRNAME
    partial_dir.mkdir(parents=True, exist_ok=True)
    (partial_dir / digest).write_text(text, encoding="utf-8")
    return {"sha256": digest, "path": f"{PARTIAL_DIRNAME}/{digest}"}


def _localize_payload(
    payload: Mapping[str, Any] | None,
    input_descriptors: Mapping[str, dict[str, str]],
) -> dict[str, Any] | None:
    """Rewrite wire-request input paths to their bundle-local hashed copies."""

    if payload is None:
        return None
    localized = dict(payload)
    for key, role in _PAYLOAD_PATH_ROLES:
        descriptor = input_descriptors.get(role)
        if key in localized and descriptor is not None:
            localized[key] = descriptor["path"]
    return localized


def _localized_argv(argv: Sequence[str]) -> list[str]:
    """Point ``--request``/``--result`` at the bundle-local file names."""

    localized: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--request" and index + 1 < len(argv):
            localized.extend([argument, REQUEST_FILENAME])
            index += 2
        elif argument == "--result" and index + 1 < len(argv):
            localized.extend([argument, RESULT_FILENAME])
            index += 2
        else:
            localized.append(str(argument))
            index += 1
    return localized


def _redact_metadata(value: Any, *, secret_values: Sequence[str]) -> Any:
    """Redact credentials/URLs from metadata, recursing into containers."""

    if isinstance(value, str):
        return _redact_log(value, secret_values=secret_values)
    if isinstance(value, list):
        return [
            _redact_metadata(item, secret_values=secret_values) for item in value
        ]
    if isinstance(value, dict):
        return {
            str(key): _redact_metadata(item, secret_values=secret_values)
            for key, item in value.items()
        }
    return value


__all__ = [
    "BUNDLE_FILENAME",
    "BUNDLE_SCHEMA_VERSION",
    "INPUTS_DIRNAME",
    "REQUEST_FILENAME",
    "RESULT_FILENAME",
    "ReplayBundle",
    "write_replay_bundle",
]
