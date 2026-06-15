#!/usr/bin/env python3
"""Seed version-1 ``timeline.config_replaced`` rows into ``public.timeline_events``.

Modes:

- ``--dry-run`` (default): inspect timelines and report what would be seeded.
- ``--apply``: insert one seed event for each eligible timeline.
- ``--rollback``: delete only rows marked with the seed idempotency prefix.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO))

from astrid.core.integrations.reigh import env as reigh_env
from astrid.core.integrations.reigh.event_construction import config_to_events
from astrid.core.integrations.reigh.supabase_client import Auth, SupabaseHTTPError, get_json
from astrid.core.timeline.banodoco_schema import canonical_timeline_config
from astrid.core.timeline.events.schema import TimelineActor

SEED_IDEMPOTENCY_PREFIX = "seed:config_replaced:"
SEED_ACTOR = TimelineActor(
    type="system",
    id="reigh-seed-timeline-events",
    display="Reigh timeline seed",
)
SEED_SOURCE = "supabase_config"


@dataclass(frozen=True)
class TimelineSeedResult:
    timeline_id: str
    action: str
    reason: str
    config_version: int | None = None
    idempotency_key: str | None = None
    event_id: str | None = None


def _seed_idempotency_key(timeline_id: str) -> str:
    return f"{SEED_IDEMPOTENCY_PREFIX}{timeline_id}"


def _build_headers(auth: Auth, *, extra: dict[str, str] | None = None) -> dict[str, str]:
    scheme, token = auth
    if not isinstance(token, str) or not token:
        raise ValueError("Supabase auth token must be a non-empty string")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if scheme == "service_role":
        headers["apikey"] = token
    if extra:
        headers.update(extra)
    return headers


def _request_json(
    method: str,
    url: str,
    *,
    auth: Auth,
    payload: Any = None,
    extra_headers: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers=_build_headers(auth, extra=extra_headers),
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SupabaseHTTPError(
            f"Supabase {method} failed: HTTP {exc.code}: {detail}",
            status=exc.code,
            body=detail,
        ) from exc
    except urllib.error.URLError as exc:
        raise SupabaseHTTPError(
            f"Supabase {method} failed: {exc.reason}",
            status=0,
            body=str(exc.reason),
        ) from exc

    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _list_timelines(
    *,
    supabase_url: str,
    auth: Auth,
    timeline_id: str | None = None,
    timeout: float = 60.0,
) -> list[dict[str, Any]]:
    endpoint = (
        f"{supabase_url.rstrip('/')}/rest/v1/timelines"
        "?select=id,config,config_version&order=id.asc"
    )
    if timeline_id:
        endpoint += f"&id=eq.{urllib.parse.quote(timeline_id, safe='')}"
    result = get_json(endpoint, auth=auth, timeout=timeout)
    if not isinstance(result, list):
        return []
    return [dict(row) for row in result if isinstance(row, dict)]


def _timeline_has_any_events(
    *,
    supabase_url: str,
    auth: Auth,
    timeline_id: str,
    timeout: float = 60.0,
) -> bool:
    endpoint = (
        f"{supabase_url.rstrip('/')}/rest/v1/timeline_events"
        f"?timeline_id=eq.{urllib.parse.quote(timeline_id, safe='')}"
        "&limit=1&select=event_id"
    )
    result = get_json(endpoint, auth=auth, timeout=timeout)
    return isinstance(result, list) and len(result) > 0


def _list_seed_rows(
    *,
    supabase_url: str,
    auth: Auth,
    timeline_id: str | None = None,
    timeout: float = 60.0,
) -> list[dict[str, Any]]:
    prefix = urllib.parse.quote(f"{SEED_IDEMPOTENCY_PREFIX}%", safe="")
    endpoint = (
        f"{supabase_url.rstrip('/')}/rest/v1/timeline_events"
        f"?select=timeline_id,event_id,idempotency_key&idempotency_key=like.{prefix}"
    )
    if timeline_id:
        endpoint += f"&timeline_id=eq.{urllib.parse.quote(timeline_id, safe='')}"
    result = get_json(endpoint, auth=auth, timeout=timeout)
    if not isinstance(result, list):
        return []
    return [dict(row) for row in result if isinstance(row, dict)]


def _insert_timeline_events(
    *,
    supabase_url: str,
    auth: Auth,
    rows: list[dict[str, Any]],
    timeout: float = 60.0,
) -> Any:
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/timeline_events"
    return _request_json(
        "POST",
        endpoint,
        auth=auth,
        payload=rows,
        extra_headers={"Prefer": "return=representation"},
        timeout=timeout,
    )


def _delete_seed_rows(
    *,
    supabase_url: str,
    auth: Auth,
    timeline_id: str | None = None,
    timeout: float = 60.0,
) -> None:
    prefix = urllib.parse.quote(f"{SEED_IDEMPOTENCY_PREFIX}%", safe="")
    endpoint = (
        f"{supabase_url.rstrip('/')}/rest/v1/timeline_events"
        f"?idempotency_key=like.{prefix}"
    )
    if timeline_id:
        endpoint += f"&timeline_id=eq.{urllib.parse.quote(timeline_id, safe='')}"
    _request_json(
        "DELETE",
        endpoint,
        auth=auth,
        extra_headers={"Prefer": "return=minimal"},
        timeout=timeout,
    )


def _normalized_expected_version(raw: object) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int) and raw >= 0:
        return raw
    return None


def _build_seed_event_row(
    *,
    timeline_id: str,
    config: dict[str, Any],
    config_version: object,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        validated_config = canonical_timeline_config(config)
    except Exception as exc:
        return None, f"invalid config: {exc}"

    expected_version = _normalized_expected_version(config_version)
    batch = config_to_events(
        validated_config,
        None,
        timeline_id,
        None,
        1,
        SEED_ACTOR,
        SEED_SOURCE,
        expected_version=expected_version,
    )
    if len(batch.events) != 1:
        return None, "seed path expected exactly one config_replaced event"
    seed_event = batch.events[0].to_append_json_obj()
    row = {
        "event_id": seed_event["event_id"],
        "timeline_id": seed_event["timeline_id"],
        "version": seed_event["version"],
        "prev_hash": seed_event["prev_hash"],
        "hash": seed_event["hash"],
        "kind": seed_event["kind"],
        "payload": seed_event["payload"],
        "schema_version": seed_event["schema_version"],
        "idempotency_key": _seed_idempotency_key(timeline_id),
        "ts": seed_event["ts"],
        "actor": seed_event["actor"],
        "expected_version": seed_event["expected_version"],
        "txn_id": seed_event["txn_id"],
    }
    return row, None


def run_seed(
    *,
    supabase_url: str,
    auth: Auth,
    apply: bool,
    timeline_id: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    results: list[TimelineSeedResult] = []
    timelines = _list_timelines(
        supabase_url=supabase_url,
        auth=auth,
        timeline_id=timeline_id,
        timeout=timeout,
    )

    for row in timelines:
        raw_timeline_id = row.get("id")
        if not isinstance(raw_timeline_id, str) or not raw_timeline_id:
            continue
        if _timeline_has_any_events(
            supabase_url=supabase_url,
            auth=auth,
            timeline_id=raw_timeline_id,
            timeout=timeout,
        ):
            results.append(
                TimelineSeedResult(
                    timeline_id=raw_timeline_id,
                    action="skipped_existing_events",
                    reason="timeline already has timeline_events rows",
                    config_version=_normalized_expected_version(row.get("config_version")),
                )
            )
            continue

        config = row.get("config")
        if not isinstance(config, dict):
            results.append(
                TimelineSeedResult(
                    timeline_id=raw_timeline_id,
                    action="invalid_config",
                    reason="config is missing or not a JSON object",
                    config_version=_normalized_expected_version(row.get("config_version")),
                )
            )
            continue

        seed_row, error = _build_seed_event_row(
            timeline_id=raw_timeline_id,
            config=config,
            config_version=row.get("config_version"),
        )
        if error is not None or seed_row is None:
            results.append(
                TimelineSeedResult(
                    timeline_id=raw_timeline_id,
                    action="invalid_config",
                    reason=error or "invalid config",
                    config_version=_normalized_expected_version(row.get("config_version")),
                )
            )
            continue

        action = "seeded" if apply else "would_seed"
        results.append(
            TimelineSeedResult(
                timeline_id=raw_timeline_id,
                action=action,
                reason="eligible for version-1 timeline.config_replaced seed",
                config_version=_normalized_expected_version(row.get("config_version")),
                idempotency_key=seed_row["idempotency_key"],
                event_id=seed_row["event_id"],
            )
        )
        if apply:
            _insert_timeline_events(
                supabase_url=supabase_url,
                auth=auth,
                rows=[seed_row],
                timeout=timeout,
            )

    invalid = [item for item in results if item.action == "invalid_config"]
    seeded = [item for item in results if item.action == "seeded"]
    would_seed = [item for item in results if item.action == "would_seed"]
    skipped = [item for item in results if item.action == "skipped_existing_events"]
    status = "ok" if not invalid else "invalid_configs_found"
    return {
        "mode": "apply" if apply else "dry_run",
        "status": status,
        "counts": {
            "timelines_seen": len(timelines),
            "seeded": len(seeded),
            "would_seed": len(would_seed),
            "skipped_existing_events": len(skipped),
            "invalid_configs": len(invalid),
        },
        "results": [asdict(item) for item in results],
    }


def run_rollback(
    *,
    supabase_url: str,
    auth: Auth,
    timeline_id: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    rows = _list_seed_rows(
        supabase_url=supabase_url,
        auth=auth,
        timeline_id=timeline_id,
        timeout=timeout,
    )
    _delete_seed_rows(
        supabase_url=supabase_url,
        auth=auth,
        timeline_id=timeline_id,
        timeout=timeout,
    )
    return {
        "mode": "rollback",
        "status": "ok",
        "counts": {
            "seed_rows_deleted": len(rows),
        },
        "results": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview seedable timelines (default).")
    mode.add_argument("--apply", action="store_true", help="Insert seed timeline_events rows.")
    mode.add_argument("--rollback", action="store_true", help="Delete only seed-marked timeline_events rows.")
    parser.add_argument("--timeline-id", help="Restrict work to a single timeline UUID.")
    parser.add_argument("--supabase-url", help="Override REIGH_SUPABASE_URL / SUPABASE_URL.")
    parser.add_argument(
        "--service-role-key",
        help="Override REIGH_SUPABASE_SERVICE_ROLE_KEY / SUPABASE_SERVICE_ROLE_KEY.",
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    apply = bool(args.apply)
    rollback = bool(args.rollback)

    try:
        supabase_url = reigh_env.resolve_supabase_url(args.supabase_url)
        service_role_key = reigh_env.resolve_service_role_key(args.service_role_key)
        auth: Auth = ("service_role", service_role_key)
        if rollback:
            summary = run_rollback(
                supabase_url=supabase_url,
                auth=auth,
                timeline_id=args.timeline_id,
                timeout=args.timeout,
            )
        else:
            summary = run_seed(
                supabase_url=supabase_url,
                auth=auth,
                apply=apply,
                timeline_id=args.timeline_id,
                timeout=args.timeout,
            )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "detail": str(exc),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary.get("status") != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
