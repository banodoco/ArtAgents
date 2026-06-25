"""Compatibility exports for Supabase HTTP helpers used by Reigh integrations."""

from __future__ import annotations

from astrid.core.timeline.eventlog.supabase_client import (
    Auth,
    AuthScheme,
    SupabaseHTTPError,
    get_json,
    post_json,
    rpc,
)

__all__ = [
    "Auth",
    "AuthScheme",
    "SupabaseHTTPError",
    "get_json",
    "post_json",
    "rpc",
]
