"""CredentialsScope — scoped API key resolution (tier-3).

Provides a single in-process credentials resolver that delegates to
``astrid.core.util.secrets.load_api_key``.  One ``SCOPE_REGISTRY`` entry is
registered per ``credentials.<provider>`` key; each resolver returns a
``CredentialsScope`` populated with that provider's resolved value (or
raises ``AstridError`` when the key is missing).

Canonical provider → env-var table
----------------------------------
fal        → ``FAL_KEY``
openai     → ``OPENAI_API_KEY``
anthropic  → ``ANTHROPIC_API_KEY``
deepseek   → ``DEEPSEEK_API_KEY``
fireworks  → ``FIREWORKS_API_KEY``
gemini     → ``GEMINI_API_KEY``
giphy      → ``GIPHY_API_KEY``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Mapping

from astrid.core.contracts.errors import AstridError
from astrid.core.contracts.scoped_config import (
    SCOPE_REGISTRY,
    ScopedConfig,
    ScopeRequest,
)
from astrid.core.util.secrets import load_api_key

# ---------------------------------------------------------------------------
# Canonical provider → env-var table
# ---------------------------------------------------------------------------

_PROVIDER_ENV: dict[str, str] = {
    "fal": "FAL_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "giphy": "GIPHY_API_KEY",
}

# ---------------------------------------------------------------------------
# CredentialsScope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CredentialsScope(ScopedConfig):
    """Resolved credentials for a single provider.

    Instances are returned by the per-provider resolvers registered in
    ``SCOPE_REGISTRY`` under ``credentials.<provider>`` keys.
    """

    provider: str
    """Provider key (e.g. ``"fal"``, ``"openai"``)."""

    value: str
    """The resolved API key value."""

    @classmethod
    def get(
        cls,
        provider: str,
        *,
        env_file: Path | None = None,
    ) -> str:
        """Resolve *provider*'s API key via the existing .env walk.

        Args:
            provider: Canonical provider key (must be in ``_PROVIDER_ENV``).
            env_file: Optional explicit ``.env`` file path forwarded to
                      ``load_api_key``.

        Returns:
            The resolved API key string.

        Raises:
            AstridError: If the provider is unknown or the key is not found.
        """
        env_var = _PROVIDER_ENV.get(provider)
        if env_var is None:
            valid = ", ".join(sorted(_PROVIDER_ENV))
            raise AstridError(
                f"Unknown credentials provider: {provider!r} (valid: {valid})",
                recovery_command="use a canonical provider name (fal, openai, anthropic, deepseek, fireworks, gemini, giphy)",
            )
        return load_api_key(env_var, env_file=env_file)


# ---------------------------------------------------------------------------
# Per-provider scope resolvers
# ---------------------------------------------------------------------------

def _make_resolver(provider: str, env_var: str):
    """Factory: create a scope resolver for *provider*."""

    def _resolve(request: ScopeRequest) -> CredentialsScope:
        # Explicit overrides take priority (caller-supplied key).
        explicit = request.explicit
        if explicit is not None:
            value = explicit.get(provider)
            if value is not None:
                return CredentialsScope(provider=provider, value=str(value))

        # Fall back to the .env walk.
        try:
            value = load_api_key(env_var)
        except AstridError:
            raise  # re-raise — missing credentials are fatal
        return CredentialsScope(provider=provider, value=value)

    return _resolve


# Register one resolver per provider at import time.
for _provider, _env_var in _PROVIDER_ENV.items():
    SCOPE_REGISTRY.register(
        f"credentials.{_provider}",
        _make_resolver(_provider, _env_var),
    )
