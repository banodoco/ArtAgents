"""Sprint 8: asset resolution / cache tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from worker_assets import (
    cache_clear,
    cache_get,
    cache_put,
    resolve_asset,
    resolve_asset_registry,
    sha256_of_file,
)


@pytest.fixture(autouse=True)
def _isolated_cache():
    cache_clear()
    yield
    cache_clear()


def test_http_url_passes_through_unchanged(tmp_path: Path):
    final_url, local_path = resolve_asset(
        {"url": "https://cdn.example.com/clip.mp4"},
        user_id="user-1",
        work_dir=tmp_path,
    )
    assert final_url == "https://cdn.example.com/clip.mp4"
    assert local_path is None


def test_http_url_with_extra_fields_still_passes_through(tmp_path: Path):
    final_url, local_path = resolve_asset(
        {
            "url": "http://localhost:8000/clip.mp4",
            "content_sha256": "deadbeef",
        },
        user_id="user-1",
        work_dir=tmp_path,
    )
    assert final_url.startswith("http://localhost:8000/")
    assert local_path is None


def test_storage_key_downloads_and_caches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REIGH_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("REIGH_SUPABASE_SERVICE_ROLE_KEY", "service-role-test")

    payload = b"fake-mp4-bytes"

    class _StubResp:
        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    http = MagicMock()
    http.stream.return_value = _StubResp()

    final_url, local_path = resolve_asset(
        {"storage_path": "user-1/timeline-1/clip.mp4"},
        user_id="user-1",
        work_dir=tmp_path,
        http=http,
    )
    assert local_path is not None
    assert local_path.exists()
    assert local_path.read_bytes() == payload
    assert final_url == local_path.as_uri()

    # Sha256 of the bytes ends up keyed in the cache.
    digest = hashlib.sha256(payload).hexdigest()
    assert cache_get(digest) == local_path


def test_cache_hit_skips_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REIGH_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("REIGH_SUPABASE_SERVICE_ROLE_KEY", "service-role-test")

    cached_file = tmp_path / "cached.mp4"
    cached_file.write_bytes(b"already-here")
    digest = sha256_of_file(cached_file)
    cache_put(digest, cached_file)

    http = MagicMock()
    final_url, local_path = resolve_asset(
        {"storage_path": "user-1/timeline-1/clip.mp4", "content_sha256": digest},
        user_id="user-1",
        work_dir=tmp_path / "fresh",
        http=http,
    )
    # The HTTP client was never called — we hit the cache.
    http.stream.assert_not_called()
    assert local_path == cached_file
    assert final_url == cached_file.as_uri()


def test_resolve_registry_handles_mixed_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REIGH_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("REIGH_SUPABASE_SERVICE_ROLE_KEY", "service-role-test")

    payload = b"storage-bytes"

    class _StubResp:
        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    http = MagicMock()
    http.stream.return_value = _StubResp()

    registry = {
        "assets": {
            "remote": {"url": "https://cdn.example.com/a.mp4"},
            "stored": {"storage_path": "user-1/timeline-1/b.mp4"},
        },
    }
    resolved = resolve_asset_registry(
        registry, user_id="user-1", work_dir=tmp_path, http=http,
    )
    assert resolved["assets"]["remote"]["file"] == "https://cdn.example.com/a.mp4"
    assert resolved["assets"]["stored"]["file"].startswith("file://")


def test_unresolvable_entry_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        resolve_asset({}, user_id="u", work_dir=tmp_path)
