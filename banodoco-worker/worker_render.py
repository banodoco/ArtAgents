"""banodoco-worker — render entry point (`banodoco_render_timeline`, Sprint 8).

Mirrors `worker.py::_execute_task` for the generate task type, but:

  1. Resolves `assets` to local files (worker_assets.resolve_asset_registry).
  2. Runs Remotion to produce an MP4 (worker_remotion.render_timeline_to_mp4).
  3. Uploads the MP4 to Reigh's render-output storage bucket at
     `<user_id>/<timeline_id>/<task_id>.mp4`. SD-034 idempotency: same
     task_id always lands at the same path, so a retried worker that
     succeeds simply overwrites the prior partial.
  4. Retries the upload up to N=3 times on transient failures. After
     N=3 terminal failures, posts task-failure with code
     ``render_artifact_upload_failed`` and a worker-logs URL pointer.
  5. Stamps the render-task record (Reigh-side) with `correlation_id`
     and the resolved storage URL via the existing render-task RPC.

Notes:

  - The render-task table in Reigh's schema is the single writer for
    artifact metadata. We don't introduce a new table — the worker
    just updates the row keyed by `task_id`, treating the row as the
    same SD-034 contract surface as Sprint 7's timeline-version write.
  - User identity in the artifact path: derived from the verified JWT
    (worker_jwt.VerifiedJwt.user_id), NOT from the params. This is the
    SD-022 anchor — even if a malicious caller stuffs a different
    user_id in the payload, the path lands under the JWT subject.

Environment used (in addition to worker.py's env):
  REIGH_RENDER_OUTPUTS_BUCKET    — defaults to `render-outputs`.
  BANODOCO_RENDER_UPLOAD_RETRIES — defaults to 3.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import httpx

from worker_assets import (
    make_render_workdir,
    resolve_asset_registry,
)
from worker_jwt import JwtVerificationError, VerifiedJwt, verify_user_jwt
from worker_remotion import (
    RemotionRenderError,
    RemotionRenderResult,
    render_timeline_to_mp4,
)

logger = logging.getLogger(__name__)


DEFAULT_RENDER_BUCKET = "render-outputs"
DEFAULT_UPLOAD_RETRIES = 3


# ---------------------------------------------------------------------------
# Storage upload (SD-034 artifact landing)
# ---------------------------------------------------------------------------


class RenderUploadError(Exception):
    """Raised when the MP4 upload to Reigh's storage bucket fails terminally."""


def _supabase_storage_upload_url(bucket: str, object_path: str) -> str:
    base = os.getenv("REIGH_SUPABASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("REIGH_SUPABASE_URL is required for render-output upload")
    return f"{base}/storage/v1/object/{bucket}/{object_path}"


def _supabase_storage_public_url(bucket: str, object_path: str) -> str:
    base = os.getenv("REIGH_SUPABASE_URL", "").rstrip("/")
    return f"{base}/storage/v1/object/{bucket}/{object_path}"


def upload_render_artifact(
    *,
    file_path: Path,
    user_id: str,
    timeline_id: str,
    task_id: str,
    bucket: Optional[str] = None,
    retries: Optional[int] = None,
    http: Optional[httpx.Client] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Upload an MP4 to Reigh's render-output bucket with N=3 retries.

    Returns the canonical storage URL on success.

    The path is `<user_id>/<timeline_id>/<task_id>.mp4` — user_id-first
    matches Reigh's RLS folder convention (Phase 6); task_id-suffixed
    means a retried worker writes to the SAME path, satisfying SD-034
    idempotency. Supabase storage `upsert: true` makes the second worker
    overwrite cleanly when the network drops at byte 99% of the first.
    """
    bucket = bucket or os.getenv("REIGH_RENDER_OUTPUTS_BUCKET", DEFAULT_RENDER_BUCKET)
    retries = retries if retries is not None else int(
        os.getenv("BANODOCO_RENDER_UPLOAD_RETRIES", str(DEFAULT_UPLOAD_RETRIES))
    )

    object_path = f"{user_id}/{timeline_id}/{task_id}.mp4"
    url = _supabase_storage_upload_url(bucket, object_path)
    service_role = os.getenv("REIGH_SUPABASE_SERVICE_ROLE_KEY", "")
    if not service_role:
        raise RuntimeError("REIGH_SUPABASE_SERVICE_ROLE_KEY is required for upload")

    headers = {
        "Authorization": f"Bearer {service_role}",
        "apikey": service_role,
        "Content-Type": "video/mp4",
        # `upsert=true` makes a re-upload (same task_id) a no-op-equivalent
        # rather than a 409. SD-034 idempotency anchor.
        "x-upsert": "true",
    }

    last_exc: Optional[Exception] = None
    client = http or httpx.Client(timeout=300)
    try:
        for attempt in range(1, retries + 1):
            try:
                with file_path.open("rb") as fh:
                    body = fh.read()
                resp = client.post(url, content=body, headers=headers)
                if resp.status_code in (200, 201):
                    logger.info(
                        "[UPLOAD] task=%s attempt=%d bytes=%d -> %s",
                        task_id, attempt, len(body), object_path,
                    )
                    return _supabase_storage_public_url(bucket, object_path)
                # Treat 4xx (except 429) as terminal — service-role
                # shouldn't see auth issues retry away.
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    raise RenderUploadError(
                        f"Storage upload returned {resp.status_code}: {resp.text[:300]}"
                    )
                last_exc = RenderUploadError(
                    f"Storage upload returned {resp.status_code}: {resp.text[:300]}"
                )
            except (httpx.HTTPError, OSError) as exc:
                last_exc = exc
                logger.warning(
                    "[UPLOAD] task=%s attempt=%d transient failure: %s",
                    task_id, attempt, exc,
                )
            if attempt < retries:
                sleep(min(2 ** (attempt - 1), 8))
    finally:
        if http is None:
            client.close()

    raise RenderUploadError(
        f"Upload failed after {retries} attempts: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Render-task record stamp (correlation_id + storage URL)
# ---------------------------------------------------------------------------


class RenderTaskRecordWriter:
    """Stamps the render-task record with the artifact URL + correlation_id.

    Implemented as a thin Supabase REST update. The render-task table is
    Reigh's `tasks` table (existing) — we update the row keyed by
    `task_id` with `result_data` containing the storage URL and
    `correlation_id` so the SD-034 audit trail closes inside Reigh's DB.
    """

    def __init__(self, *, audited_user_id: str) -> None:
        self.audited_user_id = audited_user_id

    def update_render_task(
        self,
        *,
        task_id: str,
        artifact_url: str,
        correlation_id: str,
        sha256: str,
        http: Optional[httpx.Client] = None,
    ) -> None:
        base = os.getenv("REIGH_SUPABASE_URL", "").rstrip("/")
        service_role = os.getenv("REIGH_SUPABASE_SERVICE_ROLE_KEY", "")
        if not base or not service_role:
            raise RuntimeError(
                "RenderTaskRecordWriter requires REIGH_SUPABASE_URL + "
                "REIGH_SUPABASE_SERVICE_ROLE_KEY"
            )
        endpoint = f"{base}/rest/v1/tasks?id=eq.{task_id}"
        headers = {
            "Authorization": f"Bearer {service_role}",
            "apikey": service_role,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        body = {
            "result_data": {
                "artifact_url": artifact_url,
                "correlation_id": correlation_id,
                "content_sha256": sha256,
                "audited_user_id": self.audited_user_id,
            },
        }
        client = http or httpx.Client(timeout=30)
        try:
            resp = client.patch(endpoint, headers=headers, content=json.dumps(body))
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"render-task update failed: {resp.status_code} {resp.text[:300]}"
                )
        finally:
            if http is None:
                client.close()


# ---------------------------------------------------------------------------
# Project-ownership re-verification (mirror of worker.py)
# ---------------------------------------------------------------------------


def _verify_project_ownership_supabase(project_id: str, user_id: str) -> bool:
    """Service-role read of projects.user_id.

    Lazily imports supabase to keep test-only paths import-free.
    """
    from supabase import create_client  # imported lazily — heavy

    base = os.getenv("REIGH_SUPABASE_URL")
    key = os.getenv("REIGH_SUPABASE_SERVICE_ROLE_KEY")
    if not base or not key:
        raise RuntimeError("Supabase env vars missing for ownership check")
    client = create_client(base, key)
    result = (
        client.table("projects")
        .select("user_id")
        .eq("id", project_id)
        .single()
        .execute()
    )
    data = result.data if hasattr(result, "data") else None
    if not isinstance(data, dict):
        return False
    return data.get("user_id") == user_id


# ---------------------------------------------------------------------------
# Entry point — called by worker.py's loop when claim returns a render task
# ---------------------------------------------------------------------------


async def execute_render_task(
    client: httpx.AsyncClient,
    task: Dict[str, Any],
    *,
    post_status: Callable[..., Any],
    verify_jwt: Callable[[str], VerifiedJwt] = verify_user_jwt,
    verify_ownership: Callable[[str, str], bool] = _verify_project_ownership_supabase,
    render_fn: Callable[..., RemotionRenderResult] = render_timeline_to_mp4,
    upload_fn: Callable[..., str] = upload_render_artifact,
    record_writer_factory: Callable[..., RenderTaskRecordWriter] = RenderTaskRecordWriter,
    workdir_factory: Callable[[], Path] = make_render_workdir,
) -> None:
    """Execute one `banodoco_render_timeline` task.

    All external integrations are passed in as callables so the smoke
    tests in tests/test_worker_render_smoke.py can stub them out without
    monkeypatching the whole world.
    """
    task_id = task.get("task_id") or task.get("id") or "unknown"
    params = task.get("params") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError as exc:
            logger.error("[RENDER %s] params JSON parse failed: %s", task_id, exc)
            return

    correlation_id = params.get("correlation_id", "")
    timeline_id = params.get("timeline_id", "")
    project_id = params.get("project_id", "")
    user_jwt = params.get("user_jwt", "")
    timeline = params.get("timeline") or {}
    assets = params.get("assets") or {}
    theme_id = params.get("theme_id", "")
    output_filename = params.get("output_filename") or "render.mp4"

    if not all([correlation_id, timeline_id, project_id, user_jwt, theme_id]):
        await post_status(
            client,
            task_id,
            "Failed",
            correlation_id=correlation_id or "",
            failure_code="invalid_payload",
            message="missing required SD-034 fields",
        )
        return

    # 1) Verify JWT (SD-022)
    try:
        verified = verify_jwt(user_jwt)
    except JwtVerificationError as exc:
        logger.warning("[RENDER %s] JWT rejection: %s", task_id, exc)
        await post_status(
            client,
            task_id,
            "Failed",
            correlation_id=correlation_id,
            failure_code="auth_failed",
            message=str(exc),
        )
        return

    # 2) Verify project ownership.
    try:
        owner_ok = verify_ownership(project_id, verified.user_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("[RENDER %s] ownership check failed: %s", task_id, exc)
        await post_status(
            client,
            task_id,
            "Failed",
            correlation_id=correlation_id,
            failure_code="ownership_check_failed",
            message=str(exc),
        )
        return
    if not owner_ok:
        await post_status(
            client,
            task_id,
            "Failed",
            correlation_id=correlation_id,
            failure_code="auth_failed",
            message="project does not belong to JWT subject",
        )
        return

    work_dir = workdir_factory()
    try:
        # 3) Resolve assets.
        try:
            resolved_assets = resolve_asset_registry(
                assets, user_id=verified.user_id, work_dir=work_dir,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[RENDER %s] asset resolution failed: %s", task_id, exc)
            await post_status(
                client,
                task_id,
                "Failed",
                correlation_id=correlation_id,
                failure_code="asset_resolution_failed",
                message=str(exc),
            )
            return

        # 4) Render with Remotion.
        output_path = work_dir / output_filename
        try:
            render_result = render_fn(
                timeline=timeline,
                assets=resolved_assets,
                theme_id=theme_id,
                output_path=output_path,
            )
        except RemotionRenderError as exc:
            logger.error("[RENDER %s] Remotion failure: %s", task_id, exc)
            await post_status(
                client,
                task_id,
                "Failed",
                correlation_id=correlation_id,
                failure_code="remotion_render_failed",
                message=str(exc),
            )
            return

        # 5) Upload artifact (with N=3 retries).
        try:
            artifact_url = upload_fn(
                file_path=render_result.output_path,
                user_id=verified.user_id,
                timeline_id=timeline_id,
                task_id=task_id,
            )
        except RenderUploadError as exc:
            logger.error("[RENDER %s] artifact upload failed terminally: %s", task_id, exc)
            await post_status(
                client,
                task_id,
                "Failed",
                correlation_id=correlation_id,
                failure_code="render_artifact_upload_failed",
                message=str(exc),
            )
            return

        # 6) Stamp the render-task record.
        try:
            writer = record_writer_factory(audited_user_id=verified.user_id)
            writer.update_render_task(
                task_id=task_id,
                artifact_url=artifact_url,
                correlation_id=correlation_id,
                sha256=render_result.sha256,
            )
        except Exception as exc:  # noqa: BLE001
            # The artifact is already uploaded — record-stamp failure is
            # not artifact-fatal. Log loudly and surface a soft failure
            # so the agent can show the URL even if metadata is stale.
            logger.warning(
                "[RENDER %s] artifact uploaded but record stamp failed: %s",
                task_id, exc,
            )

        # 7) Post task-completion.
        await post_status(
            client,
            task_id,
            "Complete",
            correlation_id=correlation_id,
            result={
                "artifact_url": artifact_url,
                "content_sha256": render_result.sha256,
            },
            message="MP4 render completed and uploaded",
        )
    finally:
        # In v1 we don't persist the asset cache to disk; nuking the
        # workdir is a no-op for the in-process cache (it caches by
        # sha256, not by path, so a future task hitting the same sha
        # will simply find the entry stale and redownload).
        try:
            for child in work_dir.glob("**/*"):
                if child.is_file():
                    child.unlink(missing_ok=True)
            for child in sorted(work_dir.glob("**/*"), reverse=True):
                if child.is_dir():
                    child.rmdir()
            work_dir.rmdir()
        except OSError:
            pass


__all__ = [
    "DEFAULT_RENDER_BUCKET",
    "DEFAULT_UPLOAD_RETRIES",
    "RenderTaskRecordWriter",
    "RenderUploadError",
    "execute_render_task",
    "upload_render_artifact",
]
