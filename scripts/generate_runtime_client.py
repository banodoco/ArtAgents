#!/usr/bin/env python3
"""Generate the small, dependency-free B11.1 runtime-client artifact.

The release identity runner invokes this command in a fresh staging
directory.  Inputs are explicit bytes; no repository or network state is
consulted, which makes the output safe to reproduce from a pinned checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _input(path: str, label: str) -> bytes:
    target = Path(path).expanduser().resolve()
    if target.is_symlink() or not target.is_file():
        raise SystemExit(f"{label} must be a regular file")
    return target.read_bytes()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--schema-manifest", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    contract = _input(args.contract, "--contract")
    schema = _input(args.schema_manifest, "--schema-manifest")
    output = Path(args.output_root).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    # The operation projection intentionally uses the canonical OpenAPI text
    # without a YAML dependency.  The contract digest remains authoritative
    # even when an operation line is not present.
    operations = sorted(
        line.split("operationId:", 1)[1].strip()
        for line in contract.decode("utf-8").splitlines()
        if "operationId:" in line
    )
    metadata = {
        "generator": "GENERATOR-PYTHON-ASTRID",
        "protocol": "workspace.v1",
        "contract_sha256": _digest(contract),
        "schema_manifest_sha256": _digest(schema),
        "operations": operations,
    }
    (output / "runtime_client.py").write_text(
        '"""Generated B11.1 runtime-client metadata; do not edit."""\n\n'
        + "CONTRACT_SHA256 = " + repr(metadata["contract_sha256"]) + "\n"
        + "SCHEMA_MANIFEST_SHA256 = " + repr(metadata["schema_manifest_sha256"]) + "\n"
        + "OPERATIONS = " + repr(tuple(operations)) + "\n",
        encoding="utf-8",
    )
    (output / "manifest.json").write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
