from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from astrid.packs.media.executors.gif_search import run


class FakeResponse:
    def __init__(self, body: bytes, *, headers: dict[str, str] | None = None) -> None:
        self._body = body
        self.headers = headers or {}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_normalize_giphy_response_keeps_useful_renditions() -> None:
    payload = run.normalize_giphy_response(
        {
            "data": [
                {
                    "id": "abc",
                    "title": "A GIF",
                    "url": "https://giphy.com/gifs/abc",
                    "rating": "g",
                    "images": {
                        "original": {"url": "https://cdn/abc.gif", "mp4": "https://cdn/abc.mp4", "width": "480"},
                        "fixed_width": {"url": "https://cdn/abc-fw.gif", "height": "200"},
                    },
                }
            ],
            "pagination": {"count": 1, "total_count": 20},
            "meta": {"status": 200},
        },
        query="zoom",
        media_kind="gif",
    )

    assert payload["provider"] == "giphy"
    assert payload["attribution"] == "Powered by GIPHY"
    assert payload["results"][0]["id"] == "abc"
    assert payload["results"][0]["preview_url"] == "https://cdn/abc-fw.gif"
    assert payload["results"][0]["images"]["original"]["width"] == 480


def test_main_writes_results_preview_manifest_and_download(tmp_path: Path) -> None:
    search_body = json.dumps(
        {
            "data": [
                {
                    "id": "abc",
                    "title": "A GIF",
                    "url": "https://giphy.com/gifs/abc",
                    "images": {"original": {"url": "https://cdn/abc.gif", "mp4": "https://cdn/abc.mp4"}},
                }
            ],
            "pagination": {"count": 1, "total_count": 1},
            "meta": {"status": 200},
        }
    ).encode("utf-8")

    def fake_urlopen(request, timeout):
        url = request.full_url
        if "api.giphy.com" in url:
            return FakeResponse(search_body, headers={"content-type": "application/json"})
        if url == "https://cdn/abc.mp4":
            return FakeResponse(b"mp4-bytes", headers={"content-type": "video/mp4"})
        raise AssertionError(f"unexpected URL: {url}")

    with patch("astrid.packs.media.executors.gif_search.run.CredentialsScope.get", return_value="key"):
        assert run.main(
            [
                "--query",
                "zoom",
                "--out",
                str(tmp_path),
                "--download-index",
                "0",
            ],
            urlopen=fake_urlopen,
        ) == 0

    results = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert results["results"][0]["id"] == "abc"
    assert (tmp_path / "preview.html").is_file()
    assert (tmp_path / "selected-0-abc.mp4").read_bytes() == b"mp4-bytes"
    assert manifest["kind"] == "gif_search"
    assert manifest["metrics"]["result_count"] == 1


def test_rejects_download_index_and_id_together(tmp_path: Path) -> None:
    assert run.main(
        [
            "--query",
            "zoom",
            "--out",
            str(tmp_path),
            "--download-index",
            "0",
            "--download-id",
            "abc",
        ]
    ) == 2
