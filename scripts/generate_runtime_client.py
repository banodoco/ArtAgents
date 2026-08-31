#!/usr/bin/env python3
"""Generate the checked-in Python conformance client from one contract input.

The runtime repository owns ``contract/component-manifest.json``.  This
generator intentionally accepts that file as an explicit input so a release
runner can place the same bytes beside the OpenAPI and schema-manifest inputs
in each clean checkout.  The generated source is a small, usable HTTP client;
it is not metadata pretending to be a client.  ``--check`` is the fail-closed
path used by source/release checks and never writes a checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = "GENERATOR-PYTHON-ASTRID"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _regular(path: str | Path, label: str) -> tuple[Path, bytes]:
    target = Path(path).expanduser()
    if target.is_symlink() or not target.is_file():
        raise SystemExit(f"{label} must be a regular file")
    return target, target.read_bytes()


def _json_input(path: str | Path, label: str, *, canonical: bool = True) -> tuple[Path, bytes, Any]:
    target, raw = _regular(path, label)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{label} must be UTF-8 JSON") from exc
    canonical_bytes = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if canonical and raw != canonical_bytes:
        raise SystemExit(f"{label} must use canonical JSON bytes")
    return target, raw, value


def _component_path(schema_path: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    sibling = schema_path.with_name("component-manifest.json")
    if sibling.is_file():
        return sibling
    raise SystemExit("--component-manifest is required when no staged sibling manifest exists")


def _operations(contract: bytes) -> tuple[str, ...]:
    text = contract.decode("utf-8")
    values = re.findall(r"(?m)^\s+operationId:\s*([^\s#]+)", text)
    result = tuple(sorted(values))
    if not result or len(set(result)) != len(result):
        raise SystemExit("--contract has no unique operationId projection")
    return result


def _client_definition(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    clients = manifest.get("clients")
    if not isinstance(clients, list):
        raise SystemExit("component manifest clients must be a list")
    matches = [item for item in clients if isinstance(item, Mapping) and item.get("generator") == GENERATOR]
    if len(matches) != 1:
        raise SystemExit(f"component manifest must declare exactly one {GENERATOR} client")
    client = matches[0]
    required = ("language", "metadata_output", "metadata_source", "output", "source")
    if client.get("language") != "python" or any(not isinstance(client.get(key), str) or not client.get(key) for key in required):
        raise SystemExit(f"component manifest {GENERATOR} client declaration is incomplete")
    return client


def _safe_relative(value: str, label: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value or "\\" in value:
        raise SystemExit(f"{label} must be a contained relative path")
    return path.as_posix()


def _validate_manifest(manifest: Mapping[str, Any], schema: Mapping[str, Any]) -> Mapping[str, Any]:
    if manifest.get("schema_version") != 1 or manifest.get("manifest_id") != "GENERATOR-CONFORMANCE-ID":
        raise SystemExit("component manifest identity is invalid")
    if manifest.get("protocol") != "workspace.v1":
        raise SystemExit("component manifest protocol is invalid")
    contract = manifest.get("contract")
    if not isinstance(contract, Mapping):
        raise SystemExit("component manifest contract declaration is missing")
    if contract.get("openapi") != schema.get("openapi") or contract.get("schema_manifest") != "manifest.json":
        raise SystemExit("component manifest is not bound to the supplied schema manifest")
    if schema.get("protocol") != manifest.get("protocol"):
        raise SystemExit("schema manifest protocol does not match component manifest")
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise SystemExit("component manifest fixtures must be a non-empty list")
    names = [item.get("name") for item in fixtures if isinstance(item, Mapping)]
    if len(names) != len(fixtures) or len(set(names)) != len(names) or any(not isinstance(name, str) for name in names):
        raise SystemExit("component manifest fixture names must be unique strings")
    return _client_definition(manifest)


def _py_tuple(values: tuple[str, ...]) -> str:
    return repr(values)


def _render_client(*, component_digest: str, contract_digest: str, schema_digest: str, operations: tuple[str, ...]) -> bytes:
    source = f'''"""Generated Python client; do not edit by hand.

This source is rendered from the shared component manifest and OpenAPI
operation projection.  Product adapters may use ``call`` for any declared
operation while keeping HTTP ownership in this generated boundary.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping

PROTOCOL = "workspace.v1"
GENERATOR = {GENERATOR!r}
COMPONENT_MANIFEST_SHA256 = {component_digest!r}
CONTRACT_SHA256 = {contract_digest!r}
SCHEMA_MANIFEST_SHA256 = {schema_digest!r}
OPERATIONS = {_py_tuple(operations)}

Transport = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, Mapping[str, str], bytes]]


class ApiError(RuntimeError):
    """A typed HTTP error returned by the neutral runtime."""

    def __init__(self, status: int, code: str, message: str, request_id: str = "", details: Mapping[str, Any] | None = None):
        super().__init__(f"{{code}}: {{message}}")
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id
        self.details = dict(details or {{}})


class WorkspaceClient:
    """Minimal generated transport client for the workspace.v1 operations."""

    def __init__(self, base_url: str, token: str | None = None, *, transport: Transport | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.transport = transport

    @staticmethod
    def supports(operation_id: str) -> bool:
        return operation_id in OPERATIONS

    def call(self, operation_id: str, method: str, path: str, *, body: bytes | None = None, headers: Mapping[str, str] | None = None, expected: tuple[int, ...] = (200,)) -> tuple[int, Mapping[str, str], bytes]:
        if not self.supports(operation_id):
            raise ValueError(f"unknown workspace operation: {{operation_id}}")
        request_headers = {{"Accept": "application/json", **dict(headers or {{}})}}
        if self.token:
            request_headers.setdefault("Authorization", f"Bearer {{self.token}}")
        if self.transport is not None:
            status, response_headers, payload = self.transport(method, path, request_headers, body)
        else:
            request = urllib.request.Request(self.base_url + path, data=body, headers=request_headers, method=method)
            try:
                with urllib.request.urlopen(request) as response:
                    status = response.status
                    response_headers = dict(response.headers.items())
                    payload = response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                response_headers = dict(exc.headers.items())
                payload = exc.read()
        if status not in expected:
            try:
                value = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                value = {{}}
            raise ApiError(status, str(value.get("code", "http_error")), str(value.get("message", f"HTTP {{status}}")), str(value.get("request_id", "")), value.get("details", {{}}))
        return status, response_headers, payload
'''
    return source.encode("utf-8")


def _render_metadata(*, component_digest: str, contract_digest: str, schema_digest: str, operations: tuple[str, ...]) -> bytes:
    return (f'''"""Generated Python client metadata; do not edit by hand."""

GENERATOR = {GENERATOR!r}
PROTOCOL = "workspace.v1"
COMPONENT_MANIFEST_SHA256 = {component_digest!r}
CONTRACT_SHA256 = {contract_digest!r}
SCHEMA_MANIFEST_SHA256 = {schema_digest!r}
OPERATIONS = {_py_tuple(operations)}
''').encode("utf-8")


def _fixture_bytes(manifest: Mapping[str, Any]) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for item in sorted(manifest["fixtures"], key=lambda value: value["name"]):
        name = _safe_relative(item["name"], "fixture name")
        value = item.get("value")
        if not isinstance(value, Mapping):
            raise SystemExit(f"fixture {name} must contain an object value")
        result[f"fixture-{name}"] = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return result


def _render_files(manifest: Mapping[str, Any], component_bytes: bytes, contract: bytes, schema: bytes) -> dict[str, bytes]:
    client = _client_definition(manifest)
    component_digest, contract_digest, schema_digest = _digest(component_bytes), _digest(contract), _digest(schema)
    operations = _operations(contract)
    files = {
        _safe_relative(str(client["output"]), "client output"): _render_client(component_digest=component_digest, contract_digest=contract_digest, schema_digest=schema_digest, operations=operations),
        _safe_relative(str(client["metadata_output"]), "metadata output"): _render_metadata(component_digest=component_digest, contract_digest=contract_digest, schema_digest=schema_digest, operations=operations),
    }
    files.update(_fixture_bytes(manifest))
    files["component-manifest.json"] = component_bytes
    artifacts = [{"byte_length": len(data), "path": path, "sha256": _digest(data)} for path, data in files.items() if path != "component-manifest.json"]
    artifacts.sort(key=lambda item: item["path"])
    files["manifest.json"] = (json.dumps({
        "artifacts": artifacts,
        "component_manifest_id": manifest["manifest_id"],
        "component_manifest_sha256": component_digest,
        "contract_sha256": contract_digest,
        "generator": GENERATOR,
        "operations": list(operations),
        "protocol": manifest["protocol"],
        "schema_manifest_sha256": schema_digest,
        "schema_version": 1,
    }, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    return files


def _write_files(root: Path, files: Mapping[str, bytes]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for relative, data in sorted(files.items()):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def _check_files(root: Path, files: Mapping[str, bytes], client: Mapping[str, Any], *, fixture_root: Path | None) -> int:
    expected_source = files[_safe_relative(str(client["output"]), "client output")]
    expected_metadata = files[_safe_relative(str(client["metadata_output"]), "metadata output")]
    checked = {
        Path(str(client["source"])).as_posix(): expected_source,
        Path(str(client["metadata_source"])).as_posix(): expected_metadata,
    }
    if fixture_root is not None:
        for relative, data in files.items():
            if relative.startswith("fixture-"):
                checked[(fixture_root / relative.removeprefix("fixture-")).as_posix()] = data
    failures = []
    for relative, expected in checked.items():
        path = Path(relative) if Path(relative).is_absolute() else root / relative
        if not path.is_file() or path.is_symlink() or path.read_bytes() != expected:
            failures.append(str(path))
    if failures:
        for path in failures:
            print(f"stale or mutated generated artifact: {path}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--schema-manifest", required=True)
    parser.add_argument("--component-manifest")
    parser.add_argument("--output-root")
    parser.add_argument("--source-root", default=str(ROOT))
    parser.add_argument("--fixture-root")
    parser.add_argument("--check", action="store_true", help="fail on stale checked-in source; never write")
    args = parser.parse_args()

    _, contract = _regular(args.contract, "--contract")
    schema_path, schema_bytes, schema = _json_input(args.schema_manifest, "--schema-manifest", canonical=False)
    _, component_bytes, manifest = _json_input(_component_path(schema_path, args.component_manifest), "--component-manifest")
    client = _validate_manifest(manifest, schema)
    files = _render_files(manifest, component_bytes, contract, schema_bytes)
    source_root = Path(args.source_root).expanduser().resolve()
    fixture_root = Path(args.fixture_root).expanduser().resolve() if args.fixture_root else None
    if args.check:
        return _check_files(source_root, files, client, fixture_root=fixture_root)
    if not args.output_root:
        raise SystemExit("--output-root is required unless --check is set")
    _write_files(Path(args.output_root).expanduser().resolve(), files)
    for relative in sorted(files):
        print(relative)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
