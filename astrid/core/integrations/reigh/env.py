"""Environment discovery for Reigh edge-function and Supabase integrations."""

from __future__ import annotations

import os
from pathlib import Path

from astrid.core.util.secrets import candidate_env_files, read_env_value

DEFAULT_FUNCTION_NAME = "reigh-data-fetch"


def _candidate_env_files(env_file: Path | None = None) -> list[Path]:
    return candidate_env_files(env_file, profile="reigh")


# Reserved sentinel prefix: values beginning with this are treated as UNSET by
# Reigh env resolution, so placeholder files (e.g. a "fill before release"
# .env.local) can never poison downstream consumers. A real value cannot
# legitimately start with this prefix.
PLACEHOLDER_SENTINEL = "PLACEHOLDER_"


def _env_first(keys: tuple[str, ...], env_file: Path | None = None) -> str:
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value and not value.startswith(PLACEHOLDER_SENTINEL):
            return value
    for candidate in _candidate_env_files(env_file):
        for key in keys:
            value = read_env_value(candidate, key)
            if value and not value.startswith(PLACEHOLDER_SENTINEL):
                return value
    return ""


def _url_from_base(base: str, function_name: str) -> str:
    return f"{base.rstrip('/')}/functions/v1/{function_name}"


def resolve_supabase_url(
    supabase_url: str | None = None,
    env_file: Path | None = None,
) -> str:
    explicit = (supabase_url or "").strip()
    if explicit:
        return explicit.rstrip("/")
    value = _env_first(("REIGH_SUPABASE_URL", "SUPABASE_URL"), env_file)
    if value:
        return value.rstrip("/")
    raise RuntimeError("Reigh Supabase URL not found. Set REIGH_SUPABASE_URL or SUPABASE_URL.")


def resolve_api_url(api_url: str | None = None, env_file: Path | None = None) -> str:
    explicit = (api_url or "").strip()
    if explicit:
        return explicit.rstrip("/")

    direct = _env_first(("REIGH_DATA_FETCH_URL",), env_file)
    if direct:
        return direct.rstrip("/")

    base = _env_first(("REIGH_API_URL", "REIGH_SUPABASE_URL", "SUPABASE_URL"), env_file)
    if base:
        return _url_from_base(base, DEFAULT_FUNCTION_NAME)

    raise RuntimeError(
        "Reigh API URL not found. Set REIGH_DATA_FETCH_URL, REIGH_API_URL, "
        "REIGH_SUPABASE_URL, or SUPABASE_URL."
    )


def resolve_pat(pat: str | None = None, env_file: Path | None = None) -> str:
    explicit = (pat or "").strip()
    if explicit:
        return explicit
    token = _env_first(("REIGH_PAT", "REIGH_PERSONAL_ACCESS_TOKEN"), env_file)
    if token:
        return token
    raise RuntimeError("Reigh PAT not found. Set REIGH_PAT or REIGH_PERSONAL_ACCESS_TOKEN.")


def resolve_claim_url(claim_url: str | None = None, env_file: Path | None = None) -> str:
    explicit = (claim_url or "").strip()
    if explicit:
        return explicit.rstrip("/")

    direct = _env_first(("REIGH_CLAIM_NEXT_TASK_URL", "REIGH_CLAIM_URL"), env_file)
    if direct:
        return direct.rstrip("/")

    base = _env_first(
        ("ORCHESTRATOR_BASE_URL", "REIGH_ORCHESTRATOR_URL", "REIGH_SUPABASE_URL", "SUPABASE_URL"),
        env_file,
    )
    if base:
        return _url_from_base(base, "claim-next-task")

    raise RuntimeError(
        "Claim URL not found. Set REIGH_CLAIM_NEXT_TASK_URL, ORCHESTRATOR_BASE_URL, "
        "REIGH_SUPABASE_URL, or SUPABASE_URL."
    )


def resolve_task_status_update_url(
    update_url: str | None = None,
    env_file: Path | None = None,
) -> str:
    explicit = (update_url or "").strip()
    if explicit:
        return explicit.rstrip("/")

    direct = _env_first(
        ("REIGH_TASK_STATUS_UPDATE_URL", "REIGH_UPDATE_TASK_STATUS_URL"),
        env_file,
    )
    if direct:
        return direct.rstrip("/")

    base = _env_first(
        ("ORCHESTRATOR_BASE_URL", "REIGH_ORCHESTRATOR_URL", "REIGH_SUPABASE_URL", "SUPABASE_URL"),
        env_file,
    )
    if base:
        return _url_from_base(base, "update-task-status")

    raise RuntimeError(
        "Task status update URL not found. Set REIGH_TASK_STATUS_UPDATE_URL, "
        "ORCHESTRATOR_BASE_URL, REIGH_SUPABASE_URL, or SUPABASE_URL."
    )


def resolve_service_role_key(
    service_role_key: str | None = None,
    env_file: Path | None = None,
) -> str:
    explicit = (service_role_key or "").strip()
    if explicit:
        return explicit
    key = _env_first(("REIGH_SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_ROLE_KEY"), env_file)
    if key:
        return key
    raise RuntimeError(
        "Reigh Supabase service-role key not found. Set REIGH_SUPABASE_SERVICE_ROLE_KEY."
    )


def resolve_jwt_secret(env_file: Path | None = None) -> str | None:
    """Project JWT secret for verifying HS256 Supabase access tokens.

    Optional: only needed when the append service must validate user JWTs and
    the project JWKS endpoint serves no keys (the default for GoTrue HS256
    projects). Placeholder values are treated as unset.
    """
    value = _env_first(("REIGH_SUPABASE_JWT_SECRET", "SUPABASE_JWT_SECRET"), env_file)
    return value.strip() or None


def resolve_jwks_url(jwks_url: str | None = None, env_file: Path | None = None) -> str:
    explicit = (jwks_url or "").strip()
    if explicit:
        return explicit.rstrip("/")

    direct = _env_first(("REIGH_SUPABASE_JWKS_URL",), env_file)
    if direct:
        return direct.rstrip("/")

    base = resolve_supabase_url(env_file=env_file)
    return f"{base}/auth/v1/.well-known/jwks.json"
