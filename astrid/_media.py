"""Backward-compatibility shim for ``astrid._media``.

All public names now live in ``astrid.media``.  This module re-exports
everything so existing callers continue to work without changes.
"""

from astrid.media import *  # noqa: F401,F403
