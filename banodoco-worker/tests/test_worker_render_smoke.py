"""Sprint 8 smoke: synthetic render task → mocked downloads → mocked
Remotion → mocked upload → assert task-completion posted with correct URL."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from worker_jwt import VerifiedJwt
from worker_remotion import RemotionRenderResult
from worker_render import execute_render_task


CORR_ID = "55555555-5555-5555-5555-555555555555"
TIMELINE_ID = "11111111-1111-1111-1111-11111111aaaa"
PROJECT_ID = "22222222-2222-2222-2222-22222222bbbb"
TASK_ID = "task-99"
USER_ID = "user-abc"


def _synthetic_task() -> Dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "task_type": "banodoco_render_timeline",
        "params": {
            "timeline_id": TIMELINE_ID,
            "project_id": PROJECT_ID,
            "correlation_id": CORR_ID,
            "user_jwt": "synthetic-jwt",
            "theme_id": "2rp",
            "output_filename": "hype-reel.mp4",
            "timeline": {"clips": [], "tracks": [], "theme": "2rp"},
            "assets": {"assets": {"a": {"url": "https://cdn.example.com/a.mp4"}}},
        },
    }


def test_smoke_render_completes_with_artifact_url(tmp_path: Path):
    posted: Dict[str, Any] = {}

    async def post_status(client, task_id, status, **kwargs):  # noqa: ANN001
        posted["task_id"] = task_id
        posted["status"] = status
        posted["kwargs"] = kwargs

    def fake_render(*, timeline, assets, theme_id, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-mp4")
        return RemotionRenderResult(output_path=output_path, sha256="cafebabe")

    upload_calls = []

    def fake_upload(*, file_path, user_id, timeline_id, task_id, **kwargs):  # noqa: ARG001
        upload_calls.append({
            "user_id": user_id,
            "timeline_id": timeline_id,
            "task_id": task_id,
            "size": file_path.stat().st_size,
        })
        return f"https://example.supabase.co/storage/v1/object/render-outputs/{user_id}/{timeline_id}/{task_id}.mp4"

    record_writer = MagicMock()
    record_writer.update_render_task = MagicMock()

    asyncio.run(
        execute_render_task(
            client=MagicMock(),
            task=_synthetic_task(),
            post_status=post_status,
            verify_jwt=lambda jwt: VerifiedJwt(user_id=USER_ID, audience="authenticated", raw_claims={}),
            verify_ownership=lambda pid, uid: True,
            render_fn=fake_render,
            upload_fn=fake_upload,
            record_writer_factory=lambda **kwargs: record_writer,
            workdir_factory=lambda: tmp_path / "render-job",
        )
    )

    assert posted["task_id"] == TASK_ID
    assert posted["status"] == "Complete"
    assert posted["kwargs"]["correlation_id"] == CORR_ID
    result = posted["kwargs"]["result"]
    assert result["artifact_url"].endswith(f"{USER_ID}/{TIMELINE_ID}/{TASK_ID}.mp4")
    assert result["content_sha256"] == "cafebabe"

    # The upload was called once with SD-034 path naming.
    assert upload_calls[0]["user_id"] == USER_ID
    assert upload_calls[0]["timeline_id"] == TIMELINE_ID
    assert upload_calls[0]["task_id"] == TASK_ID

    # The render-task record was stamped with correlation_id.
    record_writer.update_render_task.assert_called_once()
    stamp_kwargs = record_writer.update_render_task.call_args.kwargs
    assert stamp_kwargs["task_id"] == TASK_ID
    assert stamp_kwargs["correlation_id"] == CORR_ID
    assert stamp_kwargs["sha256"] == "cafebabe"


def test_smoke_invalid_payload_surfaces_failure(tmp_path: Path):
    posted: Dict[str, Any] = {}

    async def post_status(client, task_id, status, **kwargs):  # noqa: ANN001
        posted.update(task_id=task_id, status=status, **kwargs)

    task = _synthetic_task()
    del task["params"]["correlation_id"]

    asyncio.run(
        execute_render_task(
            client=MagicMock(),
            task=task,
            post_status=post_status,
            verify_jwt=lambda jwt: VerifiedJwt(user_id=USER_ID, audience="authenticated", raw_claims={}),
            verify_ownership=lambda pid, uid: True,
            workdir_factory=lambda: tmp_path / "render-job",
        )
    )
    assert posted["status"] == "Failed"
    assert posted["failure_code"] == "invalid_payload"


def test_smoke_ownership_mismatch_surfaces_auth_failed(tmp_path: Path):
    posted: Dict[str, Any] = {}

    async def post_status(client, task_id, status, **kwargs):  # noqa: ANN001
        posted.update(task_id=task_id, status=status, **kwargs)

    asyncio.run(
        execute_render_task(
            client=MagicMock(),
            task=_synthetic_task(),
            post_status=post_status,
            verify_jwt=lambda jwt: VerifiedJwt(user_id=USER_ID, audience="authenticated", raw_claims={}),
            verify_ownership=lambda pid, uid: False,
            workdir_factory=lambda: tmp_path / "render-job",
        )
    )
    assert posted["status"] == "Failed"
    assert posted["failure_code"] == "auth_failed"
    assert posted["correlation_id"] == CORR_ID
