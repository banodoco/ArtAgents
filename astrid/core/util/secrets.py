"""API key resolution via environment variables and .env file walk."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from astrid.core.contracts.errors import AstridError

EnvSearchProfile = Literal["default", "reigh"]


def read_env_value(env_path: Path, key: str) -> str:
    if not env_path.is_file():
        return ""
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        env_key, env_value = line.split("=", 1)
        if env_key.strip() == key:
            return env_value.strip().strip('"').strip("'")
    return ""


def candidate_env_files(
    env_file: Path | None = None,
    *,
    profile: EnvSearchProfile = "default",
) -> list[Path]:
    candidates: list[Path] = []
    if env_file is not None:
        candidates.append(env_file)
    repo_root = Path(__file__).resolve().parents[2]
    workspace = repo_root.parent
    if profile == "reigh":
        names = ("this.env", ".env.local", ".env")
        candidates.extend(
            [
                Path.cwd() / name
                for name in names
            ]
        )
        candidates.extend(repo_root / name for name in names)
        candidates.extend(workspace / name for name in names)
        candidates.extend(workspace / "reigh-app" / name for name in names)
        candidates.extend(Path.home() / name for name in names)
        candidates.extend(Path.home() / ".codex" / name for name in names)
    else:
        # Local override convention: `.env.local` wins over `.env` in the
        # working/repo/workspace dirs (so a developer's gitignored
        # `.env.local` is honored, matching the `reigh` profile).
        local_names = (".env.local", ".env")
        candidates.extend(Path.cwd() / name for name in local_names)
        candidates.append(Path(__file__).resolve().parent / ".env")
        candidates.extend(repo_root / name for name in local_names)
        candidates.extend(workspace / name for name in local_names)
        candidates.extend(
            [
                workspace / "reigh-app" / ".env",
                workspace / "reigh-worker" / ".env",
                workspace / "reigh-worker-orchestrator" / ".env",
                Path.home() / ".env",
                Path.home() / ".codex" / ".env",
                Path.home() / ".claude" / ".env",
                Path.home() / ".hermes" / ".env",
            ]
        )
    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _read_env_value(env_path: Path, key: str) -> str:
    return read_env_value(env_path, key)


def _candidate_env_files(env_file: Path | None = None) -> list[Path]:
    return candidate_env_files(env_file)


def load_api_key(name: str, env_file: Path | None = None) -> str:
    """Resolve *name* from candidate .env files first, then the environment.

    ``.env`` files take precedence over an exported environment variable so a
    stale or empty shell value never shadows the key the repo actually carries.
    An explicit ``env_file`` is checked before the standard ``.env`` walk; the
    process environment is the final fallback when no ``.env`` defines *name*.

    Args:
        name: The environment variable name (e.g. ``"FAL_KEY"``).
        env_file: An explicit .env file path, checked before the standard walk.

    Returns:
        The resolved key string.

    Raises:
        AstridError: If the key is not found in any location.
    """
    tried: list[str] = []
    for candidate in candidate_env_files(env_file):
        tried.append(str(candidate))
        if key := read_env_value(candidate, name):
            return key
    if key := os.environ.get(name, "").strip():
        return key
    tried.append(f"{name} environment variable")
    raise AstridError(
        f"{name} not found. Tried: {', '.join(tried)}",
        recovery_command=f"set {name} in your environment or a .env file",
    )


def scrub_secret(value: str, text: str) -> str:
    """Mask every occurrence of *value* in *text* with ``"***"``.

    Args:
        value: The secret string to mask.
        text: The text that may contain the secret.

    Returns:
        *text* with all occurrences of *value* replaced by ``"***"``.
    """
    if not value:
        return text
    return text.replace(value, "***")
