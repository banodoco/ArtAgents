"""Executable m4 contract tests (plan Step 2 / task T2).

These tests assert that the four frozen contract documents and the executable
surface agree **exactly** on:

- the SDK domain result envelope (``ok``/``data``/``error``/``receipt``/
  ``idempotency_key``) and the error object (``code``/``message``/``details``)
  with the exact nine-code taxonomy;
- the exposed receipt shape and the rule that bridge responses never expose it;
- project-scoped idempotency, deterministic identity, canonical semantic
  request hashing, replay, mismatch-before-mutation, and generated-key return;
- the five frozen media relation kinds and the repository-enforced rules, with
  no invented per-kind direction matrix;
- the conservative m4 platform matrix (Linux, CPython 3.11/3.12, editable
  install, Node 20.19, current stable Chromium, Astrid Release Owner,
  Sprint-5 deadline) distinct from m6 release packaging;
- the inspected Reigh commit, the five pinned selectors, the four observed
  contradictions, and the reporting-only external-gate disposition (correction
  authority DENIED for m4, absent-local-pin observation, upstream
  owner/authorization needed);
- the temporary exclusive-owner lock deviation with its m6 closure design;
- the reserved save-as-copy route: documented as planned m6, resolving through
  the catch-all 404 grammar in m4, with no ``timelines copy`` CLI verb.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

SDK_DOC = REPO_ROOT / "docs/contracts/astrid-sdk-v10.md"
PLATFORM_DOC = REPO_ROOT / "docs/contracts/supported-platforms.md"
DECISIONS_DOC = REPO_ROOT / "docs/astrid-v10-implementation-decisions.md"
BRIDGE_DOC = REPO_ROOT / "docs/contracts/astrid-bridge-v10.md"

ENVELOPE_KEYS = {"ok", "data", "error", "receipt", "idempotency_key"}
ERROR_OBJECT_KEYS = {"code", "message", "details"}
ERROR_CODES = {
    "validation_error",
    "not_found",
    "conflict",
    "stale_version",
    "terminal_state",
    "idempotency_mismatch",
    "integrity_error",
    "unavailable",
    "internal_error",
}
MEDIA_RELATION_KINDS = [
    "derived_from",
    "variant_of",
    "uses_as_input",
    "mask_for",
    "audio_for",
]
REIGH_COMMIT = "bc2d8b0327c1c7dbdcd7b7445440d8ca180dd677"
REIGH_SELECTORS = [
    "AstridBridgeDataProvider.test.ts",
    "providerCompatibility.astrid.test.ts",
    "useTimelinePersistence.test.tsx",
    "usePollSync.test.ts",
    "timeline-save-utils.test.ts",
]


def _doc(path: Path) -> str:
    assert path.is_file(), f"contract document missing: {path}"
    # Collapse markdown line wraps so substring assertions are robust to
    # where the editor wraps a sentence.
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. SDK envelope, error taxonomy, receipt shape
# ---------------------------------------------------------------------------


def test_sdk_doc_frozen_status_and_normative_sources() -> None:
    text = _doc(SDK_DOC)
    assert "frozen for milestone m4" in text
    assert "docs/contracts/astrid-bridge-v10.md" in text


def test_sdk_doc_freezes_exact_envelope_keys() -> None:
    text = _doc(SDK_DOC)
    # The document must enumerate exactly the five keys, with none missing.
    for key in ENVELOPE_KEYS:
        assert f"`{key}`" in text, f"envelope key {key!r} not documented"
    # The doc must state the key set is closed.
    assert "exactly five keys" in text
    assert "No other top-level keys exist" in text


def test_sdk_doc_freezes_error_object_and_taxonomy() -> None:
    text = _doc(SDK_DOC)
    for key in ERROR_OBJECT_KEYS:
        assert f"`{key}`" in text, f"error-object key {key!r} not documented"
    assert "exactly three keys" in text
    for code in ERROR_CODES:
        assert f"`{code}`" in text, f"error code {code!r} not documented"
    assert "No other codes exist in m4" in text


def test_sdk_doc_freezes_receipt_shape() -> None:
    text = _doc(SDK_DOC)
    receipt_keys = {
        "receipt_id",
        "command_kind",
        "idempotency_key",
        "request_hash",
        "project_id",
        "project_seq",
        "event_ids",
        "result",
        "created_at",
    }
    for key in receipt_keys:
        assert f'"{key}"' in text, f"receipt key {key!r} not documented"
    assert "read-only" in text


def test_bridge_never_exposes_receipts_in_either_doc() -> None:
    sdk = _doc(SDK_DOC)
    bridge = _doc(BRIDGE_DOC)
    # SDK doc: explicit prohibition on the bridge side.
    assert "Bridge responses never expose receipts" in sdk
    assert "no receipt field, no idempotency key" in sdk
    # Bridge doc: receipt secrecy section lists the prohibited fields.
    assert "Receipt secrecy" in bridge
    for field in ("txn_id", "request_hash", "idempotency_key", "event_ids_json"):
        assert field in bridge, f"bridge receipt-secrecy field {field!r} missing"


# ---------------------------------------------------------------------------
# 2. Idempotency and deterministic identity
# ---------------------------------------------------------------------------


def test_idempotency_contract_is_documented() -> None:
    text = _doc(SDK_DOC)
    assert "project-scoped" in text
    assert "(project_id, idempotency_key)" in text
    assert "generates" in text and "before any mutation" in text
    assert "replays" in text
    assert "idempotency_mismatch" in text
    assert "before any mutation" in text
    # Deterministic identity: derived solely from kind/scope/key/ordinal.
    assert "command kind" in text
    assert "project/global scope" in text
    assert "child ordinal" in text


def test_canonical_hash_excludes_incidental_fields() -> None:
    text = _doc(SDK_DOC)
    assert "canonical JSON hash" in text
    assert "Generated timestamps, transaction IDs, and incidental paths" in text
    assert "outside request identity" in text


# ---------------------------------------------------------------------------
# 3. Media relation vocabulary and repository rules
# ---------------------------------------------------------------------------


def test_media_relation_kinds_frozen_verbatim_in_all_docs() -> None:
    sdk = _doc(SDK_DOC)
    decisions = _doc(DECISIONS_DOC)
    # Verbatim DDL list in the decisions artifact (section 7) and the m4
    # freeze (section 17), and the SDK contract (section 5).
    assert "('derived_from','variant_of','uses_as_input','mask_for','audio_for')" in decisions
    for kind in MEDIA_RELATION_KINDS:
        assert f"`{kind}`" in sdk, f"SDK doc missing kind {kind!r}"
        assert f"`{kind}`" in decisions, f"decisions doc missing kind {kind!r}"


def test_media_relation_repository_rules_documented() -> None:
    sdk = _doc(SDK_DOC).lower()
    decisions = _doc(DECISIONS_DOC).lower()
    rules = [
        "same-project",
        "self-edge rejection",
        "duplicate rejection",
        "one `variant_of` parent",
        "variant-cycle",
    ]
    for rule in rules:
        assert rule in sdk, f"SDK doc missing rule {rule!r}"
        assert rule in decisions, f"decisions doc missing rule {rule!r}"


def test_no_per_kind_direction_matrix_invented() -> None:
    sdk = _doc(SDK_DOC)
    decisions = _doc(DECISIONS_DOC)
    assert "no per-kind direction matrix" in sdk
    assert "none may be invented" in sdk
    assert "no per-kind direction matrix" in decisions


# ---------------------------------------------------------------------------
# 4. Conservative platform matrix
# ---------------------------------------------------------------------------


def test_platform_matrix_frozen_values() -> None:
    text = _doc(PLATFORM_DOC)
    assert "frozen for milestone m4" in text
    assert "Linux" in text
    assert "3.11 and 3.12" in text
    assert "editable installation" in text
    assert "20.19" in text
    assert "current stable Chromium" in text
    assert "Astrid Release Owner" in text
    assert "Sprint 5" in text
    assert "m6 release packaging" in text


def test_platform_matrix_matches_decisions_artifact() -> None:
    platform = _doc(PLATFORM_DOC)
    decisions = _doc(DECISIONS_DOC)
    assert "docs/astrid-v10-implementation-decisions.md" in platform
    for value in ("CPython 3.11 and 3.12", "Node 20.19", "current stable Chromium"):
        assert value in decisions, f"decisions doc missing matrix value {value!r}"


# ---------------------------------------------------------------------------
# 5. Inspected Reigh state and external-gate disposition
# ---------------------------------------------------------------------------


def test_reigh_inspection_records_pinned_commit_and_selectors() -> None:
    text = _doc(DECISIONS_DOC)
    assert REIGH_COMMIT in text
    for selector in REIGH_SELECTORS:
        assert selector in text, f"pinned selector {selector!r} missing"


def test_reigh_disposition_records_all_four_contradictions() -> None:
    text = _doc(DECISIONS_DOC)
    contradictions = [
        "ignores `expectedVersion`",
        "`{config}`-only save body",
        "separate registry PUT",
        "local-file/FSA path",
    ]
    for item in contradictions:
        assert item in text, f"contradiction {item!r} missing"


def test_reigh_disposition_is_reporting_only_and_authority_denied() -> None:
    text = _doc(DECISIONS_DOC)
    assert "DENIED" in text
    assert "reporting-only" in text
    assert "absent-local-pin" in text or "Absent-local-pin" in text
    assert "not present" in text
    assert "verify it mechanically" in text
    assert "upstream" in text
    assert "authorization" in text
    assert "never" in text and "m4-gate" in text


def test_reigh_disposition_matches_bridge_contract_authority() -> None:
    decisions = _doc(DECISIONS_DOC)
    bridge = _doc(BRIDGE_DOC).lower()
    # The bridge contract remains authoritative; the decisions artifact records
    # that no compatibility behavior is added to Astrid.
    assert "frozen Astrid bridge contract remains authoritative" in decisions
    assert "No compatibility" in decisions
    assert "any other path returns 404" in bridge


# ---------------------------------------------------------------------------
# 6. Temporary owner-lock deviation and m6 closure
# ---------------------------------------------------------------------------


def test_owner_lock_deviation_documented_with_m6_closure() -> None:
    text = _doc(DECISIONS_DOC)
    assert "exclusive-owner lock" in text
    assert "temporary North Star deviation" in text
    assert "unavailable" in text
    assert "one process" in text
    assert "m6 closure" in text
    assert "loopback RPC" in text or "service-owner protocol" in text
    assert "removed in m6" in text


# ---------------------------------------------------------------------------
# 7. Reserved save-as-copy route
# ---------------------------------------------------------------------------


def test_bridge_doc_has_reserved_copy_section() -> None:
    text = _doc(BRIDGE_DOC)
    assert "Reserved route" in text
    assert "planned m6, NOT implemented in m4" in text
    assert "POST /projects/:slug/timelines/:ref/copy" in text
    assert "not registered" in text
    assert "optional target name" in text
    assert "deterministic derived key" in text
    assert "source head" in text
    assert "409 timeline_version_conflict" in text
    assert "fresh id" in text
    assert "config_version" in text and "0" in text
    assert "copied_from" in text
    assert "404/409/422" in text
    assert "never exposes a receipt or idempotency key" in text


def test_decisions_doc_records_reserved_copy_semantics() -> None:
    text = _doc(DECISIONS_DOC)
    assert "Reserved save-as-copy route" in text
    assert "planned m6, not implemented in m4" in text
    assert "timelines copy" in text
    assert "not implemented" in text


def test_reserved_copy_route_is_not_in_implemented_route_table() -> None:
    text = _doc(BRIDGE_DOC)
    # The implemented route table (section 1) must not list the copy route.
    table = text.split("## 1. Routes and methods")[1].split("## 2.")[0]
    assert "/copy" not in table
    assert "copy" not in table


def test_reserved_copy_route_404s_on_live_server(tmp_path: Path) -> None:
    """m4 leaves the copy route unregistered: both verbs hit the catch-all 404.

    Uses the real local bridge server without any bridge composition — the
    catch-all grammar answers before any repository access, matching the
    frozen "any other path → 404" rule.
    """
    from astrid.core.integrations.reigh.local_bridge_server import (
        create_local_bridge_server,
    )

    server = create_local_bridge_server(projects_root=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    url = f"http://{host}:{port}/projects/p/timelines/t/copy"
    try:
        # POST /copy must 404 with the frozen not_found envelope.
        req = Request(url, data=b"{}", method="POST")
        req.add_header("Content-Type", "application/json")
        with pytest.raises(HTTPError) as exc_info:
            urlopen(req)  # noqa: S310 - localhost test server only
        assert exc_info.value.code == 404
        body = json.loads(exc_info.value.read().decode("utf-8"))
        assert body["error"] == "not_found"
        # GET /copy must also 404.
        with pytest.raises(HTTPError) as get_exc:
            urlopen(url)  # noqa: S310 - localhost test server only
        assert get_exc.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_no_timelines_copy_cli_verb_registered() -> None:
    """No ``timelines copy`` verb is registered anywhere in m6.

    Asserts both the frozen documents and the executable CLI parser surface.
    """
    bridge = _doc(BRIDGE_DOC)
    decisions = _doc(DECISIONS_DOC)
    assert "No `timelines copy` CLI verb is registered" in bridge
    assert "`timelines copy` CLI verb" in decisions

    from astrid.packs.timeline.cli import build_parser

    parser = build_parser(object())
    verbs: list[str] = []
    for action in parser._actions:
        if getattr(action, "choices", None):
            verbs = list(action.choices.keys())
    assert verbs, "timeline CLI parser exposes no subcommands"
    assert "copy" not in verbs


# ---------------------------------------------------------------------------
# 8. Cross-document agreement (SC2)
# ---------------------------------------------------------------------------


def test_documents_agree_on_error_taxonomy() -> None:
    decisions = _doc(DECISIONS_DOC)
    for code in ERROR_CODES:
        assert f"`{code}`" in decisions, f"decisions doc missing error code {code!r}"


def test_documents_agree_on_envelope_and_identity_rules() -> None:
    decisions = _doc(DECISIONS_DOC)
    # The decisions artifact must point at the SDK contract as the authority
    # for the envelope, receipt, and taxonomy values.
    assert "docs/contracts/astrid-sdk-v10.md" in decisions
    for key in ENVELOPE_KEYS:
        assert f"`{key}`" in decisions, f"decisions doc missing envelope key {key!r}"


def test_sdk_doc_matches_bridge_doc_on_boundary() -> None:
    sdk = _doc(SDK_DOC)
    bridge = _doc(BRIDGE_DOC)
    # The bridge derives a hidden deterministic save key; the SDK accepts
    # caller/generated keys; both share one atomic command (frozen boundary).
    assert "hidden deterministic bridge-derived save key" in sdk
    assert "No `idempotency_key` field exists on this route" in bridge
    assert "derives an internal idempotency key" in bridge