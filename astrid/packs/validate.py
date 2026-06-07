"""Compatibility re-export shim for ``astrid.packs.validate``.

The real implementation now lives in
``astrid.core.pack_machinery.validate`` (M1 Pack Layout Normalization).
This module is a thin pass-through that re-exports the public API
unchanged for backward compatibility.
"""

from astrid.core.pack_machinery.validate import *  # noqa: F401,F403
