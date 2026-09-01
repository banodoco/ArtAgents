"""Immutable release gates for Astrid's vendored workspace client.

The runtime repository owns generation.  Astrid deliberately does not invoke
that repository's generator at test time: this gate proves that the checked-in
client is the exact, reviewed artifact identified by its source commit and
that its declared operation/signature surface has not drifted in-place.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path
import re

from banodoco_workspace_client import WorkspaceClient
from banodoco_workspace_client import generated
from banodoco_workspace_client.contract_metadata import (
    GENERATED_CLIENT_SHA256,
    OPERATIONS,
    PROTOCOL,
    SCHEMA_DIGEST,
    SOURCE_COMMIT,
    SOURCE_REPOSITORY,
)


ROOT = Path(__file__).resolve().parents[2]
GENERATED_PATH = ROOT / "banodoco_workspace_client" / "generated.py"

# These values are intentionally duplicated in the immutable test gate. A
# future runtime contract refresh must update the source commit, digest, and
# this test in one reviewed change; no ambient sibling checkout can silently
# alter the shipped transport.
PINNED_SOURCE_COMMIT = "52eab4ab96a54b6a1196d93e2f6f7cb0f0565baa"
PINNED_SOURCE_REPOSITORY = "https://github.com/banodoco/banodoco-workspace-runtime.git"
PINNED_PROTOCOL = "workspace.v1"
PINNED_SCHEMA_DIGEST = "sha256:8560e9cf98bda529314a620dd47650dc0a7d85ba8a7ead988f5f76f2b4932acb"
PINNED_GENERATED_CLIENT_SHA256 = "sha256:f3ddeaaf29e894ba87df80e3b82a33b839b675fc77d295fc06e4d2a8490c0f90"
PINNED_SIGNATURE_SHA256 = "sha256:85903d1bd1e79438632af084445dfc3121a34d57fe45faec89f4798dce37bd3c"


def _signature_digest() -> str:
    tree = ast.parse(GENERATED_PATH.read_text(encoding="utf-8"))
    client = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "WorkspaceClient"
    )
    signatures = [
        f"{node.name}:{ast.unparse(node.args)}\n"
        for node in client.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    return "sha256:" + hashlib.sha256("".join(signatures).encode()).hexdigest()


def _camel_to_snake(value: str) -> str:
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()


def test_vendored_client_is_the_frozen_runtime_artifact() -> None:
    assert SOURCE_REPOSITORY == PINNED_SOURCE_REPOSITORY
    assert SOURCE_COMMIT == PINNED_SOURCE_COMMIT
    assert PROTOCOL == PINNED_PROTOCOL == generated.PROTOCOL
    assert SCHEMA_DIGEST == PINNED_SCHEMA_DIGEST == generated.SCHEMA_DIGEST
    assert GENERATED_CLIENT_SHA256 == PINNED_GENERATED_CLIENT_SHA256
    assert "sha256:" + hashlib.sha256(GENERATED_PATH.read_bytes()).hexdigest() == GENERATED_CLIENT_SHA256
    assert _signature_digest() == PINNED_SIGNATURE_SHA256


def test_vendored_client_operation_catalog_matches_typed_methods() -> None:
    assert tuple(OPERATIONS) == tuple(generated.OPERATIONS)
    methods = {
        name
        for name, value in inspect.getmembers(WorkspaceClient, inspect.isfunction)
        if not name.startswith("_")
    }
    operation_methods = {_camel_to_snake(operation) for operation in OPERATIONS}
    # These are generated typed compositions, not independent OpenAPI
    # operation IDs: they compose updateDocument/ingestObject while retaining
    # a convenient resource-scoped method for product adapters.
    composed_helpers = {"update_timeline_document", "ingest_project_object"}
    assert methods - operation_methods == composed_helpers
    assert operation_methods <= methods


def test_frozen_mutation_signatures_require_idempotency_keys() -> None:
    for name in ("update_timeline_document", "create_generation", "create_variant"):
        parameter = inspect.signature(getattr(WorkspaceClient, name)).parameters["idempotency_key"]
        assert parameter.default is inspect.Parameter.empty


def test_obsolete_generic_client_artifact_is_absent() -> None:
    assert not (ROOT / "generated" / "runtime_client.py").exists()
    assert not (ROOT / "generated" / "runtime_client_metadata.py").exists()
    assert not (ROOT / "scripts" / "generate_runtime_client.py").exists()
