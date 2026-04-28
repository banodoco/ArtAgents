"""Versioned timeline write + SD-034 correlation_id retry semantics.

The worker writes its generated TimelineConfig via Reigh's
`update_timeline_config_versioned` RPC (service-role) but with the user_id
audited from the verified JWT. On version conflict (RPC returns null /
non-numeric `config_version`), the worker reads the current config and
checks whether the existing timeline-version metadata carries the SAME
correlation_id this task was assigned:

  - same correlation_id => predecessor wrote this same task; treat as
    success (this is the SD-034 retry path).
  - different correlation_id => the user made a surgical edit during
    generation; surface task-failure with code `version_conflict` and the
    canonical "your edits superseded the AI's, retry?" message.

`correlation_id` is embedded in the timeline-version metadata under the
key `_metadata.correlation_id`. The chosen key namespace is intentionally
underscore-prefixed so it doesn't collide with first-class TimelineConfig
fields (clips/tracks/theme/...).
"""

from __future__ import annotations

import copy
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


CORRELATION_ID_CONFIG_KEY = "_metadata"
CORRELATION_ID_FIELD = "correlation_id"


@dataclass
class WriteResult:
    """Outcome of `apply_versioned_write_with_correlation_retry`."""

    status: str  # "completed" | "version_conflict" | "auth_failed" | "rpc_failure"
    new_version: Optional[int] = None
    message: str = ""


class TimelineRpcClient(Protocol):
    """Minimal protocol the writer needs from the Supabase admin client.

    Implemented in production by `supabase.create_client(...)`'s `.rpc()`
    surface; mocked aggressively in tests so they don't touch a real DB.
    """

    def update_timeline_config_versioned(
        self,
        *,
        timeline_id: str,
        expected_version: int,
        config: Dict[str, Any],
    ) -> Optional[int]: ...

    def fetch_current_config(self, timeline_id: str) -> Dict[str, Any]: ...


def embed_correlation_id(
    config: Dict[str, Any], correlation_id: str
) -> Dict[str, Any]:
    """Return a copy of `config` with correlation_id stamped into _metadata.

    Idempotent — applying twice with the same correlation_id is a no-op.
    Never mutates the caller's dict.
    """
    if not correlation_id:
        raise ValueError("correlation_id must be non-empty")
    out = copy.deepcopy(config)
    metadata = out.get(CORRELATION_ID_CONFIG_KEY)
    if not isinstance(metadata, dict):
        metadata = {}
    metadata[CORRELATION_ID_FIELD] = correlation_id
    out[CORRELATION_ID_CONFIG_KEY] = metadata
    return out


def extract_correlation_id(config: Dict[str, Any]) -> Optional[str]:
    """Pull the correlation_id back out of a TimelineConfig, if present."""
    metadata = config.get(CORRELATION_ID_CONFIG_KEY)
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(CORRELATION_ID_FIELD)
    if isinstance(value, str) and value.strip():
        return value
    return None


def apply_versioned_write_with_correlation_retry(
    *,
    rpc: TimelineRpcClient,
    timeline_id: str,
    expected_version: int,
    config: Dict[str, Any],
    correlation_id: str,
) -> WriteResult:
    """Write `config` to `timeline_id` and translate 409s into SD-034 outcomes.

    Returns a WriteResult with status one of:
      - "completed"        — write landed (new_version populated).
      - "version_conflict" — different writer raced; agent should surface
                              "your edits superseded the AI's, retry?".
      - "rpc_failure"      — the RPC raised; treat as transient.
    """
    if not correlation_id:
        return WriteResult(
            status="rpc_failure",
            message="missing correlation_id (programmer error)",
        )

    stamped = embed_correlation_id(config, correlation_id)

    try:
        new_version = rpc.update_timeline_config_versioned(
            timeline_id=timeline_id,
            expected_version=expected_version,
            config=stamped,
        )
    except Exception as exc:  # noqa: BLE001 — let the worker decide retry policy
        logger.exception("[BANODOCO_WRITE] RPC call failed: %s", exc)
        return WriteResult(status="rpc_failure", message=str(exc))

    if isinstance(new_version, int):
        return WriteResult(status="completed", new_version=new_version)

    # 409 path: read current config; check correlation_id parity.
    try:
        current = rpc.fetch_current_config(timeline_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "[BANODOCO_WRITE] Failed to read current config after 409: %s", exc
        )
        return WriteResult(
            status="rpc_failure",
            message=f"409 received but could not re-read current config: {exc}",
        )

    existing_correlation_id = extract_correlation_id(current)
    if existing_correlation_id == correlation_id:
        logger.info(
            "[BANODOCO_WRITE] 409 with matching correlation_id %s — predecessor wrote.",
            correlation_id,
        )
        # We can't return the new version number from this path because
        # the RPC didn't bump it for us; the caller treats the missing
        # version as "predecessor handled it" success.
        return WriteResult(
            status="completed",
            new_version=None,
            message=(
                "predecessor write detected via correlation_id parity"
            ),
        )

    return WriteResult(
        status="version_conflict",
        message=(
            "Your edits superseded the AI's mid-generation. "
            "Retry the agent request to regenerate against the new state."
        ),
    )


# ---------------------------------------------------------------------------
# Production RPC adapter (thin wrapper over supabase-py)
# ---------------------------------------------------------------------------


class SupabaseTimelineRpc:
    """Concrete `TimelineRpcClient` backed by supabase-py service-role."""

    def __init__(
        self,
        *,
        supabase_url: Optional[str] = None,
        service_role_key: Optional[str] = None,
        audited_user_id: Optional[str] = None,
    ) -> None:
        from supabase import create_client  # imported lazily — heavy

        url = supabase_url or os.getenv("REIGH_SUPABASE_URL")
        key = service_role_key or os.getenv("REIGH_SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SupabaseTimelineRpc requires REIGH_SUPABASE_URL + "
                "REIGH_SUPABASE_SERVICE_ROLE_KEY (or explicit args)"
            )
        self._client = create_client(url, key)
        # SD-022: every mutation is audited with the JWT-derived user_id;
        # never the service-role identity, even though the call uses the
        # service-role key.
        self.audited_user_id = audited_user_id

    def update_timeline_config_versioned(
        self,
        *,
        timeline_id: str,
        expected_version: int,
        config: Dict[str, Any],
    ) -> Optional[int]:
        params: Dict[str, Any] = {
            "p_timeline_id": timeline_id,
            "p_expected_version": expected_version,
            "p_config": config,
        }
        # If Reigh's RPC accepts the auditing user_id (Phase 7 of SD-022
        # requires this — verify on the Reigh side), pass it through.
        if self.audited_user_id:
            params["p_audited_user_id"] = self.audited_user_id

        result = (
            self._client.rpc("update_timeline_config_versioned", params)
            .execute()
        )
        data = result.data if hasattr(result, "data") else None
        if isinstance(data, list) and data:
            data = data[0]
        if isinstance(data, dict):
            cv = data.get("config_version")
            if isinstance(cv, int):
                return cv
        return None

    def fetch_current_config(self, timeline_id: str) -> Dict[str, Any]:
        result = (
            self._client.table("timelines")
            .select("config")
            .eq("id", timeline_id)
            .single()
            .execute()
        )
        data = result.data if hasattr(result, "data") else None
        if isinstance(data, dict):
            cfg = data.get("config")
            if isinstance(cfg, dict):
                return cfg
        return {}


__all__ = [
    "CORRELATION_ID_CONFIG_KEY",
    "CORRELATION_ID_FIELD",
    "SupabaseTimelineRpc",
    "TimelineRpcClient",
    "WriteResult",
    "apply_versioned_write_with_correlation_retry",
    "embed_correlation_id",
    "extract_correlation_id",
]
