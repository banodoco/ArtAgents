"""Media pipeline tests: preparation, identity, walking, and frozen paths (m2 plan step 2).

T2 scope (this file's first section) proves the immutable prepared-media
contract before any repository or publication exists:

- byte identity is path-independent: identical bytes at different paths
  resolve to the same lowercase digest and the same exact shard, while
  changed bytes at one path change the digest;
- empty files digest to the standard empty-input SHA-256 and prepare with
  ``byte_size`` 0;
- directory walking is deterministic (sorted depth-first, symlinks and the
  managed root skipped) and independent of creation order;
- MIME type, media kind, and probe metadata are derived independently;
- media kind validation is strict against the frozen seven-value
  vocabulary;
- managed and staging paths reproduce the frozen decision-artifact layout
  exactly, including the two-pair sharding, and malformed digests/txn ids
  are rejected.

Later plan steps (T3/T4) extend this module with staging, publication,
verification, GC, and composition-root coverage.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from astrid.core.events.registry import core_only_registry
from astrid.core.io.media_import import (
    MANAGED_ROOT_DIRNAME,
    MEDIA_KINDS,
    MEDIA_LOCATION_REALMS,
    PreparedMedia,
    PublishedMedia,
    StagedMedia,
    StagingGcResult,
    MediaDigestError,
    MediaIntegrityError,
    MediaKindError,
    MediaLocationError,
    MediaPathError,
    MediaPreparationError,
    MediaPublicationError,
    MediaStagingError,
    derive_media_kind,
    derive_mime_type,
    gc_unreferenced_staging,
    managed_media_path,
    managed_root,
    managed_shard_path,
    prepare_external_local,
    prepare_media_directory,
    prepare_media_file,
    probe_media_file,
    publish_prepared_media,
    publish_staged_media,
    sha256_file_bytes,
    stage_prepared_media,
    staging_path,
    validate_digest,
    validate_media_kind,
    validate_txn_id,
    verify_managed_bytes,
    verify_media_bytes,
    verify_staged_media,
    walk_media_files,
)

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
HELLO_SHA256 = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def _write(root: Path, rel: str, data: bytes) -> Path:
    """Write *data* to ``root / rel`` (creating parents) and return the path."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# ---------------------------------------------------------------------------
# Byte identity: path-independent, lowercase, changed-bytes sensitive
# ---------------------------------------------------------------------------


def test_sha256_file_bytes_is_lowercase_hex(tmp_path: Path) -> None:
    path = _write(tmp_path, "hello.txt", b"hello")
    digest = sha256_file_bytes(path)
    # Known vector: sha256(b"hello").
    assert digest == HELLO_SHA256
    assert digest.islower() and len(digest) == 64
    assert HELLO_SHA256 == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_identical_bytes_at_different_paths_have_same_identity(tmp_path: Path) -> None:
    first = _write(tmp_path, "a/one.bin", b"same bytes")
    second = _write(tmp_path, "b/two/nested.bin", b"same bytes")
    digest_a = sha256_file_bytes(first)
    digest_b = sha256_file_bytes(second)
    assert digest_a == digest_b
    prepared_a = prepare_media_file(first, root=tmp_path)
    prepared_b = prepare_media_file(second, root=tmp_path)
    assert prepared_a.digest == prepared_b.digest
    # The exact shard path depends only on the digest, never the path.
    assert managed_media_path(tmp_path, prepared_a.digest) == managed_media_path(
        tmp_path, prepared_b.digest
    )
    # rel_path still records each distinct location.
    assert prepared_a.rel_path == "a/one.bin"
    assert prepared_b.rel_path == "b/two/nested.bin"


def test_changed_bytes_at_one_path_change_identity(tmp_path: Path) -> None:
    path = _write(tmp_path, "clip.bin", b"original")
    before = prepare_media_file(path)
    path.write_bytes(b"mutated!")
    after = prepare_media_file(path)
    assert before.digest != after.digest
    assert before.byte_size == 8
    assert after.byte_size == 8
    assert managed_media_path(tmp_path, before.digest) != managed_media_path(
        tmp_path, after.digest
    )


def test_empty_file_has_standard_empty_digest_and_zero_size(tmp_path: Path) -> None:
    path = _write(tmp_path, "empty.txt", b"")
    digest = sha256_file_bytes(path)
    assert digest == EMPTY_SHA256
    prepared = prepare_media_file(path)
    assert prepared.byte_size == 0
    assert prepared.digest == EMPTY_SHA256
    assert prepared.probe["is_empty"] is True
    assert managed_media_path(tmp_path, digest).name == digest


# ---------------------------------------------------------------------------
# Deterministic walking
# ---------------------------------------------------------------------------


def test_walk_order_is_deterministic_and_sorted(tmp_path: Path) -> None:
    # Create entries in scrambled order and with interleaved dirs/files.
    _write(tmp_path, "zeta.txt", b"z")
    _write(tmp_path, "alpha.txt", b"a")
    _write(tmp_path, "sub/beta.txt", b"b")
    _write(tmp_path, "sub/deep/gamma.txt", b"g")
    _write(tmp_path, "mid/delta.txt", b"d")
    first = [p.name for p in walk_media_files(tmp_path)]
    # Scramble by recreating under a fresh root with different creation order.
    other = tmp_path / "other"
    _write(other, "mid/delta.txt", b"d")
    _write(other, "sub/deep/gamma.txt", b"g")
    _write(other, "sub/beta.txt", b"b")
    _write(other, "alpha.txt", b"a")
    _write(other, "zeta.txt", b"z")
    second = [p.name for p in walk_media_files(other)]
    # Same depth-first sorted order: own files first (sorted), then subdirs.
    assert first == ["alpha.txt", "zeta.txt", "delta.txt", "beta.txt", "gamma.txt"]
    assert second == first


def test_walk_skips_symlinks_and_non_regular_files(tmp_path: Path) -> None:
    _write(tmp_path, "real.txt", b"real")
    os.symlink(tmp_path / "real.txt", tmp_path / "link.txt")
    os.symlink(tmp_path, tmp_path / "dirlink")
    (tmp_path / "fifo").mkdir(parents=True, exist_ok=True)  # a directory
    names = [p.name for p in walk_media_files(tmp_path)]
    assert names == ["real.txt"]


def test_walk_skips_managed_root(tmp_path: Path) -> None:
    _write(tmp_path, ".astrid/media/.staging/abc/secret.bin", b"staged")
    _write(tmp_path, "visible.txt", b"ok")
    names = [p.name for p in walk_media_files(tmp_path)]
    assert names == ["visible.txt"]


def test_walk_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(MediaPathError):
        walk_media_files(tmp_path / "nope")


def test_prepare_media_directory_returns_walk_order(tmp_path: Path) -> None:
    _write(tmp_path, "b.txt", b"bb")
    _write(tmp_path, "a.txt", b"aa")
    _write(tmp_path, "sub/c.txt", b"cc")
    prepared = prepare_media_directory(tmp_path)
    assert [p.rel_path for p in prepared] == ["a.txt", "b.txt", "sub/c.txt"]
    assert all(isinstance(p, PreparedMedia) for p in prepared)
    assert [p.digest for p in prepared] == [
        sha256_file_bytes(tmp_path / "a.txt"),
        sha256_file_bytes(tmp_path / "b.txt"),
        sha256_file_bytes(tmp_path / "sub/c.txt"),
    ]


# ---------------------------------------------------------------------------
# Independent kind / MIME / probe derivation
# ---------------------------------------------------------------------------


def test_kind_mime_probe_are_derived_independently(tmp_path: Path) -> None:
    path = _write(tmp_path, "shot.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    prepared = prepare_media_file(path)
    assert prepared.mime_type == "image/png"
    assert prepared.media_kind == "image"
    assert prepared.probe["extension"] == ".png"
    assert prepared.probe["byte_size"] == 24
    # Independent: kind is a pure function of the MIME string, and the probe
    # is a pure function of the file — none reads another's output.
    assert derive_media_kind("image/png") == "image"
    assert derive_media_kind(prepared.mime_type) == prepared.media_kind
    assert probe_media_file(path)["byte_size"] == 24


def test_kind_classification_across_mime_families() -> None:
    cases = {
        "image/jpeg": "image",
        "video/mp4": "video",
        "audio/mpeg": "audio",
        "text/plain": "text",
        "application/pdf": "document",
        "application/json": "data",
        "application/octet-stream": "other",
    }
    for mime, expected in cases.items():
        assert derive_media_kind(mime) == expected, mime


def test_mime_fallback_for_common_extensions(tmp_path: Path) -> None:
    assert derive_mime_type("notes.md") == "text/markdown"
    assert derive_mime_type("data.yaml") == "application/x-yaml"
    assert derive_mime_type("unknown.zzz") == "application/octet-stream"
    prepared = prepare_media_file(_write(tmp_path, "notes.md", b"# hi"))
    assert prepared.media_kind == "text"
    assert prepared.mime_type == "text/markdown"


# ---------------------------------------------------------------------------
# Strict media-kind validation
# ---------------------------------------------------------------------------


def test_validate_media_kind_accepts_frozen_seven() -> None:
    assert MEDIA_KINDS == (
        "image",
        "video",
        "audio",
        "text",
        "document",
        "data",
        "other",
    )
    for kind in MEDIA_KINDS:
        assert validate_media_kind(kind) == kind


def test_validate_media_kind_rejects_non_frozen_values() -> None:
    for bad in ("movie", "IMAGE", "image/png", "", "other ", 7, None):
        with pytest.raises(MediaKindError):
            validate_media_kind(bad)


def test_prepared_record_rejects_invalid_kind(tmp_path: Path) -> None:
    path = _write(tmp_path, "x.bin", b"x")
    with pytest.raises(MediaKindError):
        PreparedMedia(
            source_path=path,
            digest=sha256_file_bytes(path),
            byte_size=1,
            media_kind="movie",
            mime_type="application/octet-stream",
            rel_path="x.bin",
        )


# ---------------------------------------------------------------------------
# Exact frozen managed and staging paths (sharding)
# ---------------------------------------------------------------------------


def test_managed_media_path_exact_sharded_layout(tmp_path: Path) -> None:
    digest = HELLO_SHA256  # 2cf2 4dba ...
    path = managed_media_path(tmp_path, digest)
    assert path == (
        tmp_path
        / MANAGED_ROOT_DIRNAME
        / "media"
        / "sha256"
        / "2c"
        / "f2"
        / digest
    )
    assert managed_shard_path(tmp_path, digest) == path.parent
    assert managed_root(tmp_path) == tmp_path / MANAGED_ROOT_DIRNAME


def test_shard_path_depends_only_on_digest_prefix(tmp_path: Path) -> None:
    digest = "a" * 64
    path = managed_media_path(tmp_path, digest)
    assert path.parent.name == "aa"
    assert path.parent.parent.name == "aa"
    assert path.name == digest


def test_staging_path_exact_frozen_layout(tmp_path: Path) -> None:
    txn = "ab" * 16
    path = staging_path(tmp_path, txn)
    assert path == tmp_path / MANAGED_ROOT_DIRNAME / "media" / ".staging" / txn


def test_digest_validation_rejects_malformed_values(tmp_path: Path) -> None:
    for bad in ("", "ABC", "a" * 63, "A" * 64, "z" * 64, 123, None):
        with pytest.raises(MediaDigestError):
            validate_digest(bad)
        with pytest.raises(MediaDigestError):
            managed_media_path(tmp_path, bad)


def test_txn_id_validation_rejects_escaping_values(tmp_path: Path) -> None:
    for bad in ("", "../escape", "a" * 31, "AB" * 16, "a" * 32 + "/x", None):
        with pytest.raises(MediaPreparationError):
            validate_txn_id(bad)
        with pytest.raises(MediaPreparationError):
            staging_path(tmp_path, bad)


def test_prepare_media_file_rejects_missing_or_symlinked_paths(
    tmp_path: Path,
) -> None:
    with pytest.raises(MediaPathError):
        prepare_media_file(tmp_path / "missing.bin")
    target = _write(tmp_path, "real.bin", b"x")
    os.symlink(target, tmp_path / "link.bin")
    with pytest.raises(MediaPathError):
        prepare_media_file(tmp_path / "link.bin")


def test_prepare_media_file_rel_path_outside_root_rejected(tmp_path: Path) -> None:
    outside = _write(tmp_path, "outside.bin", b"x")
    with pytest.raises(MediaPathError):
        prepare_media_file(outside, root=tmp_path / "sub")


# ---------------------------------------------------------------------------
# Per-transaction staging, verified publication, and location verification
# (m2 plan step 3 / T3)
# ---------------------------------------------------------------------------

TXN_A = "ab" * 16
TXN_B = "cd" * 16
TXN_C = "ef" * 16


def _txn_staging_root(projects_root: Path, txn: str) -> Path:
    return staging_path(projects_root, txn)


# -- staging ---------------------------------------------------------------


def test_stage_creates_per_transaction_quarantine(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/shot.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    prepared = prepare_media_file(source, root=tmp_path / "in")
    staged = stage_prepared_media(tmp_path, TXN_A, prepared)
    assert isinstance(staged, StagedMedia)
    assert staged.txn_id == TXN_A
    assert staged.rel_path == "shot.png"
    assert staged.digest == prepared.digest
    assert staged.byte_size == prepared.byte_size
    expected = _txn_staging_root(tmp_path, TXN_A) / "shot.png"
    assert staged.staged_path == expected
    # Quarantine holds an exact byte copy of the prepared source.
    assert staged.staged_path.read_bytes() == source.read_bytes()
    assert sha256_file_bytes(staged.staged_path) == prepared.digest


def test_stage_preserves_nested_rel_paths(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/sub/deep/clip.bin", b"clip bytes")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    staged = stage_prepared_media(tmp_path, TXN_A, prepared)
    assert staged.staged_path == _txn_staging_root(tmp_path, TXN_A) / "sub/deep/clip.bin"
    assert staged.staged_path.is_file()


def test_stage_rejects_escaping_rel_path(tmp_path: Path) -> None:
    source = _write(tmp_path, "ok.bin", b"x")
    prepared = prepare_media_file(source)
    # A rel_path that would climb out of the staging tree is rejected even
    # though the source itself is fine: staging must stay quarantined.
    forged = PreparedMedia(
        source_path=source,
        digest=prepared.digest,
        byte_size=1,
        media_kind=prepared.media_kind,
        mime_type=prepared.mime_type,
        rel_path="../escape.bin",
    )
    with pytest.raises(MediaStagingError):
        stage_prepared_media(tmp_path, TXN_A, forged)


def test_stage_rejects_malformed_txn_id(tmp_path: Path) -> None:
    source = _write(tmp_path, "ok.bin", b"x")
    prepared = prepare_media_file(source)
    for bad in ("", "../escape", "AB" * 16, "a" * 31):
        with pytest.raises(MediaPreparationError):
            stage_prepared_media(tmp_path, bad, prepared)


# -- staged-byte verification ----------------------------------------------


def test_verify_staged_media_confirms_untouched_bytes(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/a.bin", b"verified bytes")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    staged = stage_prepared_media(tmp_path, TXN_A, prepared)
    assert verify_staged_media(staged) is staged


def test_verify_staged_media_rejects_tampered_bytes(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/a.bin", b"original bytes")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    staged = stage_prepared_media(tmp_path, TXN_A, prepared)
    staged.staged_path.write_bytes(b"tampered bytes")
    with pytest.raises(MediaIntegrityError):
        verify_staged_media(staged)


def test_verify_staged_media_rejects_missing_staged_file(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/a.bin", b"x")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    staged = stage_prepared_media(tmp_path, TXN_A, prepared)
    staged.staged_path.unlink()
    with pytest.raises(MediaIntegrityError):
        verify_staged_media(staged)


# -- atomic publication and verified reuse ---------------------------------


def test_publish_renames_atomically_into_exact_managed_path(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/clip.bin", b"publish me")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    published = publish_prepared_media(tmp_path, TXN_A, prepared)
    assert isinstance(published, PublishedMedia)
    assert published.reused is False
    assert published.digest == prepared.digest
    assert published.byte_size == prepared.byte_size
    assert published.managed_path == managed_media_path(tmp_path, prepared.digest)
    # Bytes landed at the exact frozen sharded path and the staging
    # quarantine is drained.
    assert published.managed_path.read_bytes() == b"publish me"
    assert not (staging_path(tmp_path, TXN_A) / "clip.bin").exists()
    # The shard directory tree exists and is exactly <first2>/<next2>.
    assert published.managed_path.parent.name == prepared.digest[2:4]
    assert published.managed_path.parent.parent.name == prepared.digest[:2]


def test_publish_verifies_staged_bytes_before_publication(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/a.bin", b"clean bytes")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    staged = stage_prepared_media(tmp_path, TXN_A, prepared)
    staged.staged_path.write_bytes(b"dirty bytes")
    with pytest.raises(MediaIntegrityError):
        publish_staged_media(tmp_path, staged)
    # Nothing was published and the quarantine still holds the dirty copy.
    assert not managed_media_path(tmp_path, prepared.digest).exists()
    assert staged.staged_path.exists()


def test_publish_reuses_existing_verified_digest(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/a.bin", b"dedupe me")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    first = publish_prepared_media(tmp_path, TXN_A, prepared)
    assert first.reused is False
    # Second import of identical bytes from a different path: no copy.
    second_source = _write(tmp_path, "elsewhere/b.bin", b"dedupe me")
    second_prepared = prepare_media_file(second_source, root=tmp_path / "elsewhere")
    second = publish_prepared_media(tmp_path, TXN_B, second_prepared)
    assert second.reused is True
    assert second.managed_path == first.managed_path
    assert second.managed_path.read_bytes() == b"dedupe me"
    # The redundant staging copy was drained.
    assert not (staging_path(tmp_path, TXN_B) / "b.bin").exists()


def test_publish_rejects_mutated_existing_digest(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/a.bin", b"original")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    publish_prepared_media(tmp_path, TXN_A, prepared)
    # Corrupt the managed digest file directly (simulating disk mutation).
    managed = managed_media_path(tmp_path, prepared.digest)
    managed.write_bytes(b"mutated!")
    with pytest.raises(MediaLocationError) as excinfo:
        publish_prepared_media(tmp_path, TXN_B, prepare_media_file(source, root=tmp_path / "in"))
    assert excinfo.value.reason == "mutated"
    # The corrupted digest is never silently overwritten; the staging copy
    # stays quarantined for GC to handle.
    assert managed.read_bytes() == b"mutated!"
    assert (staging_path(tmp_path, TXN_B) / "a.bin").exists()


def test_publish_prepared_media_validates_records(tmp_path: Path) -> None:
    source = _write(tmp_path, "a.bin", b"x")
    with pytest.raises(MediaPreparationError):
        publish_prepared_media(tmp_path, TXN_A, source)  # not a PreparedMedia


# -- explicit external_local preparation -----------------------------------


def test_external_local_preparation_is_explicit_and_byte_identical(tmp_path: Path) -> None:
    path = _write(tmp_path, "ext/shot.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    external = prepare_external_local(path, root=tmp_path / "ext")
    assert isinstance(external, PreparedMedia)
    assert external.digest == prepare_media_file(path, root=tmp_path / "ext").digest
    assert external.rel_path == "shot.png"
    assert external.media_kind == "image"
    # The realm vocabulary records the explicit opt-in: external_local is a
    # named realm, never the default (managed_local comes first).
    assert MEDIA_LOCATION_REALMS == ("managed_local", "external_local", "remote")


def test_external_local_rejects_missing_and_symlinked_paths(tmp_path: Path) -> None:
    with pytest.raises(MediaPathError):
        prepare_external_local(tmp_path / "missing.bin")
    target = _write(tmp_path, "real.bin", b"x")
    os.symlink(target, tmp_path / "link.bin")
    with pytest.raises(MediaPathError):
        prepare_external_local(tmp_path / "link.bin")


# -- missing/mutated location verification ---------------------------------


def test_verify_media_bytes_detects_missing_and_mutated(tmp_path: Path) -> None:
    path = _write(tmp_path, "loc.bin", b"location bytes")
    digest = sha256_file_bytes(path)
    assert verify_media_bytes(path, digest) == 14
    with pytest.raises(MediaLocationError) as missing:
        verify_media_bytes(tmp_path / "nope.bin", digest)
    assert missing.value.reason == "missing"
    path.write_bytes(b"mutated bytes!")
    with pytest.raises(MediaLocationError) as mutated:
        verify_media_bytes(path, digest)
    assert mutated.value.reason == "mutated"
    assert mutated.value.expected_digest == digest
    assert mutated.value.actual_digest == sha256_file_bytes(path)


def test_verify_media_bytes_treats_symlink_as_missing(tmp_path: Path) -> None:
    target = _write(tmp_path, "target.bin", b"x")
    os.symlink(target, tmp_path / "link.bin")
    with pytest.raises(MediaLocationError) as excinfo:
        verify_media_bytes(tmp_path / "link.bin", sha256_file_bytes(target))
    assert excinfo.value.reason == "missing"


def test_verify_managed_bytes_covers_published_digests(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/a.bin", b"managed bytes")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    publish_prepared_media(tmp_path, TXN_A, prepared)
    assert verify_managed_bytes(tmp_path, prepared.digest) == 13
    with pytest.raises(MediaLocationError) as missing:
        verify_managed_bytes(tmp_path, "f" * 64)
    assert missing.value.reason == "missing"
    managed_media_path(tmp_path, prepared.digest).write_bytes(b"mutated!")
    with pytest.raises(MediaLocationError) as mutated:
        verify_managed_bytes(tmp_path, prepared.digest)
    assert mutated.value.reason == "mutated"


# -- selective staging GC --------------------------------------------------


def _stage_dir(projects_root: Path, txn: str, rel: str, data: bytes) -> Path:
    prepared = prepare_media_file(_write(projects_root / "src", rel, data), root=projects_root / "src")
    staged = stage_prepared_media(projects_root, txn, prepared)
    return staged.staged_path.parent


def test_gc_removes_only_unreferenced_staging_directories(tmp_path: Path) -> None:
    live = _stage_dir(tmp_path, TXN_A, "live.bin", b"live")
    unreferenced_b = _stage_dir(tmp_path, TXN_B, "dead.bin", b"dead")
    unreferenced_c = _stage_dir(tmp_path, TXN_C, "sub/old.bin", b"old")
    # A published managed digest must survive GC untouched.
    published = publish_prepared_media(tmp_path, TXN_A, prepare_media_file(tmp_path / "src" / "live.bin", root=tmp_path / "src"))
    managed_before = set(p for p in (tmp_path / ".astrid" / "media" / "sha256").rglob("*") if p.is_file())

    result = gc_unreferenced_staging(tmp_path, live_txn_ids={TXN_A})
    assert isinstance(result, StagingGcResult)
    assert result.removed_directories == 2
    assert result.removed_files == 2
    assert result.remaining_directories == 1
    # Live staging kept; unreferenced staging gone.
    assert live.exists()
    assert not unreferenced_b.exists()
    assert not unreferenced_c.exists()
    # The managed digest tree is byte-for-byte untouched.
    managed_after = set(p for p in (tmp_path / ".astrid" / "media" / "sha256").rglob("*") if p.is_file())
    assert managed_after == managed_before
    assert published.managed_path.read_bytes() == b"live"


def test_gc_with_empty_live_set_removes_every_staging_dir(tmp_path: Path) -> None:
    _stage_dir(tmp_path, TXN_A, "a.bin", b"a")
    _stage_dir(tmp_path, TXN_B, "b.bin", b"b")
    result = gc_unreferenced_staging(tmp_path, live_txn_ids=set())
    assert result.removed_directories == 2
    assert result.remaining_directories == 0
    assert not staging_path(tmp_path, TXN_A).exists()
    assert not staging_path(tmp_path, TXN_B).exists()


def test_gc_skips_foreign_and_malformed_entries(tmp_path: Path) -> None:
    _stage_dir(tmp_path, TXN_A, "a.bin", b"a")
    staging_root = staging_path(tmp_path, TXN_A).parent
    foreign_dir = staging_root / "not-a-txn"
    foreign_dir.mkdir(parents=True, exist_ok=True)
    (foreign_dir / "keep.bin").write_bytes(b"keep")
    stray_file = staging_root / "stray.txt"
    stray_file.write_bytes(b"stray")
    result = gc_unreferenced_staging(tmp_path, live_txn_ids=set())
    # Only the valid txn staging dir is removed; foreign entries are never
    # deleted by GC (they are not staging directories by the frozen grammar).
    assert result.removed_directories == 1
    assert foreign_dir.exists()
    assert stray_file.exists()


def test_gc_removes_unreferenced_dirs_with_nested_files(tmp_path: Path) -> None:
    _stage_dir(tmp_path, TXN_A, "sub/deep/a.bin", b"a")
    _stage_dir(tmp_path, TXN_A, "sub/b.bin", b"b")
    result = gc_unreferenced_staging(tmp_path, live_txn_ids=set())
    assert result.removed_directories == 1
    assert result.removed_files == 2
    assert not staging_path(tmp_path, TXN_A).exists()


def test_gc_is_noop_without_staging_root(tmp_path: Path) -> None:
    result = gc_unreferenced_staging(tmp_path, live_txn_ids=set())
    assert result.removed_directories == 0
    assert result.remaining_directories == 0


def test_gc_rejects_malformed_live_txn_ids(tmp_path: Path) -> None:
    _stage_dir(tmp_path, TXN_A, "a.bin", b"a")
    with pytest.raises(MediaPreparationError):
        gc_unreferenced_staging(tmp_path, live_txn_ids={"../escape"})


def test_staged_and_published_records_roundtrip(tmp_path: Path) -> None:
    source = _write(tmp_path, "in/a.bin", b"round trip")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    staged = stage_prepared_media(tmp_path, TXN_A, prepared)
    assert StagedMedia(
        txn_id=staged.txn_id,
        staged_path=staged.staged_path,
        rel_path=staged.rel_path,
        digest=staged.digest,
        byte_size=staged.byte_size,
    ) == staged
    assert staged.to_dict()["digest"] == prepared.digest
    published = publish_prepared_media(tmp_path, TXN_B, prepared)
    assert PublishedMedia(
        digest=published.digest,
        managed_path=published.managed_path,
        byte_size=published.byte_size,
        reused=published.reused,
    ) == published
    assert published.to_dict()["managed_path"] == str(published.managed_path)


# ---------------------------------------------------------------------------
# Startup staging GC through the standard composition root (m2 plan step 3/4,
# T4)
# ---------------------------------------------------------------------------

GC_TS = "2026-08-16T00:00:00.000000+00:00"
GC_TS2 = "2026-08-16T01:00:00.000000+00:00"

_GC_SEED_COUNTER = 0


def _derived_db_path(projects_root: Path) -> Path:
    """The standard composition database path under a projects root."""
    from astrid.core.integrations.reigh.bridge_service import derive_database_path

    return derive_database_path(projects_root)


def _seed_live_attempt(
    projects_root: Path,
    *,
    txn_id: str,
    status: str = "claimed",
    progress: dict | None = None,
) -> str:
    """Create project + task + one attempt row directly (pre-composition).

    Returns the seeded task id. The database is created at the standard
    composition path with a kernel-only registry, then closed so the
    composition can open it next. Each call uses fresh slugs and
    idempotency keys so one test may seed several attempts.
    """
    global _GC_SEED_COUNTER

    from astrid.core.events.service import EventAppendService
    from astrid.core.ids import generate_lowercase_ulid
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.projects import ProjectRepository
    from astrid.core.repositories.tasks import TaskRepository
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.store.writer import DatabaseWriter

    _GC_SEED_COUNTER += 1
    suffix = _GC_SEED_COUNTER
    db_path = _derived_db_path(projects_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = DatabaseWriter(db_path, core_only_registry())
    try:
        events = EventAppendService(core_only_registry())
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        tasks = TaskRepository(events=events, receipts=receipts)
        project = UnitOfWork(writer).run(
            lambda u: projects.create(
                u,
                slug=f"pilot-{suffix}",
                name="Pilot",
                settings={},
                idempotency_key=f"gc-proj-k-{suffix}",
                created_at=GC_TS,
            )
        )
        task = UnitOfWork(writer).run(
            lambda u: tasks.create(
                u,
                project_id=project.id,
                capability="rendering.timeline_visualize",
                spec={"fps": 24},
                input_manifest=[],
                idempotency_key=f"gc-task-k-{suffix}",
                task_id=generate_lowercase_ulid(),
                created_at=GC_TS,
            )
        )
        payload = json.dumps(progress if progress is not None else {"staging_txn_id": txn_id})
        writer.submit(
            lambda session: session.execute(
                "INSERT INTO execution_attempts "
                "(id, task_id, attempt_no, executor_id, status, status_version, "
                "lease_id, lease_expires_at, heartbeat_counter, last_heartbeat_at, "
                "progress_json, error_json, created_at, updated_at, finished_at) "
                "VALUES (?, ?, 1, ?, ?, 1, ?, ?, 0, NULL, ?, '{}', ?, ?, NULL)",
                (
                    f"attempt-gc-{suffix}",
                    task.id,
                    "exec-1",
                    status,
                    f"lease-gc-{suffix}",
                    GC_TS2,
                    payload,
                    GC_TS,
                    GC_TS,
                ),
            )
        )
        return task.id
    finally:
        writer.close()


def test_composition_startup_gc_preserves_live_attempt_staging(tmp_path: Path) -> None:
    """The standard composition runs GC keeping live-attempt staging only."""
    from astrid.packs import compose_standard_bridge

    live_dir = _stage_dir(tmp_path, TXN_A, "live.bin", b"live")
    orphan_dir = _stage_dir(tmp_path, TXN_B, "dead.bin", b"dead")
    _seed_live_attempt(tmp_path, txn_id=TXN_A, status="claimed")

    composition = compose_standard_bridge(tmp_path)
    try:
        # Startup GC kept the live-attempt staging and removed the orphan.
        assert live_dir.exists()
        assert not orphan_dir.exists()
        # The composed bridge is fully serviceable: the read surface works.
        with composition.writer.read_only_connection() as conn:
            project_id = str(conn.execute("SELECT id FROM projects").fetchone()[0])
        project = composition.projects.show(composition.writer, project_id)
        assert project.slug == "pilot-1"
    finally:
        composition.writer.close()


def test_composition_startup_gc_collects_live_attempts_read_only(tmp_path: Path) -> None:
    """collect_live_staging_txn_ids reads only live attempts, never terminal."""
    from astrid.core.store.writer import DatabaseWriter
    from astrid.packs import collect_live_staging_txn_ids, run_startup_staging_gc

    _seed_live_attempt(tmp_path, txn_id=TXN_A, status="running")
    _seed_live_attempt(tmp_path, txn_id=TXN_B, status="failed", progress={"staging_txn_id": TXN_B})
    live_dir = _stage_dir(tmp_path, TXN_A, "live.bin", b"live")
    dead_dir = _stage_dir(tmp_path, TXN_B, "dead.bin", b"dead")
    orphan_dir = _stage_dir(tmp_path, TXN_C, "orphan.bin", b"orphan")

    db_path = _derived_db_path(tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = DatabaseWriter(db_path, core_only_registry())
    try:
        assert collect_live_staging_txn_ids(writer) == {TXN_A}
        result = run_startup_staging_gc(tmp_path, writer)
        assert result.removed_directories == 2  # TXN_B (terminal) + TXN_C (orphan)
        assert result.remaining_directories == 1  # TXN_A (running)
        assert live_dir.exists()
        assert not dead_dir.exists()
        assert not orphan_dir.exists()
    finally:
        writer.close()


def test_composition_startup_gc_never_touches_managed_digests(tmp_path: Path) -> None:
    """Composition GC leaves the published managed digest tree byte-identical."""
    from astrid.packs import compose_standard_bridge

    source = _write(tmp_path, "in/clip.bin", b"managed bytes")
    prepared = prepare_media_file(source, root=tmp_path / "in")
    publish_prepared_media(tmp_path, TXN_A, prepared)
    _stage_dir(tmp_path, TXN_B, "orphan.bin", b"orphan")
    managed_before = set(
        p for p in (tmp_path / MANAGED_ROOT_DIRNAME / "media" / "sha256").rglob("*") if p.is_file()
    )

    composition = compose_standard_bridge(tmp_path)
    try:
        managed_after = set(
            p
            for p in (tmp_path / MANAGED_ROOT_DIRNAME / "media" / "sha256").rglob("*")
            if p.is_file()
        )
        assert managed_after == managed_before
        assert managed_media_path(tmp_path, prepared.digest).read_bytes() == b"managed bytes"
        assert not staging_path(tmp_path, TXN_B).exists()
    finally:
        composition.writer.close()


def test_composition_startup_gc_skips_malformed_staging_references(tmp_path: Path) -> None:
    """A corrupt progress entry never blocks composition nor preserves staging."""
    from astrid.packs import compose_standard_bridge

    _seed_live_attempt(
        tmp_path,
        txn_id=TXN_A,
        status="claimed",
        progress={"staging_txn_id": "../escape"},
    )
    _seed_live_attempt(
        tmp_path,
        txn_id=TXN_B,
        status="running",
        progress={"staging_txn_id": 42},
    )
    _seed_live_attempt(
        tmp_path,
        txn_id=TXN_C,
        status="claimed",
        progress="not-json",
    )
    _stage_dir(tmp_path, TXN_A, "a.bin", b"a")
    _stage_dir(tmp_path, TXN_B, "b.bin", b"b")
    _stage_dir(tmp_path, TXN_C, "c.bin", b"c")

    composition = compose_standard_bridge(tmp_path)
    try:
        # Malformed references are skipped: every staging dir is unreferenced
        # and removed, and composition still succeeds.
        assert not staging_path(tmp_path, TXN_A).exists()
        assert not staging_path(tmp_path, TXN_B).exists()
        assert not staging_path(tmp_path, TXN_C).exists()
    finally:
        composition.writer.close()


def test_composition_startup_gc_without_staging_root_is_noop(tmp_path: Path) -> None:
    """A fresh root without staging composes cleanly and stays serviceable."""
    from astrid.packs import compose_standard_bridge

    composition = compose_standard_bridge(tmp_path)
    try:
        assert not (tmp_path / MANAGED_ROOT_DIRNAME / "media" / ".staging").exists()
        assert composition.projects.list(composition.writer) == []
    finally:
        composition.writer.close()
