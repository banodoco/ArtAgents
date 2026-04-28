"""Sprint 8: upload retry semantics.

Two scenarios per the sprint brief:
  1. Upload fails twice then succeeds → task-completion lands.
  2. Upload fails 3× → task-failure with `render_artifact_upload_failed`.

The retry helper itself is the test surface; the smoke test already
covers the happy task lifecycle.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from worker_render import RenderUploadError, upload_render_artifact


def _stub_response(status_code: int, text: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


def test_upload_succeeds_after_two_transient_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("REIGH_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("REIGH_SUPABASE_SERVICE_ROLE_KEY", "service-role")

    file_path = tmp_path / "out.mp4"
    file_path.write_bytes(b"render-bytes")

    http = MagicMock()
    http.post.side_effect = [
        httpx.ConnectError("network blip"),
        _stub_response(500, "transient"),
        _stub_response(200),
    ]

    sleeps = []
    url = upload_render_artifact(
        file_path=file_path,
        user_id="user-1",
        timeline_id="t-1",
        task_id="task-9",
        retries=3,
        http=http,
        sleep=lambda s: sleeps.append(s),
    )
    assert url.endswith("user-1/t-1/task-9.mp4")
    assert http.post.call_count == 3
    # Two retries → two backoff sleeps.
    assert len(sleeps) == 2


def test_upload_fails_terminally_after_three_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("REIGH_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("REIGH_SUPABASE_SERVICE_ROLE_KEY", "service-role")

    file_path = tmp_path / "out.mp4"
    file_path.write_bytes(b"render-bytes")

    http = MagicMock()
    http.post.side_effect = [
        _stub_response(503, "still down"),
        _stub_response(503, "still down"),
        _stub_response(503, "still down"),
    ]

    with pytest.raises(RenderUploadError) as exc:
        upload_render_artifact(
            file_path=file_path,
            user_id="user-1",
            timeline_id="t-1",
            task_id="task-9",
            retries=3,
            http=http,
            sleep=lambda s: None,
        )
    assert "after 3 attempts" in str(exc.value)
    assert http.post.call_count == 3


def test_upload_fails_immediately_on_4xx_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("REIGH_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("REIGH_SUPABASE_SERVICE_ROLE_KEY", "service-role")

    file_path = tmp_path / "out.mp4"
    file_path.write_bytes(b"render-bytes")

    http = MagicMock()
    http.post.side_effect = [_stub_response(403, "forbidden")]

    with pytest.raises(RenderUploadError) as exc:
        upload_render_artifact(
            file_path=file_path,
            user_id="user-1",
            timeline_id="t-1",
            task_id="task-9",
            retries=3,
            http=http,
            sleep=lambda s: None,
        )
    # Service-role should never see 403 — surface it immediately rather
    # than burning two more retries.
    assert "403" in str(exc.value)
    assert http.post.call_count == 1
