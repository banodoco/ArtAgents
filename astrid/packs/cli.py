"""Compatibility re-export shim for ``astrid.packs.cli``.

The real implementation now lives in
``astrid.core.pack_machinery.cli`` (M1 Pack Layout Normalization).
This module is a thin pass-through that re-exports the public API
unchanged for backward compatibility.
"""

from astrid.core.pack_machinery.cli import *  # noqa: F401,F403
