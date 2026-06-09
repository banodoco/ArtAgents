"""Shared helpers for editorial pack executors."""

from __future__ import annotations

import os
from pathlib import Path

from astrid.core.util.secrets import candidate_env_files, read_env_value


def load_api_key(env_file: Path | None) -> str:
    # Lookup order: process env, explicit --env-file, then nearby this.env/.env files.
    tried: list[str] = ["OPENAI_API_KEY environment variable"]
    if key := os.environ.get("OPENAI_API_KEY", "").strip():
        return key
    for candidate in candidate_env_files(env_file):
        tried.append(str(candidate))
        if key := read_env_value(candidate, "OPENAI_API_KEY"):
            return key
    raise SystemExit(f"OPENAI_API_KEY not found. Tried: {', '.join(tried)}")


__all__ = ["load_api_key"]
