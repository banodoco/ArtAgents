"""Astrid banodoco worker pool implementation.

Resolution of open contracts (citations are intentionally repeated here so the
worker file is auditable in isolation):

* **Contract #1 — claim-next-task body**:
  ``banodoco-worker/worker.py:88-130`` POSTs
  ``{worker_id, run_type:"banodoco-worker", worker_pool:"banodoco",
    task_types:[...]}``. AA's :mod:`astrid.core.integrations.reigh.task_client` mirrors
  that exactly; this worker calls into it.

* **Contract #2 — JWT + service-role split**:
  ``banodoco-worker/worker_jwt.py`` verifies the user JWT against the Reigh
  Supabase JWKS for *identity*. The reference worker then does an explicit
  service-role read of ``projects.user_id`` (``_verify_project_ownership``)
  before any service-role write — JWKS verification alone does NOT prove
  project ownership. This worker honours that contract via
  :func:`_verify_project_ownership`.

* **Contract #4 — update-task-status with result_data**: reigh-app commit
  ``ee2e6f10c`` added a ``task-status`` GET endpoint that surfaces
  ``tasks.result_data`` to the UI poller. AA's worker writes
  ``result_data={config_version, correlation_id, timeline_id}`` on success and
  ``{correlation_id}`` on failure via :mod:`astrid.core.integrations.reigh.task_client`'s
  ``update_task_status``. AA NEVER calls ``/functions/v1/complete-task`` and
  NEVER calls ``/functions/v1/task-status``.

Status enum casing is Title Case ONLY (``Queued | In Progress | Complete |
Failed | Cancelled``). All emitted clips carry the SD-003 fields ``source_uuid,
generation, pool_id, clip_order`` — there is no new structured ``source: ...``
field. SD-008 baseline_snapshot is a sha256 hex string written at exactly
``runs/<run_id>.json#metadata.baseline_snapshot``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from astrid.core.contracts.run_status import RunStatus
from astrid.core.project.run import write_run_record
from astrid.core.integrations.reigh import env as reigh_env
from astrid.core.integrations.reigh.data_provider import SupabaseDataProvider
from astrid.core.integrations.reigh.task_client import (
    SUPPORTED_TASK_TYPES,
    ClaimResult,
    claim_next_task,
    update_task_status,
)
from astrid.core.integrations.reigh.timeline_io import Mutator
from astrid.core.integrations.reigh.timeline_io import RawTimelinePayload as TimelineConfig
from astrid.core.integrations.reigh.worker_jwt import JwtVerificationError, VerifiedJwt, verify_user_jwt

logger = logging.getLogger(__name__)


CARRY_FIELDS: tuple[str, ...] = ("source_uuid", "generation", "pool_id", "clip_order")


class DispatchError(RuntimeError):
    """Raised when intent dispatch cannot produce a mutator."""


class ProjectOwnershipError(RuntimeError):
    """Raised when projects.user_id does not match the verified JWT subject."""


class IntentDispatcher(Protocol):
    """Maps a task envelope to a timeline mutator."""

    def __call__(
        self,
        *,
        intent: str,
        params: Mapping[str, Any],
        verified: VerifiedJwt,
    ) -> Mutator:
        ...


@dataclass
class WorkerConfig:
    """Runtime knobs for the banodoco worker."""

    worker_id: str = field(default_factory=lambda: f"aa-worker-{uuid.uuid4().hex[:8]}")
    poll_interval_sec: float = 5.0
    idle_sleep_sec: float = 5.0
    max_iterations: int | None = None  # None = run forever
    project_slug: str | None = None  # for runs/ provenance cache


def canonical_json(payload: Any) -> str:
    """Stable JSON encoding used for SD-008 baseline_snapshot hashing."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_carry_fields(clips: Any) -> None:
    """Populate the SD-003 carry-fields on every emitted clip dict.

    Defaults:
      * ``source_uuid`` — generated if missing (per-clip uuid4 hex).
      * ``generation`` — defaults to ``{}``.
      * ``pool_id`` — defaults to ``"default"`` if missing.
      * ``clip_order`` — defaults to the clip's index if missing.
    """

    if not isinstance(clips, list):
        return
    for index, clip in enumerate(clips):
        if not isinstance(clip, dict):
            continue
        if "source_uuid" not in clip or not clip.get("source_uuid"):
            clip["source_uuid"] = uuid.uuid4().hex
        clip.setdefault("generation", {})
        if "pool_id" not in clip or not clip.get("pool_id"):
            clip["pool_id"] = "default"
        if "clip_order" not in clip or not isinstance(clip.get("clip_order"), int):
            clip["clip_order"] = index


def _verify_project_ownership(
    *,
    provider: SupabaseDataProvider,
    project_id: str,
    verified: VerifiedJwt,
    service_role_key: str,
) -> None:
    """Service-role read of projects.user_id; gate the write on a match.

    Mirrors ``banodoco-worker/worker.py``'s ``_verify_project_ownership``
    (FLAG-013). This is REQUIRED — the JWKS-verified user JWT proves identity
    but not ownership; without this check the service-role RPC could be
    abused to write any project.
    """

    rest = f"{provider.supabase_url.rstrip('/')}/rest/v1/projects?id=eq.{project_id}&select=user_id"
    import urllib.request as _request

    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
        "Accept": "application/json",
    }
    request = _request.Request(rest, headers=headers, method="GET")
    with _request.urlopen(request, timeout=provider.timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ProjectOwnershipError(
            f"projects row {project_id} not found via service-role read"
        )
    row = payload[0]
    owner = row.get("user_id") if isinstance(row, dict) else None
    if not isinstance(owner, str) or owner != verified.user_id:
        raise ProjectOwnershipError(
            f"project ownership mismatch: project_id={project_id} owner={owner!r} "
            f"verified={verified.user_id!r}"
        )


def _write_baseline_snapshot(
    *,
    project_slug: str | None,
    run_id: str,
    payload: Any,
) -> str | None:
    """Write SD-008 ``runs/<run_id>.json#metadata.baseline_snapshot`` and return the hash."""

    digest = sha256_hex(canonical_json(payload))
    if not project_slug:
        # None reserved ONLY for "no project slug configured" — failures
        # below must propagate so the claim loop can mark the task Failed
        # rather than silently recording a success-shaped digest.
        return None
    run_record = write_run_record(
        project_slug,
        run_id,
        tool_id="astrid.core.integrations.worker.banodoco_worker",
        kind="banodoco_timeline_generate",
        metadata={"baseline_snapshot": digest},
    )
    if not isinstance(run_record.get("metadata"), dict) or run_record["metadata"].get("baseline_snapshot") != digest:
        logger.warning("baseline_snapshot did not round-trip into run record for %s", run_id)
    return digest


# ---------------------------------------------------------------------------
# Worker event-append adapter (m3.5)
# ---------------------------------------------------------------------------

def _worker_append_events(
    *,
    project_slug: str | None,
    project_id: str,
    timeline_id: str,
    worker_id: str,
    claim_task_id: str,
    mutator,
    snapshot_payload: Any,
    verified_user_id: str | None = None,
) -> int:
    """Append worker-generated timeline mutations through the local event gateway.

    Attempts to resolve a local project-timeline binding for the remote
    timeline.  When successful, appends ``timeline.config_replaced`` events via
    ``pack_write_gateway`` and returns the new event-stream version.

    Remote-only claims (no local project_slug, or no matching local timeline)
    raise ``RuntimeError`` as controlled failures — the actual Supabase
    write-back is deferred to m6.

    When *verified_user_id* is provided (from the JWKS-verified user JWT),
    it is chained as ``actor.via`` on the emitted events to preserve
    initiator provenance.

    Returns:
        int: Event-stream version after appends (used as ``config_version``
        in the success payload).
    """
    if not project_slug:
        raise RuntimeError(
            f"worker append: no local project_slug configured; "
            f"remote-only claim deferred to m6 (project_id={project_id})"
        )

    from astrid.core.timeline import canonical_timeline_config
    from astrid.core.timeline._edit_helpers import pack_write_gateway
    from astrid.core.timeline.events.schema import TimelineActor
    from astrid.core.timeline.paths import find_timeline_by_event_stream_id

    # Resolve a local timeline slug from the remote timeline_id (event-stream UUID).
    found = find_timeline_by_event_stream_id(project_slug, timeline_id)
    if found is None:
        raise RuntimeError(
            f"worker append: no local timeline found for "
            f"event_stream_id={timeline_id} in project {project_slug}; "
            f"remote-only claim deferred to m6"
        )
    timeline_ulid, timeline_slug = found

    # Build the actor: system actor for the worker, with upstream provenance
    # in actor.via (the user/agent who initiated the task).
    actor_via = None
    if verified_user_id:
        actor_via = TimelineActor(
            type="human",
            id=verified_user_id,
            display=verified_user_id,
        )
    actor = TimelineActor(
        type="system",
        id=f"banodoco_worker:claim:{claim_task_id}",
        display=f"banodoco-worker:{worker_id}",
        via=[actor_via] if actor_via is not None else None,
    )

    # Apply the mutator to the snapshot to produce the new config.
    new_config = mutator(snapshot_payload, 0)
    if not isinstance(new_config, dict):
        raise RuntimeError("worker mutator did not return a dict")
    new_config = canonical_timeline_config(new_config)

    # Emit the validated full TimelineConfig replacement surface.
    events = [
        {
            "kind": "timeline.config_replaced",
            "payload": {"config": new_config},
        }
    ]

    result = pack_write_gateway(
        project_slug=project_slug,
        timeline_slug=timeline_slug,
        timeline_ulid=timeline_ulid,
        timeline_event_stream_id=timeline_id,
        events=events,
        actor=actor,
    )

    return result.new_version


@dataclass
class BanodocoWorker:
    """Reusable worker engine; ``run`` enters the long-poll loop."""

    dispatcher: IntentDispatcher
    config: WorkerConfig = field(default_factory=WorkerConfig)
    provider: SupabaseDataProvider | None = None

    def _provider(self) -> SupabaseDataProvider:
        if self.provider is None:
            self.provider = SupabaseDataProvider.from_env()
        return self.provider

    def run(self) -> int:
        """Long-running poll loop; returns 0 when ``max_iterations`` is reached."""

        iteration = 0
        service_role_key = reigh_env.resolve_service_role_key()
        while True:
            iteration += 1
            if self.config.max_iterations is not None and iteration > self.config.max_iterations:
                return 0
            try:
                claim = claim_next_task(
                    worker_id=self.config.worker_id,
                    service_role_key=service_role_key,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[claim] transport error: %s", exc)
                time.sleep(self.config.idle_sleep_sec)
                continue
            if claim is None:
                time.sleep(self.config.idle_sleep_sec)
                continue
            self._handle_claim(claim, service_role_key=service_role_key)
            time.sleep(self.config.poll_interval_sec)

    def _handle_claim(self, claim: ClaimResult, *, service_role_key: str) -> None:
        params = claim.params or {}
        correlation_id = str(params.get("correlation_id") or "")
        timeline_id = str(params.get("timeline_id") or "")
        run_id = str(claim.run_id or claim.task_id)

        # (a) defensive task-type guard
        if claim.task_type not in SUPPORTED_TASK_TYPES:
            self._fail(
                claim.task_id,
                error=f"unsupported task_type {claim.task_type!r}",
                correlation_id=correlation_id,
                service_role_key=service_role_key,
            )
            return

        # (b) JWKS-verified identity
        try:
            verified = verify_user_jwt(claim.user_jwt)
        except JwtVerificationError as exc:
            self._fail(
                claim.task_id,
                error=f"invalid user_jwt: {exc}",
                correlation_id=correlation_id,
                service_role_key=service_role_key,
            )
            return

        # (c) FLAG-013 — explicit service-role project-ownership read
        provider = self._provider()
        project_id = claim.project_id or str(params.get("project_id") or "")
        if not project_id:
            self._fail(
                claim.task_id,
                error="claim envelope missing project_id",
                correlation_id=correlation_id,
                service_role_key=service_role_key,
            )
            return
        try:
            _verify_project_ownership(
                provider=provider,
                project_id=project_id,
                verified=verified,
                service_role_key=service_role_key,
            )
        except ProjectOwnershipError as exc:
            self._fail(
                claim.task_id,
                error=f"project ownership mismatch: {exc}",
                correlation_id=correlation_id,
                service_role_key=service_role_key,
            )
            return

        # (d) snapshot fast-path
        current_timeline_param = params.get("current_timeline")
        if isinstance(current_timeline_param, dict):
            snapshot_payload = current_timeline_param
        else:
            try:
                snapshot_payload, _version = provider.load_timeline(project_id, timeline_id)
            except Exception as exc:  # noqa: BLE001
                self._fail(
                    claim.task_id,
                    error=f"timeline load failed: {exc}",
                    correlation_id=correlation_id,
                    service_role_key=service_role_key,
                )
                return

        # SD-008 baseline_snapshot — write must propagate failures (mirrors
        # the load_timeline failure pattern above): a snapshot-write crash
        # cannot silently leak past the claim loop or the task will appear
        # to succeed without provenance.
        try:
            _write_baseline_snapshot(
                project_slug=self.config.project_slug,
                run_id=run_id,
                payload=snapshot_payload,
            )
        except Exception as exc:  # noqa: BLE001
            self._fail(
                claim.task_id,
                error=f"baseline snapshot write failed: {exc}",
                correlation_id=correlation_id,
                service_role_key=service_role_key,
            )
            return

        # (e) intent dispatch -> mutator
        intent = str(params.get("intent") or "")
        try:
            inner_mutator = self.dispatcher(intent=intent, params=params, verified=verified)
        except DispatchError as exc:
            self._fail(
                claim.task_id,
                error=f"intent dispatch failed: {exc}",
                correlation_id=correlation_id,
                service_role_key=service_role_key,
            )
            return

        def _wrapped_mutator(config: TimelineConfig, version: int) -> TimelineConfig:
            new_config = inner_mutator(config, version)
            if not isinstance(new_config, dict):
                raise DispatchError("intent mutator must return a TimelineConfig dict")
            _ensure_carry_fields(new_config.get("clips"))
            return new_config

        # (f) versioned write — m3.5: prefer local event gateway; remote-only
        # claims without a local append backend fail with a controlled error.
        try:
            config_version = _worker_append_events(
                project_slug=self.config.project_slug,
                project_id=project_id,
                timeline_id=timeline_id,
                worker_id=self.config.worker_id,
                claim_task_id=claim.task_id,
                mutator=_wrapped_mutator,
                snapshot_payload=snapshot_payload,
                verified_user_id=verified.user_id,
            )
        except RuntimeError as exc:
            self._fail(
                claim.task_id,
                error=f"worker append failed: {exc}",
                correlation_id=correlation_id,
                service_role_key=service_role_key,
            )
            return

        self._complete(
            claim.task_id,
            config_version=config_version,
            timeline_id=timeline_id,
            correlation_id=correlation_id,
            service_role_key=service_role_key,
        )

    # ----- status helpers -----

    def _complete(
        self,
        task_id: str,
        *,
        config_version: int,
        timeline_id: str,
        correlation_id: str,
        service_role_key: str,
    ) -> None:
        result_data = {
            "config_version": config_version,
            "correlation_id": correlation_id,
            "timeline_id": timeline_id,
        }
        update_task_status(
            task_id,
            status=RunStatus.COMPLETED.to_reigh_wire(),
            result_data=result_data,
            service_role_key=service_role_key,
        )

    def _fail(
        self,
        task_id: str,
        *,
        error: str,
        correlation_id: str,
        service_role_key: str,
    ) -> None:
        try:
            update_task_status(
                task_id,
                status=RunStatus.FAILED.to_reigh_wire(),
                error=error,
                result_data={"correlation_id": correlation_id},
                service_role_key=service_role_key,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[status] failed to post Failed for %s: %s", task_id, exc)


# ----- default dispatcher + entrypoint -----


def _default_dispatcher(
    *,
    intent: str,
    params: Mapping[str, Any],
    verified: VerifiedJwt,
) -> Mutator:
    """Stub dispatcher that supports the ``passthrough`` intent.

    The ``passthrough`` intent leaves the timeline unchanged but exercises the
    full claim/verify/save loop end-to-end. Real intent handlers will replace
    this dispatcher; tests substitute their own ``IntentDispatcher`` directly.
    """

    if intent == "passthrough":

        def _identity(config: TimelineConfig, _version: int) -> TimelineConfig:
            return config

        return _identity
    raise DispatchError(f"no dispatcher registered for intent {intent!r}")


def run_worker(
    *,
    dispatcher: IntentDispatcher | None = None,
    config: WorkerConfig | None = None,
    provider: SupabaseDataProvider | None = None,
) -> int:
    worker = BanodocoWorker(
        dispatcher=dispatcher or _default_dispatcher,
        config=config or WorkerConfig(),
        provider=provider,
    )
    return worker.run()


def main(argv: list[str] | None = None) -> int:
    """``python3 -m astrid worker --pool banodoco`` entrypoint."""

    import argparse

    parser = argparse.ArgumentParser(prog="python3 -m astrid worker")
    parser.add_argument("--pool", default="banodoco", help="Worker pool. Only 'banodoco' is supported in v1.")
    parser.add_argument("--worker-id", help="Override worker id (default: aa-worker-<rand>).")
    parser.add_argument("--max-iterations", type=int, help="Stop after N claim iterations (for tests).")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--idle-sleep", type=float, default=5.0)
    parser.add_argument("--project-slug", help="Local project slug for runs/ provenance cache.")
    args = parser.parse_args(argv)

    if args.pool != "banodoco":
        print(f"worker: unsupported pool {args.pool!r}; only 'banodoco' is supported", flush=True)
        return 2

    cfg = WorkerConfig(
        worker_id=args.worker_id or WorkerConfig().worker_id,
        poll_interval_sec=args.poll_interval,
        idle_sleep_sec=args.idle_sleep,
        max_iterations=args.max_iterations,
        project_slug=args.project_slug,
    )
    return run_worker(config=cfg)


__all__ = [
    "BanodocoWorker",
    "DispatchError",
    "IntentDispatcher",
    "ProjectOwnershipError",
    "WorkerConfig",
    "_default_dispatcher",
    "_ensure_carry_fields",
    "_verify_project_ownership",
    "canonical_json",
    "main",
    "run_worker",
    "sha256_hex",
]
