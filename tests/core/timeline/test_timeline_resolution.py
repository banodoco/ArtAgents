from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from astrid.core.timeline.resolution import (
    AssetIntegrity,
    classify_asset,
    classify_registry,
    resolve_asset_path,
)

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "timeline_visualize"
)
SLICE_DIR = FIXTURE_ROOT / "desert_slice"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(tmp_path: Path, relative: str, data: bytes) -> Path:
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


# --- 1. verified original ---------------------------------------------------

def test_verified_original(tmp_path: Path) -> None:
    data = b"plant frame one bytes"
    path = _write(tmp_path, "sources/plant-frame-1.png", data)
    result = classify_asset(
        "plant-frame-1",
        {"file": "sources/plant-frame-1.png", "content_sha256": _sha256(data)},
        project_root=tmp_path,
    )
    assert result.state == "verified_original"
    assert result.role == "timeline_media"
    assert result.expected_sha256 == _sha256(data)
    assert result.observed_sha256 == _sha256(data)
    assert Path(result.path) == path.resolve()
    assert result.source_id is None
    assert result.source_version is None
    assert resolve_asset_path(
        "plant-frame-1",
        {"file": "sources/plant-frame-1.png"},
        project_root=tmp_path,
    ) == path.resolve()


# --- 2. hash mismatch -------------------------------------------------------

@pytest.mark.parametrize("hash_key", ["content_sha256", "sha256", "hash"])
def test_hash_mismatch(tmp_path: Path, hash_key: str) -> None:
    _write(tmp_path, "sources/clip.mp4", b"actual bytes")
    expected = _sha256(b"different bytes")
    result = classify_asset(
        "clip",
        {"file": "sources/clip.mp4", hash_key: expected},
        project_root=tmp_path,
    )
    assert result.state == "hash_mismatch"
    assert result.expected_sha256 == expected
    assert result.observed_sha256 == _sha256(b"actual bytes")
    assert "!=" in result.reason


# --- 3. hash unrecorded -----------------------------------------------------

def test_hash_unrecorded(tmp_path: Path) -> None:
    data = b"toccata fugue audio bytes"
    _write(tmp_path, "sources/toccata-fugue/toccata-fugue.mp3", data)
    result = classify_asset(
        "toccata-fugue",
        {"file": "toccata-fugue/toccata-fugue.mp3", "duration": 97.5},
        project_root=tmp_path,
    )
    assert result.state == "hash_unrecorded"
    assert result.expected_sha256 is None
    # A current hash does not retroactively verify: never observed.
    assert result.observed_sha256 is None
    assert "no expected sha256" in result.reason


# --- 4. missing -------------------------------------------------------------

def test_missing(tmp_path: Path) -> None:
    result = classify_asset(
        "plant-frame-1",
        {"file": "sources/plant-frame-1.png", "content_sha256": "a" * 64},
        project_root=tmp_path,
    )
    assert result.state == "missing"
    assert result.expected_sha256 == "a" * 64
    assert result.observed_sha256 is None
    assert result.path is not None
    assert not Path(result.path).exists()
    assert "file not found" in result.reason


# --- 5. remote --------------------------------------------------------------

@pytest.mark.parametrize("url", ["https://cdn.example/plant.png", "data:image/png;base64,AAAA"])
def test_remote(tmp_path: Path, url: str) -> None:
    result = classify_asset(
        "plant-frame-1",
        {"url": url},
        project_root=tmp_path,
    )
    assert result.state == "remote"
    assert result.path is None
    assert "no fetch" in result.reason
    assert resolve_asset_path("plant-frame-1", {"url": url}, project_root=tmp_path) is None


# --- 6. path escape ---------------------------------------------------------

def test_path_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.png"
    outside.write_bytes(b"outside")
    result = classify_asset(
        "plant-frame-1",
        {"file": "../../outside.png"},
        project_root=tmp_path,
    )
    assert result.state == "unsupported"
    assert result.path is None
    assert "path escapes project root" in result.reason
    assert resolve_asset_path(
        "plant-frame-1", {"file": "../../outside.png"}, project_root=tmp_path
    ) is None


# --- 7. contained relative path --------------------------------------------

def test_contained_relative_path(tmp_path: Path) -> None:
    data = b"foo png bytes"
    _write(tmp_path, "sources/foo.png", data)
    result = classify_asset(
        "foo",
        {"file": "sources/foo.png", "content_sha256": _sha256(data)},
        project_root=tmp_path,
    )
    assert result.state == "verified_original"
    resolved = (tmp_path / "sources/foo.png").resolve()
    assert Path(result.path) == resolved
    assert resolved.is_relative_to(tmp_path.resolve())


# --- 7b. sources-relative refs (R4 base parity) -----------------------------

def test_sources_relative_refs(tmp_path: Path) -> None:
    """Relative refs resolve against sources_root (R4 parity); an absolute
    ref must also land inside sources to be accepted."""
    data = b"bar png bytes"
    _write(tmp_path, "sources/bar.png", data)
    sources_relative = classify_asset(
        "bar",
        {"file": "bar.png", "content_sha256": _sha256(data)},
        project_root=tmp_path,
    )
    assert sources_relative.state == "verified_original"
    assert Path(sources_relative.path) == (tmp_path / "sources/bar.png").resolve()

    absolute = classify_asset(
        "bar",
        {"file": str((tmp_path / "sources/bar.png").resolve()), "content_sha256": _sha256(data)},
        project_root=tmp_path,
    )
    assert absolute.state == "verified_original"
    assert Path(absolute.path) == (tmp_path / "sources/bar.png").resolve()


# --- 8. thumbnail only ------------------------------------------------------

def test_thumbnail_only(tmp_path: Path) -> None:
    by_key = classify_asset(
        "plant-frame-1-thumbnail",
        {"thumbnailUrl": "https://cdn.example/plant-thumb.png"},
        project_root=tmp_path,
    )
    assert by_key.role == "thumbnail_only"
    assert by_key.state == "thumbnail_only"
    assert by_key.expected_sha256 is None

    by_role = classify_asset(
        "plant-frame-1",
        {"role": "thumbnail", "file": "sources/plant-frame-1.png"},
        project_root=tmp_path,
    )
    assert by_role.role == "thumbnail_only"
    assert by_role.state == "thumbnail_only"
    assert by_role.path is not None  # local path still recorded, no hash required

    by_explicit = classify_asset(
        "plant-frame-1",
        {"thumbnailUrl": "https://cdn.example/plant-thumb.png"},
        project_root=tmp_path,
        roles={"thumbnail_only"},
    )
    assert by_explicit.state == "thumbnail_only"


# --- 8b. provenance ---------------------------------------------------------

def test_provenance_fields(tmp_path: Path) -> None:
    data = b"provenance bytes"
    _write(tmp_path, "sources/prov.png", data)
    result = classify_asset(
        "prov",
        {
            "file": "sources/prov.png",
            "content_sha256": _sha256(data),
            "sourceId": "local:abc123",
            "sourceVersion": "local-v1:def456",
        },
        project_root=tmp_path,
    )
    assert result.state == "verified_original"
    assert result.source_id == "local:abc123"
    assert result.source_version == "local-v1:def456"

    # Provenance survives non-verified states too (missing file).
    missing = classify_asset(
        "prov",
        {"file": "sources/nope.png", "sourceId": "local:xyz", "sourceVersion": "local-v1:uvw"},
        project_root=tmp_path,
    )
    assert missing.state == "missing"
    assert missing.source_id == "local:xyz"
    assert missing.source_version == "local-v1:uvw"

    # Blank/absent provenance stays None.
    blank = classify_asset(
        "prov",
        {"file": "sources/prov.png", "sourceId": "   ", "sourceVersion": None},
        project_root=tmp_path,
    )
    assert blank.source_id is None
    assert blank.source_version is None


# --- 8c. outside-sources rejection ------------------------------------------

def test_outside_sources_rejected(tmp_path: Path) -> None:
    """A path inside project_root but outside sources/ is unsupported."""
    _write(tmp_path, "README.md", b"# readme")
    result = classify_asset(
        "readme",
        {"file": "../README.md"},
        project_root=tmp_path,
    )
    assert result.state == "unsupported"
    assert result.path is None
    assert "path outside sources" in result.reason
    assert resolve_asset_path("readme", {"file": "../README.md"}, project_root=tmp_path) is None


# --- 8d. README repro (R4 agreement) ----------------------------------------

def test_readme_repro_missing(tmp_path: Path) -> None:
    """The oracle repro: a plain `README.md` ref resolves against sources/ and
    is missing there — matching R4's MEDIA_MISSING, never verified_original."""
    _write(tmp_path, "README.md", b"# readme")
    result = classify_asset(
        "readme",
        {"file": "README.md", "content_sha256": "a" * 64},
        project_root=tmp_path,
    )
    assert result.state == "missing"
    assert result.observed_sha256 is None
    assert result.path is not None
    assert Path(result.path).is_relative_to((tmp_path / "sources").resolve())
    assert "file not found" in result.reason


# --- 8e. symlink escape -----------------------------------------------------

def test_symlink_escape_inside_project(tmp_path: Path) -> None:
    """A symlink inside sources pointing outside sources (but inside the
    project) must not be followed into a verified original."""
    secret = _write(tmp_path, "secret.png", b"secret bytes")
    link = _write(tmp_path, "sources/link.png", b"")
    link.unlink()
    link.symlink_to(secret)
    result = classify_asset(
        "plant-frame-1",
        {"file": "link.png", "content_sha256": _sha256(b"secret bytes")},
        project_root=tmp_path,
    )
    assert result.state == "unsupported"
    assert result.path is None
    assert "symlink escapes sources" in result.reason
    assert resolve_asset_path("plant-frame-1", {"file": "link.png"}, project_root=tmp_path) is None


def test_symlink_escape_outside_project(tmp_path: Path) -> None:
    """A symlink inside sources pointing fully outside project_root is also
    unsupported with the symlink-escape reason."""
    outside = tmp_path.parent / "outside-secret.png"
    outside.write_bytes(b"outside secret")
    link = _write(tmp_path, "sources/link2.png", b"")
    link.unlink()
    link.symlink_to(outside)
    result = classify_asset(
        "plant-frame-1",
        {"file": "link2.png", "content_sha256": _sha256(b"outside secret")},
        project_root=tmp_path,
    )
    assert result.state == "unsupported"
    assert result.path is None
    assert "symlink escapes sources" in result.reason


def test_symlink_inside_sources_allowed(tmp_path: Path) -> None:
    """A symlink inside sources whose real target still lands inside sources
    is allowed and verified against the target's bytes."""
    data = b"real target bytes"
    real = _write(tmp_path, "sources/real.png", data)
    link = _write(tmp_path, "sources/alias.png", b"")
    link.unlink()
    link.symlink_to(real)
    result = classify_asset(
        "plant-frame-1",
        {"file": "alias.png", "content_sha256": _sha256(data)},
        project_root=tmp_path,
    )
    assert result.state == "verified_original"
    assert Path(result.path) == real.resolve()


# --- 8f. sources root escaping project --------------------------------------

def test_sources_root_escaping_project(tmp_path: Path) -> None:
    """If project_root/sources itself resolves outside project_root (R4:
    MEDIA_SOURCES_OUTSIDE_PROJECT), every local ref is unsupported."""
    outside_sources = tmp_path.parent / "outside-sources-dir"
    outside_sources.mkdir(exist_ok=True)
    (outside_sources / "foo.png").write_bytes(b"foo")
    (tmp_path / "sources").symlink_to(outside_sources, target_is_directory=True)
    result = classify_asset(
        "foo",
        {"file": "foo.png"},
        project_root=tmp_path,
    )
    assert result.state == "unsupported"
    assert result.path is None
    assert "path escapes project root" in result.reason


# --- 9. desert slice registry shape ----------------------------------------

def test_classify_registry_desert_slice_shape(tmp_path: Path) -> None:
    registry = json.loads((SLICE_DIR / "registry.json").read_text(encoding="utf-8"))
    assert set(registry) == {"assets"}
    entries = registry["assets"]
    assert set(entries) == {"plant-frame-1", "plant-frame-2", "plant-frame-3", "plant-frame-4", "toccata-fugue"}

    # Build a temp project with real files under sources/; keep the slice's
    # registry shape but align content_sha256 with the bytes we actually write.
    for key, entry in entries.items():
        file_ref = entry["file"]
        data = f"{key} bytes".encode()
        _write(tmp_path, f"sources/{file_ref}", data)
        if "content_sha256" in entry:
            entry["content_sha256"] = _sha256(data)

    results = classify_registry(registry, project_root=tmp_path)

    assert set(results) == set(entries)
    for key in ("plant-frame-1", "plant-frame-2", "plant-frame-3", "plant-frame-4"):
        assert results[key].state == "verified_original", key
        assert results[key].role == "timeline_media"
        # Real registry shape carries provenance.
        assert results[key].source_id is not None, key
        assert results[key].source_version is not None, key
        assert results[key].source_id.startswith("local:")
        assert results[key].source_version.startswith("local-v1:")

    toccata = results["toccata-fugue"]
    assert toccata.state == "hash_unrecorded"
    assert toccata.expected_sha256 is None
    assert toccata.observed_sha256 is None
    assert "duration=97.5" in toccata.reason
    assert toccata.path is not None
    assert Path(toccata.path).is_relative_to((tmp_path / "sources").resolve())
    assert toccata.source_id is not None
    assert toccata.source_version is not None


# --- 10. determinism --------------------------------------------------------

def test_determinism(tmp_path: Path) -> None:
    data = b"deterministic bytes"
    _write(tmp_path, "sources/foo.png", data)
    entry = {"file": "sources/foo.png", "content_sha256": _sha256(data), "duration": 3.0}
    first = classify_asset("foo", entry, project_root=tmp_path)
    second = classify_asset("foo", entry, project_root=tmp_path)
    assert first == second
    assert first is not second  # frozen dataclass, not the same object

    registry = {"assets": {"foo": entry, "bar": {"file": "sources/bar.png"}}}
    left = classify_registry(registry, project_root=tmp_path)
    right = classify_registry(registry, project_root=tmp_path)
    assert left == right
    assert list(left) == list(right)  # stable key order


# --- extras ---------------------------------------------------------------

def test_remote_url_with_local_file_prefers_local(tmp_path: Path) -> None:
    data = b"local wins"
    _write(tmp_path, "sources/foo.png", data)
    result = classify_asset(
        "foo",
        {"file": "sources/foo.png", "url": "https://cdn.example/foo.png", "content_sha256": _sha256(data)},
        project_root=tmp_path,
    )
    assert result.state == "verified_original"
    assert result.path is not None
    assert "remote" not in result.reason


def test_roles_and_default_role_params(tmp_path: Path) -> None:
    _write(tmp_path, "sources/ref.png", b"ref")
    explicit = classify_asset(
        "ref",
        {"file": "sources/ref.png"},
        project_root=tmp_path,
        roles={"generation_reference"},
    )
    assert explicit.role == "generation_reference"

    defaulted = classify_asset(
        "ref",
        {"file": "sources/ref.png"},
        project_root=tmp_path,
        default_role="rendered_sample",
    )
    assert defaulted.role == "rendered_sample"

    unknown = classify_asset(
        "ref",
        {"file": "sources/ref.png", "kind": "banodoco-unknown-kind"},
        project_root=tmp_path,
    )
    assert unknown.role == "unknown"


def test_list_assets_shape(tmp_path: Path) -> None:
    data = b"list shape"
    _write(tmp_path, "sources/a.png", data)
    registry = {
        "assets": [
            {"asset_key": "a", "file": "sources/a.png", "content_sha256": _sha256(data)},
            {"b": {"file": "sources/b.png"}},
            "c",
        ]
    }
    results = classify_registry(registry, project_root=tmp_path)
    assert set(results) == {"a", "b", "asset-2"}
    assert results["a"].state == "verified_original"
    assert results["b"].state == "missing"
    assert results["asset-2"].state == "missing"
