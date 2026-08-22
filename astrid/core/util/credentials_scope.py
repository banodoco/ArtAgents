"""CredentialsScope — scoped API key resolution (tier-3).

Provides a single in-process credentials resolver that delegates to
``astrid.core.util.secrets.load_api_key``.  One ``SCOPE_REGISTRY`` entry is
registered per ``credentials.<provider>`` key; each resolver returns a
``CredentialsScope`` populated with that provider's resolved value (or
raises ``AstridError`` when the key is missing).

Resolution precedence (frozen in m4, plan Step 31):

1. explicit option (caller-supplied key, ``ScopeRequest.explicit`` or the
   ``explicit`` argument);
2. process environment;
3. injectable supported OS keychain (tier 3 — the default boundary never
   accesses a keychain; ``keyring`` is imported lazily, never eagerly);
4. one explicitly named env file, as a lower-priority convenience only.

Broad cwd/repository/workspace/home env-file scavenging is absent.

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

from dataclasses import dataclass
from pathlib import Path

from astrid.core.contracts.errors import AstridError
from astrid.core.contracts.scoped_config import (
    SCOPE_REGISTRY,
    ScopedConfig,
    ScopeRequest,
)
from astrid.core.util.secrets import KeychainProvider, load_api_key

# ---------------------------------------------------------------------------
# Canonical provider → env-var table
# ---------------------------------------------------------------------------

_PROVIDER_ENV: dict[str, str] = {
    "fal": "FAL_KEY",
    "wavespeed": "WAVESPEED_API_KEY",
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
        explicit: str | None = None,
        keychain: KeychainProvider | None = None,
    ) -> str:
        """Resolve *provider*'s API key in the frozen m4 precedence.

        Args:
            provider: Canonical provider key (must be in ``_PROVIDER_ENV``).
            env_file: Optional explicitly named ``.env`` file (lowest-priority
                      convenience tier, forwarded to ``load_api_key``).
            explicit: Optional caller-supplied explicit value (highest
                      priority tier).
            keychain: Optional injectable keychain boundary (tier 3). When
                      ``None`` no OS keychain is ever accessed.

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
        return load_api_key(
            env_var,
            env_file=env_file,
            explicit=explicit,
            keychain=keychain,
        )


# ---------------------------------------------------------------------------
# Per-provider scope resolvers
# ---------------------------------------------------------------------------

def _make_resolver(provider: str, env_var: str):
    """Factory: create a scope resolver for *provider*."""

    def _resolve(request: ScopeRequest) -> CredentialsScope:
        # Tier 1: explicit overrides take priority (caller-supplied key).
        # ScopeRequest.explicit keys are scope keys ("credentials.fal"); the
        # bare provider key ("fal") is also accepted for compatibility.
        explicit = request.explicit
        if explicit is not None:
            for key in (f"credentials.{provider}", provider):
                value = explicit.get(key)
                if value is not None:
                    return CredentialsScope(provider=provider, value=str(value))

        # Tiers 2–4: process environment (from the request's env mapping when
        # present, else os.environ), injectable keychain boundary (default:
        # none), then an explicitly named env file (not carried by
        # ScopeRequest, so the registry path resolves through the first three
        # tiers; direct callers may pass env_file via CredentialsScope.get).
        try:
            value = load_api_key(env_var, environ=request.env)
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
