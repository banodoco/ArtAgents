"""Backward-compatibility shim for ``astrid.core._search``.

All public names now live in ``astrid.core.search``.  This module re-exports
everything so existing callers continue to work without changes.
"""

from astrid.core.search import *  # noqa: F401,F403
