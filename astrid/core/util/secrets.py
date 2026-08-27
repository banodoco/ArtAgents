"""API key resolution with the frozen m4 precedence.

Resolution order (frozen in m4, plan Step 31):

1. **Explicit option** — a non-empty caller-supplied value.
2. **Process environment** — ``os.environ`` (or the injected environment
   mapping).
3. **Supported OS keychain (injectable boundary)** — consulted only when an
   injected :class:`KeychainProvider` supplies a value; the default boundary
   never touches an OS keychain and the ``keyring`` dependency is imported
   lazily, so domain-only use and tests never access a keychain.
4. **One explicitly named env file** — a lower-priority convenience, consulted
   only when the caller names ``env_file`` explicitly.

Broad cwd/repository/workspace/home env-file scavenging is **removed**: an env
file is never discovered implicitly, and no placeholder/search profile adds
paths.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Protocol

from astrid.core.contracts.errors import AstridError

EnvSearchProfile = Literal["default", "reigh"]

_RECOVERY_HINTS: dict[str, str] = {
    "GIPHY_API_KEY": "Get a GIPHY API key at https://developers.giphy.com/dashboard/.",
}


# ---------------------------------------------------------------------------
# Injectable keychain boundary
# ---------------------------------------------------------------------------


class KeychainProvider(Protocol):
    """Injectable OS-keychain boundary (tier 3 of the frozen precedence).

    Implementations return the stored secret for *name* or ``None`` when the
    keychain is unavailable or holds no value. Injection keeps the boundary
    testable and keeps domain-only use and tests free of keychain access.
    """

    def get(self, name: str) -> str | None:
        """Return the stored secret for *name*, or ``None`` when unavailable."""
        ...


class NullKeychainProvider:
    """Default keychain boundary: never accesses an OS keychain."""

    def get(self, name: str) -> str | None:
        return None


class OSKeychainProvider:
    """Supported OS-keychain boundary backed by the ``keyring`` dependency.

    ``keyring`` is imported **lazily** inside :meth:`get`, so importing this
    module or resolving a credential that an earlier precedence tier satisfies
    never accesses a keychain (no eager keychain access). Any keychain
    unavailability is treated as "no value", letting resolution fall through to
    the named env file tier.
    """

    def get(self, name: str) -> str | None:
        try:
            import keyring  # noqa: PLC0415 - lazy: no eager keychain access
        except Exception:  # noqa: BLE001 - keychain absence degrades to "no value"
            return None
        try:
            value = keyring.get_password("astrid", name)
        except Exception:  # noqa: BLE001 - backend failure degrades to "no value"
            return None
        if not value:
            return None
        return value


# ---------------------------------------------------------------------------
# Env-file parsing and discovery
# ---------------------------------------------------------------------------


def read_env_value(env_path: Path | str, key: str) -> str:
    env_path = Path(env_path)
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
    """Return at most the one explicitly named env file.

    Broad cwd/repository/workspace/home env-file scavenging was removed in m4:
    an env file is consulted **only** when the caller names it explicitly. The
    ``profile`` argument is retained for call-site compatibility
    (``astrid.core.integrations.reigh.env``); both profiles behave identically
    and add no implicit paths.
    """
    if env_file is None:
        return []
    resolved = env_file.expanduser().resolve()
    return [resolved]


# ---------------------------------------------------------------------------
# Canonical resolver
# ---------------------------------------------------------------------------


def load_api_key(
    name: str,
    env_file: Path | None = None,
    *,
    explicit: str | None = None,
    keychain: KeychainProvider | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Resolve *name* in the frozen m4 precedence.

    Args:
        name: The environment variable name (e.g. ``"FAL_KEY"``).
        env_file: An explicitly named .env file, consulted as the **lowest**
            priority convenience tier only.
        explicit: A caller-supplied explicit value (highest priority tier).
        keychain: An injectable keychain boundary (tier 3). When ``None``, the
            default :class:`NullKeychainProvider` is used and no OS keychain is
            ever accessed.
        environ: The process environment mapping to read for tier 2. Defaults
            to ``os.environ``.

    Returns:
        The resolved key string.

    Raises:
        AstridError: If no tier yields a value. The message names the tiers
            tried and never contains a secret value, file contents, or paths.
    """
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()

    env = os.environ if environ is None else environ
    if value := env.get(name, "").strip():
        return value

    provider = keychain if keychain is not None else NullKeychainProvider()
    if value := (provider.get(name) or "").strip():
        return value

    if env_file is not None:
        if value := read_env_value(env_file, name).strip():
            return value

    recovery = f"set {name} in your environment or pass an explicit env file"
    if hint := _RECOVERY_HINTS.get(name):
        recovery = f"{recovery}. {hint}"
    raise AstridError(
        f"{name} not found. Tried: explicit option, environment, keychain, env file.",
        recovery_command=recovery,
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
