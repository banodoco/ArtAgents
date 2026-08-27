from __future__ import annotations

import copy

import pytest

from astrid.core import timeline
from astrid.core.timeline.validators.registry import validate_registry


def _base_registry() -> dict[str, object]:
    return {
        "assets": {
            "main": {
                "file": "main.mp4",
                "media_id": "01jpairedreleaseasset000001",
                "url": "https://example.com/assets/main.mp4",
                "etag": '"main-etag"',
                "content_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                "url_expires_at": "2026-12-31T23:59:59Z",
                "type": "video/mp4",
                "duration": 42.0,
                "resolution": "1920x1080",
                "fps": 30.0,
                "origin": "refreshable-from-generation",
                "derivedFrom": {
                    "assetId": "source-main",
                    "content_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
                    "role": "proxy",
                },
                "generationId": "gen-main",
                "variantId": "variant-main",
                "thumbnailUrl": "https://example.com/main.jpg",
            }
        }
    }


# ---------------------------------------------------------------------------
# Round-trip preservation tests
# ---------------------------------------------------------------------------

def test_roundtrip_preserves_extended_asset_fields(tmp_path) -> None:
    registry = _base_registry()
    path = tmp_path / "registry.json"

    timeline.save_registry(registry, path)
    loaded = timeline.load_registry(path)

    assert loaded == registry


def test_roundtrip_preserves_url(tmp_path) -> None:
    registry: dict[str, object] = {
        "assets": {
            "a": {
                "file": "a.mp4",
                "url": "https://cdn.example.com/a.mp4",
            }
        }
    }
    path = tmp_path / "registry.json"
    timeline.save_registry(registry, path)
    loaded = timeline.load_registry(path)
    assert loaded == registry


def test_roundtrip_preserves_media_id(tmp_path) -> None:
    registry: dict[str, object] = {
        "assets": {
            "a": {
                "file": "a.mp4",
                "media_id": "01jpairedreleaseasset000001",
            }
        }
    }
    path = tmp_path / "registry.json"
    timeline.save_registry(registry, path)
    loaded = timeline.load_registry(path)
    assert loaded == registry


def test_validate_registry_accepts_media_id_without_file_or_url() -> None:
    validate_registry(
        {"assets": {"managed": {"media_id": "01jpairedreleaseasset000001"}}}
    )


def test_roundtrip_preserves_etag(tmp_path) -> None:
    registry: dict[str, object] = {
        "assets": {
            "a": {
                "file": "a.mp4",
                "etag": '"abc123"',
            }
        }
    }
    path = tmp_path / "registry.json"
    timeline.save_registry(registry, path)
    loaded = timeline.load_registry(path)
    assert loaded == registry


def test_roundtrip_preserves_content_sha256(tmp_path) -> None:
    registry: dict[str, object] = {
        "assets": {
            "a": {
                "file": "a.mp4",
                "content_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            }
        }
    }
    path = tmp_path / "registry.json"
    timeline.save_registry(registry, path)
    loaded = timeline.load_registry(path)
    assert loaded == registry


def test_roundtrip_preserves_url_expires_at(tmp_path) -> None:
    registry: dict[str, object] = {
        "assets": {
            "a": {
                "file": "a.mp4",
                "url_expires_at": "2026-12-31T23:59:59Z",
            }
        }
    }
    path = tmp_path / "registry.json"
    timeline.save_registry(registry, path)
    loaded = timeline.load_registry(path)
    assert loaded == registry


def test_roundtrip_preserves_origin(tmp_path) -> None:
    for origin in ("immutable-public", "refreshable-from-generation", "opaque-foreign"):
        registry: dict[str, object] = {
            "assets": {
                "a": {
                    "file": "a.mp4",
                    "origin": origin,
                }
            }
        }
        path = tmp_path / "registry.json"
        timeline.save_registry(registry, path)
        loaded = timeline.load_registry(path)
        assert loaded == registry


def test_roundtrip_preserves_thumbnailUrl(tmp_path) -> None:
    registry: dict[str, object] = {
        "assets": {
            "a": {
                "file": "a.mp4",
                "thumbnailUrl": "https://cdn.example.com/a.jpg",
            }
        }
    }
    path = tmp_path / "registry.json"
    timeline.save_registry(registry, path)
    loaded = timeline.load_registry(path)
    assert loaded == registry


def test_roundtrip_preserves_derivedFrom(tmp_path) -> None:
    registry: dict[str, object] = {
        "assets": {
            "a": {
                "file": "a.mp4",
                "derivedFrom": {
                    "assetId": "parent-a",
                    "content_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "role": "proxy",
                },
            }
        }
    }
    path = tmp_path / "registry.json"
    timeline.save_registry(registry, path)
    loaded = timeline.load_registry(path)
    assert loaded == registry


def test_roundtrip_preserves_generationId(tmp_path) -> None:
    registry: dict[str, object] = {
        "assets": {
            "a": {
                "file": "a.mp4",
                "generationId": "gen-abc-123",
            }
        }
    }
    path = tmp_path / "registry.json"
    timeline.save_registry(registry, path)
    loaded = timeline.load_registry(path)
    assert loaded == registry


# ---------------------------------------------------------------------------
# Validation rejection tests
# ---------------------------------------------------------------------------

def test_validate_registry_rejects_invalid_origin() -> None:
    registry = _base_registry()
    registry["assets"]["main"]["origin"] = "vendor-cache"  # type: ignore[index]

    try:
        validate_registry(registry)
    except ValueError as exc:
        assert "origin" in str(exc)
    else:
        raise AssertionError("validate_registry should reject invalid origin values")


def test_validate_registry_rejects_invalid_derived_from_role() -> None:
    registry = _base_registry()
    broken = copy.deepcopy(registry)
    broken["assets"]["main"]["derivedFrom"]["role"] = "preview"  # type: ignore[index]

    try:
        validate_registry(broken)
    except ValueError as exc:
        assert "derivedFrom.role" in str(exc)
    else:
        raise AssertionError("validate_registry should reject invalid derivedFrom.role values")


@pytest.mark.parametrize("bad_sha256", [
    "too-short",
    "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789",
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85g",
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85",  # 63 chars
    1234567890123456789012345678901234567890123456789012345678901234,  # number, not string
])
def test_validate_registry_rejects_invalid_content_sha256(bad_sha256) -> None:
    registry = _base_registry()
    registry["assets"]["main"]["content_sha256"] = bad_sha256  # type: ignore[index]

    with pytest.raises(ValueError, match="content_sha256"):
        validate_registry(registry)


def test_validate_registry_rejects_invalid_derived_from_asset_id() -> None:
    registry = _base_registry()
    broken = copy.deepcopy(registry)
    broken["assets"]["main"]["derivedFrom"]["assetId"] = ""  # type: ignore[index]

    with pytest.raises(ValueError, match="derivedFrom.assetId"):
        validate_registry(broken)


def test_validate_registry_rejects_invalid_derived_from_content_sha256() -> None:
    registry = _base_registry()
    broken = copy.deepcopy(registry)
    broken["assets"]["main"]["derivedFrom"]["content_sha256"] = "bad-hash"  # type: ignore[index]

    with pytest.raises(ValueError, match="derivedFrom.content_sha256"):
        validate_registry(broken)


def test_validate_registry_rejects_invalid_url_expires_at() -> None:
    registry = _base_registry()
    registry["assets"]["main"]["url_expires_at"] = "not-a-date"  # type: ignore[index]

    with pytest.raises(ValueError, match="url_expires_at"):
        validate_registry(registry)


def test_validate_registry_rejects_invalid_etag() -> None:
    registry = _base_registry()
    registry["assets"]["main"]["etag"] = ""  # type: ignore[index]

    with pytest.raises(ValueError, match="etag"):
        validate_registry(registry)


@pytest.mark.parametrize("bad_media_id", ["", "   ", 123])
def test_validate_registry_rejects_invalid_media_id(bad_media_id) -> None:
    registry = _base_registry()
    registry["assets"]["main"]["media_id"] = bad_media_id  # type: ignore[index]

    with pytest.raises(ValueError, match="media_id"):
        validate_registry(registry)


def test_validate_registry_accepts_all_valid_origins() -> None:
    for origin in ("immutable-public", "refreshable-from-generation", "opaque-foreign"):
        registry = _base_registry()
        registry["assets"]["main"]["origin"] = origin  # type: ignore[index]
        # Should not raise
        validate_registry(registry)


def test_validate_registry_rejects_non_dict_derived_from() -> None:
    registry = _base_registry()
    registry["assets"]["main"]["derivedFrom"] = "not-an-object"  # type: ignore[index]

    with pytest.raises(ValueError, match="derivedFrom"):
        validate_registry(registry)
