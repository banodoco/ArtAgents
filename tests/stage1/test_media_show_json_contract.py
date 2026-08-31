"""The product media show read must remain a JSON metadata operation."""

from __future__ import annotations

import json

from astrid.core.cli.domain_output import render_envelope_json
from astrid.sdk.remote import RemoteMedia


class _Runtime:
    def __init__(self) -> None:
        self.downloads = 0

    def list_project_objects(self, project: str, *, cursor: str | None, limit: int):
        assert project == "demo"
        assert cursor is None
        assert limit == 50
        return [
            [
                {
                    "object_id": "sha256:object",
                    "digest": "sha256:object",
                    "media_type": "image/png",
                    "size": 3,
                    "version": 1,
                    "created_at": "2026-09-01T00:00:00Z",
                    "filename": "shot.png",
                }
            ],
            None,
        ]

    def get_object(self, _object_id: str):
        self.downloads += 1
        return {"data": b"raw managed bytes"}


def test_media_show_returns_metadata_and_never_downloads_bytes() -> None:
    runtime = _Runtime()
    result = RemoteMedia(runtime).show("demo", "sha256:object")

    assert result.ok
    assert result.data == {
        "object_id": "sha256:object",
        "digest": "sha256:object",
        "media_type": "image/png",
        "size": 3,
        "version": 1,
        "created_at": "2026-09-01T00:00:00Z",
        "filename": "shot.png",
    }
    assert runtime.downloads == 0

    envelope = json.loads(render_envelope_json(result))
    assert set(envelope) == {"ok", "data", "error", "receipt", "idempotency_key"}
    assert envelope["data"]["object_id"] == "sha256:object"
