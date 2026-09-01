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
import re
from pathlib import Path

from banodoco_workspace_client import WorkspaceClient, generated
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
PINNED_SOURCE_COMMIT = "4050394c5395206f1ec6bf0d905ffbfb7bb0e4de"
PINNED_SOURCE_REPOSITORY = "https://github.com/banodoco/banodoco-workspace-runtime.git"
PINNED_PROTOCOL = "workspace.v1"
PINNED_SCHEMA_DIGEST = "sha256:e86426f871a0ae70359ad43196a8b8c172e8b1d83d6b44d5e45b30fc9ff5c7e2"
PINNED_GENERATED_CLIENT_SHA256 = "sha256:657c4f56deea2871c46d5f5be4b151256b373405dd559b06a92844efb3eea3ab"
PINNED_SIGNATURE_SHA256 = "sha256:e3160e51ea25d771b401ec02c3afc00ea422e657793bd1714ef8f8eadf352c52"


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
    # This is a generated typed composition, not an independent OpenAPI
    # operation ID: it composes updateDocument while retaining a convenient
    # resource-scoped method for product adapters.
    composed_helpers = {"update_timeline_document"}
    assert methods - operation_methods == composed_helpers
    assert operation_methods <= methods


def test_frozen_mutation_signatures_require_idempotency_keys() -> None:
    for name in (
        "update_timeline_document",
        "create_generation",
        "create_variant",
        "promote_project_shot_candidate",
    ):
        parameter = inspect.signature(getattr(WorkspaceClient, name)).parameters["idempotency_key"]
        assert parameter.default is inspect.Parameter.empty


def test_obsolete_generic_client_artifact_is_absent() -> None:
    assert not (ROOT / "generated" / "runtime_client.py").exists()
    assert not (ROOT / "generated" / "runtime_client_metadata.py").exists()
    assert not (ROOT / "scripts" / "generate_runtime_client.py").exists()
