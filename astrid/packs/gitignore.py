"""Compatibility re-export shim for gitignore machinery.

The canonical implementation lives at ``astrid.core.pack.gitignore``.
This module re-exports the public API so existing import sites continue
to work during the M2 transition.

This shim will be removed in M2 after all callers have been updated.
"""

from astrid.core.pack.gitignore import (  # noqa: F401
    GitIgnoreFilter,
    gitignore_filter,
)

__all__ = ["GitIgnoreFilter", "gitignore_filter"]
