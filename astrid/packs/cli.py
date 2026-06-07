"""Compatibility re-export shim for ``astrid.packs.cli``.

The canonical implementation lives at ``astrid.core.pack.cli``.
This module is a thin pass-through that re-exports the public API
unchanged for backward compatibility.
"""

from astrid.core.pack.cli import *  # noqa: F401,F403
