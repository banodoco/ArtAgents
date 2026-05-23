"""Core Astrid framework modules."""

from .alias_resolver import AliasResolutionError, AliasResolver, create_shared_alias_resolver

__all__ = [
    "AliasResolutionError",
    "AliasResolver",
    "create_shared_alias_resolver",
]
