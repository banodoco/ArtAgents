"""Compatibility re-export shim for ``astrid.packs.agent_index``.

The canonical implementation lives at ``astrid.core.pack.agent_index``.
This module is a thin pass-through that re-exports the public API
unchanged for backward compatibility.
"""

from astrid.core.pack.agent_index import *  # noqa: F401,F403
