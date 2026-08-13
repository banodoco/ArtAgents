"""Failure replay bundles for backend renders.

A replay bundle snapshots every input and side effect needed to reproduce a
failed backend render offline: the qualified renderer id, the request and
manifest digests, the exact command argv, localized hashed copies of the
timeline/assets/theme inputs, redacted logs, any partial result the backend
wrote before failing, and structured failure metadata.

:class:`ReplayBundle` is the in-memory record.  :func:`write_replay_bundle`
persists one bundle directory that is self-contained and host-path-free:

* ``bundle.json`` — the manifest (digests, localized argv, input descriptors,
  redacted logs, redacted metadata, partial result);
* ``request.json`` — the exact wire request the backend received, with
  ``timeline_path``/``assets_registry_path`` rewritten to the bundle-local
  hashed input copies;
* ``inputs/<sha256>`` — byte-for-byte copies of every localized input file,
  named by their SHA-256 digest.

Credential and URL redaction reuses the transport's log redaction helpers so
the bundle can never reintroduce secrets the command transport already
stripped from diagnostics.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.hash import sha256_file

from .transport import _redact_log, _secret_environment_values

BUNDLE_SCHEMA_VERSION = 1
BUNDLE_FILENAME = "bundle.json"
REQUEST_FILENAME = "request.json"
RESULT_FILENAME = "result.json"
INPUTS_DIRNAME = "inputs"

#: Roles whose payload path keys are localized to the hashed input copies.
_PAYLOAD_PATH_ROLES: tuple[tuple[str, str], ...] = (
    ("timeline_path", "timeline"),
    ("assets_registry_path", "assets_registry"),
)


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


def write_replay_bundle(bundle: ReplayBundle, dest: str | Path) -> Path:
    """Persist *bundle* under *dest* and return the bundle directory.

    The directory contains ``bundle.json`` plus the localized hashed input
    files and the localized wire request.  Credentials and URLs are redacted
    from logs and metadata using the transport's redaction helpers.
    """

    dest_path = Path(dest)
    inputs_dir = dest_path / INPUTS_DIRNAME
    inputs_dir.mkdir(parents=True, exist_ok=True)
    secret_values = _secret_environment_values(os.environ, None)

    input_descriptors = _copy_inputs(bundle.inputs, inputs_dir=inputs_dir)
    localized_request = _localize_payload(bundle.payload, input_descriptors)
    if localized_request is not None:
        write_json_atomic(dest_path / REQUEST_FILENAME, localized_request)

    payload = {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "renderer_id": bundle.renderer_id,
        "request_digest": bundle.request_digest,
        "manifest_digest": bundle.manifest_digest,
        "argv": _localized_argv(bundle.argv),
        "inputs": input_descriptors,
        "logs": {
            str(stream): _redact_log(str(text), secret_values=secret_values)
            for stream, text in bundle.logs.items()
        },
        "partial_result": bundle.partial_result,
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

    Files are named by their SHA-256 digest only, so the descriptors contain
    no absolute host paths.  Missing sources are skipped (the backend-visible
    file may already have been cleaned up).
    """

    descriptors: dict[str, dict[str, str]] = {}
    for role, source in inputs.items():
        source_path = Path(source)
        try:
            if not source_path.is_file():
                continue
            digest = sha256_file(source_path)
        except OSError:
            continue
        target = inputs_dir / digest
        if not target.exists():
            try:
                shutil.copyfile(source_path, target)
            except OSError:
                continue
        descriptors[str(role)] = {
            "sha256": digest,
            "path": f"{INPUTS_DIRNAME}/{digest}",
        }
    return descriptors


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
