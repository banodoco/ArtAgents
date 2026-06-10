"""Shared helpers for editorial pack executors."""

from __future__ import annotations

from pathlib import Path

from astrid.core.contracts.errors import AstridError
from astrid.core.util.credentials_scope import CredentialsScope


def load_api_key(env_file: Path | None) -> str:
    """Resolve the OPENAI_API_KEY via the canonical scoped credentials resolver."""
    try:
        return CredentialsScope.get("openai", env_file=env_file)
    except AstridError as exc:
        raise SystemExit(str(exc)) from exc


__all__ = ["load_api_key"]
