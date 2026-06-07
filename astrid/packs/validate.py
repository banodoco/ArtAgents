"""Compatibility re-export shim for ``astrid.packs.validate``.

The canonical implementation lives at ``astrid.core.pack.validate``.
This module is a thin pass-through that re-exports the public API
unchanged for backward compatibility.
"""

from astrid.core.pack.validate import *  # noqa: F401,F403
