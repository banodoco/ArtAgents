"""Canonical child-process environment policy."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping

from astrid.core.env_vars import (
    ASTRID_ACTOR,
    ASTRID_AUTHOR_TEST,
    ASTRID_INTERNAL_INVOCATION,
)
from astrid.core.env_vars import (
    ASTRID_HOME as ASTRID_HOME_ENV,
)
from astrid.core.env_vars import (
    ASTRID_PROJECT_RUN as PROJECT_RUN_ENV,
)
from astrid.core.env_vars import (
    ASTRID_PROJECTS_ROOT as PROJECTS_ROOT_ENV,
)
from astrid.core.env_vars import (
    ASTRID_SESSION_ID as ASTRID_SESSION_ID_ENV,
)
from astrid.core.env_vars import (
    ASTRID_TASK_ITEM_ID as TASK_ITEM_ID_ENV,
)
from astrid.core.env_vars import (
    ASTRID_TASK_ITERATION as TASK_ITERATION_ENV,
)
from astrid.core.env_vars import (
    ASTRID_TASK_PROJECT as TASK_PROJECT_ENV,
)
from astrid.core.env_vars import (
    ASTRID_TASK_RUN_ID as TASK_RUN_ID_ENV,
)
from astrid.core.env_vars import (
    ASTRID_TASK_STEP_ID as TASK_STEP_ID_ENV,
)
from astrid.core.env_vars import (
    ASTRID_THEMES_ROOT as THEMES_ROOT_ENV,
)
from astrid.core.env_vars import (
    HYPE_ACTIVE_THEME as ACTIVE_THEME_ENV,
)

_SAFE_BASE_ENV = frozenset(
    {
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LOGNAME",
        "PATH",
        "PWD",
        "SHELL",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USER",
        "USERNAME",
        "VIRTUAL_ENV",
        "PYENV_VERSION",
    }
)

_ASTRID_PROPAGATED_ENV = frozenset(
    {
        ASTRID_HOME_ENV,
        ASTRID_SESSION_ID_ENV,
        PROJECTS_ROOT_ENV,
        PROJECT_RUN_ENV,
        ASTRID_AUTHOR_TEST,
        ASTRID_INTERNAL_INVOCATION,
        ACTIVE_THEME_ENV,
        TASK_RUN_ID_ENV,
        TASK_PROJECT_ENV,
        TASK_STEP_ID_ENV,
        TASK_ITEM_ID_ENV,
        TASK_ITERATION_ENV,
        THEMES_ROOT_ENV,
    }
)

_SECRET_NAME_RE = re.compile(
    r"(^|_)(API[_-]?KEY|AUTH|CREDENTIAL|PASSWORD|SECRET|TOKEN)($|_)", re.IGNORECASE
)
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SubprocessEnvPolicyError(ValueError):
    """Raised when a requested subprocess env shape violates policy."""


def build_child_subprocess_env(
    *,
    base: Mapping[str, str] | None = None,
    parent: Mapping[str, str] | None = None,
    explicit_env: Mapping[str, str] | None = None,
    passthrough: Iterable[str] = (),
    declared_passthrough: Iterable[str] = (),
) -> dict[str, str]:
    """Return the safe environment for an Astrid child process.

    ``base`` contributes only known-safe process variables unless a key is
    declared and requested through ``passthrough``. Astrid task/session/project
    invariants are copied from ``parent`` and take precedence over ``base``.
    """

    base_env = os.environ if base is None else base
    parent_env = os.environ if parent is None else parent
    requested = _normalize_names(passthrough, "passthrough")
    declared = _normalize_names(declared_passthrough, "declared_passthrough")
    undeclared = requested - declared
    if undeclared:
        names = ", ".join(sorted(undeclared))
        raise SubprocessEnvPolicyError(f"env passthrough requested without declaration: {names}")

    env: dict[str, str] = {}
    for key, value in base_env.items():
        if key in _SAFE_BASE_ENV or key in requested:
            if not _is_secret_name(key):
                env[key] = str(value)

    for key, value in (explicit_env or {}).items():
        env[str(key)] = str(value)

    env.pop(ASTRID_ACTOR, None)
    for key in sorted(_ASTRID_PROPAGATED_ENV):
        value = parent_env.get(key)
        if value is not None:
            env[key] = str(value)
    return env


def _normalize_names(values: Iterable[str], label: str) -> set[str]:
    names: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value:
            raise SubprocessEnvPolicyError(f"{label} entries must be non-empty strings")
        if not _ENV_NAME_RE.fullmatch(value):
            raise SubprocessEnvPolicyError(f"{label} entry {value!r} is not a valid environment variable name")
        if _is_secret_name(value):
            raise SubprocessEnvPolicyError(f"{label} entry {value!r} looks secret-like")
        names.add(value)
    return names


def _is_secret_name(name: str) -> bool:
    return bool(_SECRET_NAME_RE.search(name))


__all__ = [
    "ASTRID_ACTOR",
    "ASTRID_AUTHOR_TEST",
    "ASTRID_INTERNAL_INVOCATION",
    "ACTIVE_THEME_ENV",
    "SubprocessEnvPolicyError",
    "TASK_ITEM_ID_ENV",
    "TASK_ITERATION_ENV",
    "TASK_PROJECT_ENV",
    "TASK_RUN_ID_ENV",
    "TASK_STEP_ID_ENV",
    "THEMES_ROOT_ENV",
    "build_child_subprocess_env",
]
