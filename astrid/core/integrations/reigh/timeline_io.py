"""Versioned timeline read/write loop against Reigh fetch surfaces.

The ``save_timeline`` helper implements the optimistic-concurrency contract
documented in ``docs/contracts/integration_contracts.md``: load
``(timeline, config_version)`` via the ``reigh-data-fetch`` Edge Function,
apply a caller-supplied mutator, then persist the replacement config. When a
service-role append transport is configured, Astrid routes the save through the
timeline-event append library so Python remains the single owner of hashing and
projection. Without that transport, the helper falls back to the legacy
``update_timeline_config_versioned`` blob RPC. On version-mismatch, it re-loads
and re-applies the mutator up to ``retries`` times before raising
:class:`TimelineVersionConflictError`.

Auth scopes (FLAG-012 / SD-009): the worker write path uses ``service_role``
auth so it can write any timeline once it has verified ownership separately;
non-worker callers (CLI, ``open_in_reigh``) should pass a ``user_jwt`` or
``pat`` Auth tuple via ``write_auth=``. The helper does not bake in either
choice; callers select the auth scheme.
"""

from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from astrid.core.timeline import Timeline
from astrid.core.timeline.eventlog.supabase import LiveSupabaseAppendTransport
from astrid.core.timeline.eventlog.types import EventLogStaleVersionError
from astrid.core.timeline.events.schema import TimelineActor

from .errors import TimelineNotFoundError, TimelineVersionConflictError
from .supabase_client import Auth, SupabaseHTTPError, get_json, post_json, rpc

logger = logging.getLogger(__name__)


# Local raw-payload alias for in-flight mutation. The rich TypedDict for
# fully-validated timelines lives in astrid.core.timeline; this module operates on
# the unvalidated POST/PATCH body before it has been schema-checked.
RawTimelinePayload = dict[str, Any]
Mutator = Callable[[RawTimelinePayload, int], RawTimelinePayload]


@dataclass(frozen=True)
class SaveResult:
    timeline: RawTimelinePayload
    new_version: int
    attempts: int


def _round_trip(payload: Mapping[str, Any]) -> RawTimelinePayload:
    """Round-trip a fetched timeline through astrid.core.timeline so byte-equivalent
    allowlist parity stays intact."""

    return Timeline.from_json_data(dict(payload)).to_config()  # type: ignore[return-value]


def _to_storage_payload(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate + emit the JSON shape the DB column expects."""

    return Timeline.from_config(dict(config)).to_json_data()


def _canonicalize_config(config: Mapping[str, Any]) -> RawTimelinePayload:
    """Validate + round-trip config into Astrid's canonical timeline shape."""

    canonical = Timeline.from_config(dict(config)).to_config()  # type: ignore[assignment]
    canonical.setdefault("tracks", [])
    canonical.setdefault("clips", [])
    return canonical  # type: ignore[return-value]


def _looks_like_version_conflict(exc: SupabaseHTTPError) -> bool:
    if exc.status == 409:
        return True
    body = (exc.body or "").lower()
    return any(
        marker in body
        for marker in (
            "version_conflict",
            "version conflict",
            "expected_version",
            "stale config_version",
        )
    )


def fetch_timeline(
    *,
    fetch_url: str,
    project_id: str,
    timeline_id: str,
    auth: Auth,
    timeout: float = 60.0,
) -> tuple[RawTimelinePayload, int]:
    """Call ``reigh-data-fetch`` and return ``(timeline_config, config_version)``."""

    payload = post_json(
        fetch_url,
        {"project_id": project_id, "timeline_id": timeline_id},
        auth=auth,
        timeout=timeout,
    )
    if not isinstance(payload, dict):
        raise TimelineNotFoundError(
            f"reigh-data-fetch returned non-object payload for timeline {timeline_id}"
        )
    timelines = payload.get("timelines")
    if not isinstance(timelines, list) or not timelines:
        raise TimelineNotFoundError(
            f"reigh-data-fetch returned no timelines for {timeline_id}"
        )
    match: Mapping[str, Any] | None = None
    for entry in timelines:
        if isinstance(entry, dict) and entry.get("id") == timeline_id:
            match = entry
            break
    if match is None:
        first = timelines[0]
        if isinstance(first, dict):
            match = first
    if match is None:
        raise TimelineNotFoundError(
            f"reigh-data-fetch did not return timeline {timeline_id}"
        )

    raw_config = match.get("config")
    if not isinstance(raw_config, dict):
        raise TimelineNotFoundError(
            f"reigh-data-fetch row for {timeline_id} has no config object"
        )
    raw_version = match.get("config_version")
    if not isinstance(raw_version, int):
        raise TimelineNotFoundError(
            "reigh-data-fetch payload is missing config_version. "
            "Phase 2 requires the reigh-app PR adding config_version to TIMELINES_SELECT."
        )
    return _round_trip(raw_config), raw_version


def save_timeline(
    *,
    timeline_id: str,
    project_id: str,
    mutator: Mutator,
    fetch_url: str,
    supabase_url: str,
    read_auth: Auth,
    write_auth: Auth,
    expected_version: int | None = None,
    retries: int = 3,
    force: bool = False,
    timeout: float = 60.0,
    asset_registry: Mapping[str, Any] | None = None,
    append_service_role_key: str | None = None,
) -> SaveResult:
    """Apply ``mutator`` to the timeline and persist via the versioned RPC.

    The mutator receives ``(current_config, current_version)`` and must return
    a new ``RawTimelinePayload`` dict. On version-mismatch responses (HTTP 409 or
    body markers like ``version_conflict`` / ``expected_version``), the helper
    re-fetches and re-applies the mutator. ``retries`` is the total attempt
    count (including the first one).

    ``expected_version=None`` is rejected unless ``force=True`` — this protects
    the worker path which must always carry ``task.params.expected_version``.
    ``force=True`` is logged at WARNING because it bypasses the optimistic
    concurrency contract.
    """

    if retries < 1:
        raise ValueError("retries must be >= 1")
    if expected_version is None and not force:
        raise ValueError(
            "save_timeline requires expected_version unless force=True"
        )
    if force:
        logger.warning(
            "save_timeline called with force=True for timeline_id=%s expected_version=%s",
            timeline_id,
            expected_version,
        )

    last_version: int | None = expected_version
    last_exc: SupabaseHTTPError | None = None
    last_stale: EventLogStaleVersionError | None = None
    append_token = _resolve_append_service_role_key(
        write_auth=write_auth,
        append_service_role_key=append_service_role_key,
    )
    for attempt in range(1, retries + 1):
        config, current_version = fetch_timeline(
            fetch_url=fetch_url,
            project_id=project_id,
            timeline_id=timeline_id,
            auth=read_auth,
            timeout=timeout,
        )
        last_version = current_version

        if (
            not force
            and expected_version is not None
            and current_version != expected_version
            and attempt == 1
        ):
            logger.info(
                "save_timeline expected_version=%s but DB has %s; retrying with fresh load",
                expected_version,
                current_version,
            )

        new_config = mutator(config, current_version)
        if not isinstance(new_config, dict):
            raise TypeError("save_timeline mutator must return a RawTimelinePayload dict")
        canonical_config = _canonicalize_config(new_config)

        if append_token is not None:
            try:
                result = _save_via_append_transport(
                    timeline_id=timeline_id,
                    config=canonical_config,
                    asset_registry=asset_registry,
                    supabase_url=supabase_url,
                    service_role_key=append_token,
                    expected_version=current_version,
                    timeout=timeout,
                    actor=_default_actor_for_auth(write_auth),
                )
            except EventLogStaleVersionError as exc:
                last_stale = exc
                if not force:
                    logger.info(
                        "save_timeline append conflict on attempt %d/%d for %s (expected=%s)",
                        attempt,
                        retries,
                        timeline_id,
                        current_version,
                    )
                    continue
                raise
            return SaveResult(
                timeline=canonical_config,
                new_version=result.config_version,
                attempts=attempt,
            )
        storage_payload = _to_storage_payload(canonical_config)
        try:
            response = rpc(
                "update_timeline_config_versioned",
                {
                    "p_timeline_id": timeline_id,
                    "p_expected_version": current_version,
                    "p_config": storage_payload,
                },
                supabase_url=supabase_url,
                auth=write_auth,
                timeout=timeout,
            )
        except SupabaseHTTPError as exc:
            last_exc = exc
            if _looks_like_version_conflict(exc) and not force:
                logger.info(
                    "save_timeline version conflict on attempt %d/%d for %s (expected=%s)",
                    attempt,
                    retries,
                    timeline_id,
                    current_version,
                )
                continue
            raise

        new_version = _extract_new_version(response, fallback=current_version + 1)
        return SaveResult(
            timeline=canonical_config,
            new_version=new_version,
            attempts=attempt,
        )

    raise TimelineVersionConflictError(
        f"save_timeline exhausted {retries} attempts for timeline_id={timeline_id}",
        attempts=retries,
        last_expected_version=last_version,
    ) from (last_stale or last_exc)


def _resolve_append_service_role_key(
    *,
    write_auth: Auth,
    append_service_role_key: str | None,
) -> str | None:
    if append_service_role_key:
        return append_service_role_key
    return None


def _default_actor_for_auth(write_auth: Auth) -> TimelineActor:
    scheme, _token = write_auth
    if scheme == "service_role":
        return TimelineActor(type="system", id="astrid-python")
    return TimelineActor(type="human", id=f"reigh-{scheme}")


def _save_via_append_transport(
    *,
    timeline_id: str,
    config: RawTimelinePayload,
    asset_registry: Mapping[str, Any] | None,
    supabase_url: str,
    service_role_key: str,
    expected_version: int,
    timeout: float,
    actor: TimelineActor,
):
    transport = LiveSupabaseAppendTransport(
        supabase_url=supabase_url,
        auth_token=service_role_key,
        timeout=timeout,
    )
    return transport.append_config_replaced(
        timeline_id=timeline_id,
        config=dict(config),
        asset_registry=dict(asset_registry) if asset_registry is not None else None,
        actor=actor,
        source="editor_save",
        expected_version=expected_version,
    )


def _extract_new_version(response: Any, *, fallback: int) -> int:
    if isinstance(response, int):
        return response
    if isinstance(response, dict):
        for key in ("config_version", "new_version", "version"):
            value = response.get(key)
            if isinstance(value, int):
                return value
    if isinstance(response, list) and response:
        first = response[0]
        if isinstance(first, dict):
            for key in ("config_version", "new_version", "version"):
                value = first.get(key)
                if isinstance(value, int):
                    return value
    return fallback


# ---------------------------------------------------------------------------
# Migration discovery helpers (SD3 — Reigh transport seam)
# ---------------------------------------------------------------------------


def list_timelines(
    *,
    supabase_url: str,
    auth: Auth,
    project_id: str | None = None,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """List ``public.timelines`` rows via PostgREST GET.

    Returns a list of row dicts (each with ``id``, ``project_id``,
    ``config_version``).  When *project_id* is given, results are filtered
    to that project.
    """

    base = supabase_url.rstrip("/")
    endpoint = f"{base}/rest/v1/timelines?select=id,project_id,config_version"
    if project_id:
        endpoint += f"&project_id=eq.{urllib.parse.quote(project_id, safe='')}"

    try:
        result = get_json(endpoint, auth=auth, timeout=timeout)
    except SupabaseHTTPError:
        return []
    if isinstance(result, list):
        return [dict(row) for row in result if isinstance(row, dict)]
    return []


def timeline_has_events(
    *,
    supabase_url: str,
    auth: Auth,
    timeline_id: str,
    timeout: float = 30.0,
) -> bool:
    """Check whether ``public.timeline_events`` has any rows for *timeline_id*."""

    base = supabase_url.rstrip("/")
    endpoint = (
        f"{base}/rest/v1/timeline_events"
        f"?timeline_id=eq.{urllib.parse.quote(timeline_id, safe='')}"
        f"&limit=1&select=event_id"
    )

    try:
        result = get_json(endpoint, auth=auth, timeout=timeout)
    except SupabaseHTTPError:
        return False
    return isinstance(result, list) and len(result) > 0
