"""banodoco-worker — long-running poll loop for `banodoco_timeline_generate`.

Lifecycle (SD-035):

    boot
      └─ load env, configure logging, init readiness tracker
    ready
      └─ /healthz starts returning 200 once theme packages + shared libs
         imported cleanly; orchestrator can begin assigning work.
    claim
      └─ poll the orchestrator's claim endpoint with worker_pool=banodoco
         and run_type=banodoco-worker.
    execute
      └─ verify JWT (worker_jwt), verify project ownership, run pipeline,
         validate strict.
    write
      └─ apply versioned RPC; on 409 check correlation_id; emit
         WriteResult.
    complete
      └─ post task-completion (or task-failure) to orchestrator.

Environment:

    REIGH_SUPABASE_URL
    REIGH_SUPABASE_SERVICE_ROLE_KEY    — service-role for the audited DB call
    REIGH_SUPABASE_JWT_AUDIENCE         — defaults to "authenticated"
    ORCHESTRATOR_BASE_URL               — orchestrator HTTP root
                                            (e.g. https://orchestrator.up.railway.app)
    BANODOCO_WORKER_ID                  — unique worker id for claim
    BANODOCO_WORKER_POOL                — defaults to "banodoco"
    BANODOCO_PARENT_POLL_SEC            — claim poll cadence (default 5)
    WORKER_HEALTH_HOST / WORKER_HEALTH_PORT
    BANODOCO_PIPELINE_TIMEOUT_SEC       — pipeline subprocess kill timeout
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

import httpx

# Local imports — keep them after stdlib for clarity in tracebacks.
from worker_health import (
    WorkerReadiness,
    detect_readiness,
    start_health_server,
)
from worker_jwt import JwtVerificationError, verify_user_jwt
from worker_pipeline import PipelineError, run_pipeline, validate_timeline_strict
from worker_render import execute_render_task
from worker_writes import (
    SupabaseTimelineRpc,
    WriteResult,
    apply_versioned_write_with_correlation_retry,
)


logger = logging.getLogger("banodoco_worker")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


RUN_TYPE = os.getenv("BANODOCO_WORKER_RUN_TYPE", "banodoco-worker")
WORKER_POOL = os.getenv("BANODOCO_WORKER_POOL", "banodoco")
WORKER_ID = os.getenv("BANODOCO_WORKER_ID", "banodoco-worker-main")
PARENT_POLL_SEC = int(os.getenv("BANODOCO_PARENT_POLL_SEC", "5"))


# ---------------------------------------------------------------------------
# Orchestrator interaction
# ---------------------------------------------------------------------------


def _orchestrator_url(path: str) -> str:
    base = os.getenv("ORCHESTRATOR_BASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("ORCHESTRATOR_BASE_URL is required")
    return f"{base}{path}"


async def _claim_next_task(client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {os.getenv('REIGH_SUPABASE_SERVICE_ROLE_KEY', '')}",
        "Content-Type": "application/json",
    }
    payload = {
        "worker_id": WORKER_ID,
        "run_type": RUN_TYPE,
        "worker_pool": WORKER_POOL,
        # Sprint 7 = generate. Sprint 8 added render. Same image, same pool,
        # both task types claimable. The dispatch in _execute_task picks
        # the right entry-point function based on `task_type`.
        "task_types": [
            "banodoco_timeline_generate",
            "banodoco_render_timeline",
        ],
    }
    try:
        resp = await client.post(
            _orchestrator_url("/functions/v1/claim-next-task"),
            headers=headers,
            json=payload,
            timeout=30,
        )
    except httpx.HTTPError as exc:
        logger.warning("[CLAIM] orchestrator unreachable: %s", exc)
        return None

    if resp.status_code == 204:
        return None
    if resp.status_code != 200:
        logger.warning("[CLAIM] non-200 from orchestrator: %s %s", resp.status_code, resp.text[:300])
        return None
    try:
        return resp.json()
    except ValueError:
        logger.warning("[CLAIM] orchestrator returned non-JSON")
        return None


async def _post_task_status(
    client: httpx.AsyncClient,
    task_id: str,
    status: str,
    *,
    correlation_id: str,
    new_version: Optional[int] = None,
    result: Optional[Dict[str, Any]] = None,
    failure_code: Optional[str] = None,
    message: Optional[str] = None,
) -> None:
    """Post task status to the orchestrator.

    Sprint 7 only ever set ``result = {"config_version": new_version}``.
    Sprint 8 also needs to surface ``{"artifact_url": ..., "content_sha256": ...}``
    for render tasks, so the helper now accepts an explicit ``result``
    dict; ``new_version`` is kept as a convenience for the generate path
    so call sites don't change.
    """
    headers = {
        "Authorization": f"Bearer {os.getenv('REIGH_SUPABASE_SERVICE_ROLE_KEY', '')}",
        "Content-Type": "application/json",
    }
    body: Dict[str, Any] = {
        "task_id": task_id,
        "status": status,
        "correlation_id": correlation_id,
    }
    if result is not None:
        body["result"] = result
    elif new_version is not None:
        body["result"] = {"config_version": new_version}
    if failure_code:
        body["failure_code"] = failure_code
    if message:
        body["message"] = message[:500]

    endpoint = "/functions/v1/complete_task" if status == "Complete" else "/functions/v1/update-task-status"
    try:
        await client.post(_orchestrator_url(endpoint), headers=headers, json=body, timeout=15)
    except httpx.HTTPError as exc:
        logger.error("[STATUS] failed to post status %s for %s: %s", status, task_id, exc)


# ---------------------------------------------------------------------------
# Per-task execution
# ---------------------------------------------------------------------------


async def _execute_task(client: httpx.AsyncClient, task: Dict[str, Any]) -> None:
    """Dispatch a claimed task to the right entry point based on task_type.

    Sprint 7: only `banodoco_timeline_generate` was supported.
    Sprint 8: `banodoco_render_timeline` runs through `worker_render`.
    Unknown task_type → log + post invalid_payload (the orchestrator
    shouldn't ever hand the worker a type it didn't claim, but defend
    in depth).
    """
    task_type = task.get("task_type") or "banodoco_timeline_generate"
    if task_type == "banodoco_render_timeline":
        await execute_render_task(client, task, post_status=_post_task_status)
        return
    if task_type != "banodoco_timeline_generate":
        task_id = task.get("task_id") or task.get("id") or "unknown"
        logger.error("[EXEC %s] unsupported task_type=%s", task_id, task_type)
        await _post_task_status(
            client,
            task_id,
            "Failed",
            correlation_id="",
            failure_code="invalid_payload",
            message=f"unsupported task_type {task_type!r}",
        )
        return
    await _execute_generate_task(client, task)


async def _execute_generate_task(client: httpx.AsyncClient, task: Dict[str, Any]) -> None:
    task_id = task.get("task_id") or task.get("id") or "unknown"
    params = task.get("params") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError as exc:
            logger.error("[EXEC %s] params JSON parse failed: %s", task_id, exc)
            return

    correlation_id = params.get("correlation_id", "")
    timeline_id = params.get("timeline_id", "")
    project_id = params.get("project_id", "")
    expected_version = params.get("expected_version")
    user_jwt = params.get("user_jwt", "")

    if not all([correlation_id, timeline_id, project_id, isinstance(expected_version, int), user_jwt]):
        await _post_task_status(
            client,
            task_id,
            "Failed",
            correlation_id=correlation_id or "",
            failure_code="invalid_payload",
            message="missing required SD-034 fields",
        )
        return

    # 1) Verify JWT
    try:
        verified = verify_user_jwt(user_jwt)
    except JwtVerificationError as exc:
        logger.warning("[EXEC %s] JWT rejection: %s", task_id, exc)
        await _post_task_status(
            client,
            task_id,
            "Failed",
            correlation_id=correlation_id,
            failure_code="auth_failed",
            message=str(exc),
        )
        return

    # 2) Verify project ownership (service-role read of projects.user_id).
    rpc = SupabaseTimelineRpc(audited_user_id=verified.user_id)
    try:
        owner_ok = _verify_project_ownership(rpc, project_id, verified.user_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("[EXEC %s] ownership check failed: %s", task_id, exc)
        await _post_task_status(
            client,
            task_id,
            "Failed",
            correlation_id=correlation_id,
            failure_code="ownership_check_failed",
            message=str(exc),
        )
        return
    if not owner_ok:
        await _post_task_status(
            client,
            task_id,
            "Failed",
            correlation_id=correlation_id,
            failure_code="auth_failed",
            message="project does not belong to JWT subject",
        )
        return

    # 3) Run pipeline + validate.
    try:
        pipeline_result = run_pipeline(
            intent=params.get("intent", ""),
            brief_inputs=params.get("brief_inputs", {}),
            theme_id=params.get("theme_id", ""),
            current_timeline=params.get("current_timeline"),
        )
        validate_timeline_strict(pipeline_result.config)
    except PipelineError as exc:
        logger.error("[EXEC %s] pipeline failure: %s", task_id, exc)
        await _post_task_status(
            client,
            task_id,
            "Failed",
            correlation_id=correlation_id,
            failure_code="pipeline_failure",
            message=str(exc),
        )
        return

    # 4) Versioned write with correlation_id retry.
    write_result: WriteResult = apply_versioned_write_with_correlation_retry(
        rpc=rpc,
        timeline_id=timeline_id,
        expected_version=expected_version,
        config=pipeline_result.config,
        correlation_id=correlation_id,
    )

    if write_result.status == "completed":
        await _post_task_status(
            client,
            task_id,
            "Complete",
            correlation_id=correlation_id,
            new_version=write_result.new_version,
            message=write_result.message or "TimelineConfig written",
        )
        return
    if write_result.status == "version_conflict":
        await _post_task_status(
            client,
            task_id,
            "Failed",
            correlation_id=correlation_id,
            failure_code="version_conflict",
            message=write_result.message,
        )
        return

    # rpc_failure
    await _post_task_status(
        client,
        task_id,
        "Failed",
        correlation_id=correlation_id,
        failure_code="rpc_failure",
        message=write_result.message,
    )


def _verify_project_ownership(
    rpc: SupabaseTimelineRpc, project_id: str, user_id: str
) -> bool:
    """Service-role read of projects.user_id; service-role identity is used
    for the call but the audit trail records `user_id` as the actor."""
    result = (
        rpc._client.table("projects")  # noqa: SLF001 — intentional reuse
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
# Main loop
# ---------------------------------------------------------------------------


async def main_async() -> None:
    readiness = WorkerReadiness()
    runner = await start_health_server(readiness)
    detect_readiness(readiness)
    if not readiness.ready:
        logger.error("[BOOT] readiness checks failed; staying up so /healthz reports 503")
    else:
        logger.info("[BOOT] worker is ready; starting claim loop")

    async with httpx.AsyncClient(timeout=30) as client:
        readiness.orchestrator_reachable = True
        try:
            while True:
                if not readiness.ready:
                    await asyncio.sleep(PARENT_POLL_SEC)
                    continue
                task = await _claim_next_task(client)
                if not task:
                    await asyncio.sleep(PARENT_POLL_SEC)
                    continue
                logger.info("[LOOP] claimed task %s", task.get("task_id"))
                try:
                    await _execute_task(client, task)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("[LOOP] unhandled exception while executing task: %s", exc)
        finally:
            await runner.cleanup()


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
