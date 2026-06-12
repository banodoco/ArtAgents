"""CAS identity tests — stable reuse, bust-on-change, and byte-content separation.

Proves that the identity CAS primitives operate on *input references + producer
identity + producer version* without ever reading or hashing produced artifact
bytes, and that legacy byte-content helpers retain their original semantics.

Coverage:
  * canonical_json_digest  — deterministic canonical JSON → sha256
  * executor_definition_digest — stable digest of an executor definition
  * input_reference_digest — stable digest of input refs (never opens paths)
  * identity_digest        — sha256(input_digest + producer_id + producer_version)
  * link_identity_artifact — intern by identity key (no byte hashing)
  * Separation between byte-content CAS (intern) and identity-keyed reuse.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import patch

from astrid.core.io.cas import (
    canonical_json_digest,
    executor_definition_digest,
    hash_file,
    identity_digest,
    input_reference_digest,
    intern,
    link_identity_artifact,
)


# ── helpers ─────────────────────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _FakeExecutorDef:
    """Minimal stub with the ``to_dict()`` contract required by
    :func:`executor_definition_digest`."""

    def __init__(self, **kw: Any) -> None:
        self._fields = kw

    def to_dict(self) -> dict[str, Any]:
        return dict(self._fields)


# ═══════════════════════════════════════════════════════════════════════════
# canonical_json_digest
# ═══════════════════════════════════════════════════════════════════════════

def test_canonical_json_deterministic_across_key_order() -> None:
    """Same logical dict with different key insertion order → same digest."""
    a = canonical_json_digest({"b": 1, "a": 2})
    b = canonical_json_digest({"a": 2, "b": 1})
    assert a == b
    assert len(a) == 64  # sha256 hex


def test_canonical_json_different_values_different_digest() -> None:
    """Different payloads produce different digests."""
    d1 = canonical_json_digest({"key": "value1"})
    d2 = canonical_json_digest({"key": "value2"})
    assert d1 != d2


def test_canonical_json_handles_nested_structures() -> None:
    """Nested dicts, lists, and mixed types are serialised deterministically."""
    payload = {
        "strings": ["z", "a", "m"],
        "numbers": [3, 1, 2],
        "nested": {"inner": True, "count": 42},
        "none_val": None,
    }
    d1 = canonical_json_digest(payload)
    d2 = canonical_json_digest(payload)
    assert d1 == d2
    assert len(d1) == 64


def test_canonical_json_list_order_matters() -> None:
    """Unlike input_reference_digest, canonical_json_digest *does* preserve
    list order — it's a raw JSON hash."""
    d1 = canonical_json_digest([1, 2, 3])
    d2 = canonical_json_digest([3, 2, 1])
    assert d1 != d2


def test_canonical_json_compact_separators_stable() -> None:
    """Compact JSON separators produce the same output across Python versions."""
    # The implementation uses (',', ':') — verify the output is compact.
    digest = canonical_json_digest({"a": 1, "b": [2, 3]})
    # Manually compute expected with same settings.
    import json
    raw = json.dumps({"a": 1, "b": [2, 3]}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected = _sha256(raw.encode("utf-8"))
    assert digest == expected


# ═══════════════════════════════════════════════════════════════════════════
# executor_definition_digest
# ═══════════════════════════════════════════════════════════════════════════

def test_executor_definition_digest_stable_for_same_def() -> None:
    """Same to_dict() output → same digest."""
    ed1 = _FakeExecutorDef(id="step-1", name="Demo", kind="built_in", version="1.0.0")
    ed2 = _FakeExecutorDef(id="step-1", name="Demo", kind="built_in", version="1.0.0")
    assert executor_definition_digest(ed1) == executor_definition_digest(ed2)


def test_executor_definition_digest_busts_on_version_change() -> None:
    """Changing the version field changes the digest."""
    ed1 = _FakeExecutorDef(id="step-1", name="Demo", kind="built_in", version="1.0.0")
    ed2 = _FakeExecutorDef(id="step-1", name="Demo", kind="built_in", version="1.0.1")
    assert executor_definition_digest(ed1) != executor_definition_digest(ed2)


def test_executor_definition_digest_busts_on_id_change() -> None:
    """Changing the executor id changes the digest."""
    ed1 = _FakeExecutorDef(id="step-a", name="Demo", kind="built_in", version="1.0.0")
    ed2 = _FakeExecutorDef(id="step-b", name="Demo", kind="built_in", version="1.0.0")
    assert executor_definition_digest(ed1) != executor_definition_digest(ed2)


def test_executor_definition_digest_busts_on_kind_change() -> None:
    """Changing the kind changes the digest."""
    ed1 = _FakeExecutorDef(id="step-1", name="Demo", kind="built_in", version="1.0.0")
    ed2 = _FakeExecutorDef(id="step-1", name="Demo", kind="external", version="1.0.0")
    assert executor_definition_digest(ed1) != executor_definition_digest(ed2)


def test_executor_definition_digest_busts_on_new_field() -> None:
    """Adding a field (e.g. description) changes the digest."""
    ed1 = _FakeExecutorDef(id="step-1", name="Demo", kind="built_in", version="1.0.0")
    ed2 = _FakeExecutorDef(id="step-1", name="Demo", kind="built_in", version="1.0.0", description="Does something")
    assert executor_definition_digest(ed1) != executor_definition_digest(ed2)


# ═══════════════════════════════════════════════════════════════════════════
# input_reference_digest
# ═══════════════════════════════════════════════════════════════════════════

def test_input_reference_digest_order_independent_for_lists() -> None:
    """Same set of input refs in different order → same digest."""
    refs_a = ["step_b.produces.x", "step_a.produces.y"]
    refs_b = ["step_a.produces.y", "step_b.produces.x"]
    assert input_reference_digest(refs_a) == input_reference_digest(refs_b)


def test_input_reference_digest_different_refs_different_digest() -> None:
    """Different input refs → different digest."""
    d1 = input_reference_digest(["step_a.produces.x"])
    d2 = input_reference_digest(["step_b.produces.x"])
    assert d1 != d2


def test_input_reference_digest_dict_stable_across_key_order() -> None:
    """Dict inputs are sorted by key before hashing."""
    d1 = input_reference_digest({"b": 1, "a": 2})
    d2 = input_reference_digest({"a": 2, "b": 1})
    assert d1 == d2


def test_input_reference_digest_dict_different_values_different_digest() -> None:
    """Dicts with different values produce different digests."""
    d1 = input_reference_digest({"key": "alpha"})
    d2 = input_reference_digest({"key": "beta"})
    assert d1 != d2


def test_input_reference_digest_never_opens_paths() -> None:
    """Path-like string values are treated as opaque strings, never resolved."""
    # Even a non-existent path reference should work fine.
    refs = ["/nonexistent/path/output.bin", "step.produces.other"]
    digest = input_reference_digest(refs)
    assert len(digest) == 64
    # Same refs in different order → same digest.
    assert digest == input_reference_digest(list(reversed(refs)))


def test_input_reference_digest_single_scalar() -> None:
    """A single string input ref is handled correctly."""
    digest = input_reference_digest("step_a.produces.x")
    assert len(digest) == 64
    assert digest == canonical_json_digest("step_a.produces.x")


def test_input_reference_digest_empty_list() -> None:
    """Empty list of inputs produces a stable digest."""
    d1 = input_reference_digest([])
    d2 = input_reference_digest([])
    assert d1 == d2
    assert len(d1) == 64


# ═══════════════════════════════════════════════════════════════════════════
# identity_digest
# ═══════════════════════════════════════════════════════════════════════════

_ID_DIGEST = "a" * 64
_PRODUCER_ID = "step-1"
_PRODUCER_VERSION = "v1.0.0"


def test_identity_digest_stable_for_identical_inputs() -> None:
    """Same input digest + producer_id + producer_version → same identity key."""
    k1 = identity_digest(
        input_digest=_ID_DIGEST,
        producer_id=_PRODUCER_ID,
        producer_version=_PRODUCER_VERSION,
    )
    k2 = identity_digest(
        input_digest=_ID_DIGEST,
        producer_id=_PRODUCER_ID,
        producer_version=_PRODUCER_VERSION,
    )
    assert k1 == k2
    assert len(k1) == 64


def test_identity_digest_busts_on_input_digest_change() -> None:
    """Different input digest → different identity key."""
    k1 = identity_digest(input_digest="a" * 64, producer_id="step-1", producer_version="v1")
    k2 = identity_digest(input_digest="b" * 64, producer_id="step-1", producer_version="v1")
    assert k1 != k2


def test_identity_digest_busts_on_producer_id_change() -> None:
    """Different producer_id → different identity key."""
    k1 = identity_digest(input_digest=_ID_DIGEST, producer_id="step-1", producer_version="v1")
    k2 = identity_digest(input_digest=_ID_DIGEST, producer_id="step-2", producer_version="v1")
    assert k1 != k2


def test_identity_digest_busts_on_producer_version_change() -> None:
    """Different producer_version → different identity key."""
    k1 = identity_digest(input_digest=_ID_DIGEST, producer_id="step-1", producer_version="v1.0.0")
    k2 = identity_digest(input_digest=_ID_DIGEST, producer_id="step-1", producer_version="v1.0.1")
    assert k1 != k2


def test_identity_digest_all_three_components_change() -> None:
    """Changing all three components → different key (obviously)."""
    k1 = identity_digest(input_digest="a" * 64, producer_id="step-a", producer_version="v1")
    k2 = identity_digest(input_digest="b" * 64, producer_id="step-b", producer_version="v2")
    assert k1 != k2


def test_identity_digest_deterministic_payload_format() -> None:
    """The identity digest is sha256(input:producer_id:producer_version)."""
    expected = _sha256(f"{_ID_DIGEST}:{_PRODUCER_ID}:{_PRODUCER_VERSION}".encode("utf-8"))
    actual = identity_digest(
        input_digest=_ID_DIGEST,
        producer_id=_PRODUCER_ID,
        producer_version=_PRODUCER_VERSION,
    )
    assert actual == expected


# ═══════════════════════════════════════════════════════════════════════════
# link_identity_artifact
# ═══════════════════════════════════════════════════════════════════════════

def test_link_identity_artifact_creates_cas_entry(tmp_path: Path) -> None:
    """link_identity_artifact stores the source under .cas/<identity_key>."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    src = project_dir / "artifact.bin"
    payload = b"identity-linked content"
    src.write_bytes(payload)

    identity_key = _sha256(b"deterministic-key-1")
    result = link_identity_artifact(project_dir, src, identity_key)

    expected = project_dir / ".cas" / identity_key
    assert result == expected
    assert expected.exists()
    assert expected.read_bytes() == payload
    assert not src.exists()  # source was moved, not copied


def test_link_identity_artifact_idempotent_discards_duplicate_source(tmp_path: Path) -> None:
    """Second link with same identity key returns existing entry, discards source."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    payload = b"shared identity content"

    identity_key = _sha256(b"deterministic-key-2")

    a = project_dir / "a.bin"
    b = project_dir / "b.bin"
    a.write_bytes(payload)
    b.write_bytes(payload)

    first = link_identity_artifact(project_dir, a, identity_key)
    second = link_identity_artifact(project_dir, b, identity_key)

    assert first == second
    assert not b.exists()  # duplicate source discarded
    entries = list((project_dir / ".cas").iterdir())
    assert len(entries) == 1
    assert entries[0] == first
    assert entries[0].read_bytes() == payload


def test_link_identity_artifact_different_keys_create_different_entries(tmp_path: Path) -> None:
    """Different identity keys create distinct CAS entries."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    key1 = _sha256(b"key-1")
    key2 = _sha256(b"key-2")

    a = project_dir / "a.bin"
    b = project_dir / "b.bin"
    a.write_bytes(b"alpha")
    b.write_bytes(b"beta")

    first = link_identity_artifact(project_dir, a, key1)
    second = link_identity_artifact(project_dir, b, key2)

    assert first != second
    entries = sorted(p.name for p in (project_dir / ".cas").iterdir())
    assert len(entries) == 2
    assert sorted([first.name, second.name]) == entries
    assert first.read_bytes() == b"alpha"
    assert second.read_bytes() == b"beta"


def test_link_identity_artifact_never_hashes_bytes(tmp_path: Path) -> None:
    """link_identity_artifact must NOT call hash_file or read the source
    bytes for hashing purposes — it only uses the pre-computed identity_key."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    src = project_dir / "data.bin"
    src.write_bytes(b"these bytes should never be hashed by link_identity_artifact")

    identity_key = _sha256(b"pre-computed-key")

    # Prove that hash_file is NOT called during link_identity_artifact.
    with patch("astrid.core.io.cas.hash_file") as mock_hash:
        link_identity_artifact(project_dir, src, identity_key)
        mock_hash.assert_not_called()


def test_link_identity_artifact_does_not_read_source_for_digest(tmp_path: Path) -> None:
    """Even if we monitor all hashlib.sha256 calls, the source bytes are
    never fed into a hash during link_identity_artifact."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    src = project_dir / "data.bin"
    src.write_bytes(b"should-not-be-hashed")

    identity_key = _sha256(b"pre-computed-key-2")

    # Patch hashlib.sha256 to detect any new hashing of bytes.
    with patch("hashlib.sha256", wraps=hashlib.sha256) as mock_sha:
        link_identity_artifact(project_dir, src, identity_key)
        # link_identity_artifact only does Path operations (mkdir/exists/unlink/replace).
        # hashlib.sha256 should not be called.
        mock_sha.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# Separation: byte-content CAS vs identity-keyed reuse
# ═══════════════════════════════════════════════════════════════════════════

def test_identity_reuse_when_bytes_differ_but_inputs_identical(tmp_path: Path) -> None:
    """Two artifacts with different bytes but identical identity inputs get
    the same identity key — proving identity CAS is about logical identity,
    not byte content.  Meanwhile, byte-content CAS (intern) gives different
    keys for the same files."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    payload_a = b"logically same artifact -- version A"
    payload_b = b"logically same artifact -- version B"

    # Byte-content CAS: different bytes → different keys.
    a_file = project_dir / "a.bin"
    b_file = project_dir / "b.bin"
    a_file.write_bytes(payload_a)
    b_file.write_bytes(payload_b)

    byte_key_a = intern(project_dir, a_file)
    # Recreate a_file since intern moved it.
    a_file = project_dir / "a.bin"
    a_file.write_bytes(payload_a)
    byte_key_b = intern(project_dir, b_file)

    assert byte_key_a != byte_key_b  # Different byte content → different keys

    # Identity CAS: same logical inputs → same key regardless of bytes.
    input_dig = input_reference_digest(["step_x.produces.result"])
    producer_id = "step-y"
    producer_version = "v1.0.0"
    identity_key = identity_digest(
        input_digest=input_dig,
        producer_id=producer_id,
        producer_version=producer_version,
    )

    # Link two different byte payloads under the same identity key.
    src1 = project_dir / "src1.bin"
    src2 = project_dir / "src2.bin"
    src1.write_bytes(payload_a)
    src2.write_bytes(payload_b)

    result1 = link_identity_artifact(project_dir, src1, identity_key)
    # First link moves src1 into CAS.
    assert result1.name == identity_key
    assert result1.read_bytes() == payload_a

    result2 = link_identity_artifact(project_dir, src2, identity_key)
    # Second link with same identity key returns the existing entry,
    # discarding src2 — the identity key is reused.
    assert result2 == result1
    assert not src2.exists()
    # The CAS still holds the first payload (identity-keyed, not byte-keyed).
    assert result1.read_bytes() == payload_a


def test_identity_key_changes_when_input_refs_differ(tmp_path: Path) -> None:
    """Different input refs → different identity key → different CAS entry."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    payload = b"artifact"

    input_dig_a = input_reference_digest(["step_a.produces.x"])
    input_dig_b = input_reference_digest(["step_b.produces.x"])
    producer_id = "step-c"
    producer_version = "v1"

    key_a = identity_digest(input_digest=input_dig_a, producer_id=producer_id, producer_version=producer_version)
    key_b = identity_digest(input_digest=input_dig_b, producer_id=producer_id, producer_version=producer_version)
    assert key_a != key_b

    src_a = project_dir / "a.bin"
    src_b = project_dir / "b.bin"
    src_a.write_bytes(payload)
    src_b.write_bytes(payload)

    result_a = link_identity_artifact(project_dir, src_a, key_a)
    result_b = link_identity_artifact(project_dir, src_b, key_b)

    assert result_a != result_b
    assert result_a.name == key_a
    assert result_b.name == key_b


def test_identity_key_changes_when_producer_id_differs(tmp_path: Path) -> None:
    """Same inputs, different producer_id → different identity key."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    payload = b"artifact"

    input_dig = input_reference_digest(["step_x.produces.out"])
    key_a = identity_digest(input_digest=input_dig, producer_id="producer-a", producer_version="v1")
    key_b = identity_digest(input_digest=input_dig, producer_id="producer-b", producer_version="v1")
    assert key_a != key_b

    src_a = project_dir / "a.bin"
    src_b = project_dir / "b.bin"
    src_a.write_bytes(payload)
    src_b.write_bytes(payload)

    result_a = link_identity_artifact(project_dir, src_a, key_a)
    result_b = link_identity_artifact(project_dir, src_b, key_b)

    assert result_a != result_b


def test_identity_key_changes_when_producer_version_differs(tmp_path: Path) -> None:
    """Same inputs, same producer_id, different producer_version → different identity key."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    payload = b"artifact"

    input_dig = input_reference_digest(["step_x.produces.out"])
    key_a = identity_digest(input_digest=input_dig, producer_id="step-p", producer_version="v1.0.0")
    key_b = identity_digest(input_digest=input_dig, producer_id="step-p", producer_version="v2.0.0")
    assert key_a != key_b

    src_a = project_dir / "a.bin"
    src_b = project_dir / "b.bin"
    src_a.write_bytes(payload)
    src_b.write_bytes(payload)

    result_a = link_identity_artifact(project_dir, src_a, key_a)
    result_b = link_identity_artifact(project_dir, src_b, key_b)

    assert result_a != result_b


def test_legacy_hash_file_unaffected_by_identity_additions(tmp_path: Path) -> None:
    """hash_file still computes a byte-content sha256 of the file."""
    p = tmp_path / "data.bin"
    p.write_bytes(b"legacy hash test")
    expected = _sha256(b"legacy hash test")
    assert hash_file(p) == expected


def test_legacy_intern_unaffected_by_identity_additions(tmp_path: Path) -> None:
    """intern still uses byte-content hash to determine CAS path."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    src = project_dir / "data.bin"
    payload = b"legacy intern test"
    src.write_bytes(payload)

    result = intern(project_dir, src)
    expected_key = _sha256(payload)
    assert result.name == expected_key
    assert result.read_bytes() == payload


def test_identity_link_and_byte_intern_produce_different_keys(tmp_path: Path) -> None:
    """For the same artifact bytes, intern (byte-content) and
    link_identity_artifact (identity-keyed) store under different keys."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    payload = b"same bytes, different keys"

    # Byte-content intern
    src1 = project_dir / "src1.bin"
    src1.write_bytes(payload)
    byte_result = intern(project_dir, src1)
    byte_key = byte_result.name

    # Identity link
    src2 = project_dir / "src2.bin"
    src2.write_bytes(payload)
    identity_key = identity_digest(
        input_digest=input_reference_digest(["step.produces.out"]),
        producer_id="step-p",
        producer_version="v1",
    )
    identity_result = link_identity_artifact(project_dir, src2, identity_key)

    # The two keys must be different — identity key is NOT a byte hash.
    assert byte_key != identity_key
    # But the content is identical.
    assert byte_result.read_bytes() == payload
    assert identity_result.read_bytes() == payload


# ═══════════════════════════════════════════════════════════════════════════
# Full end-to-end: identity_key reuse on identical inputs
# ═══════════════════════════════════════════════════════════════════════════

def test_full_identity_pipeline_stable_reuse(tmp_path: Path) -> None:
    """Simulate a full identity CAS pipeline: same logical step with same
    inputs, producer, and version always produces the same identity key."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    # Build identity inputs.
    input_dig = input_reference_digest(["step_a.produces.result", "step_b.produces.config"])
    producer_id = "step-c"
    producer_version = "v3.2.1"
    identity_key = identity_digest(
        input_digest=input_dig,
        producer_id=producer_id,
        producer_version=producer_version,
    )

    # "Run" the step three times with identical logical inputs.
    keys_seen = []
    for i in range(3):
        src = project_dir / f"run_{i}.bin"
        src.write_bytes(b"artifact payload")
        result = link_identity_artifact(project_dir, src, identity_key)
        keys_seen.append(result.name)

    # All three runs use the same identity key.
    assert all(k == identity_key for k in keys_seen)
    # Only one CAS entry exists.
    entries = list((project_dir / ".cas").iterdir())
    assert len(entries) == 1
    assert entries[0].name == identity_key


def test_full_identity_pipeline_busts_on_input_change(tmp_path: Path) -> None:
    """Changing input refs between runs produces different identity keys."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    producer_id = "step-x"
    producer_version = "v1"

    id_a = identity_digest(
        input_digest=input_reference_digest(["step_a.produces.x"]),
        producer_id=producer_id,
        producer_version=producer_version,
    )
    id_b = identity_digest(
        input_digest=input_reference_digest(["step_b.produces.x"]),
        producer_id=producer_id,
        producer_version=producer_version,
    )
    assert id_a != id_b

    src_a = project_dir / "a.bin"
    src_b = project_dir / "b.bin"
    src_a.write_bytes(b"payload")
    src_b.write_bytes(b"payload")

    ra = link_identity_artifact(project_dir, src_a, id_a)
    rb = link_identity_artifact(project_dir, src_b, id_b)
    assert ra != rb
    assert len(list((project_dir / ".cas").iterdir())) == 2
