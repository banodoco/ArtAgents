"""Thin re-export shim (M1 Pack Layout Normalization).

The canonical public API surface lives in ``astrid.packs.install``
until M2, when the implementation relocates here and test mocks are
updated.  This module re-exports everything to satisfy
``astrid.core.pack_machinery`` import conventions established during M1.
"""

from astrid.packs.install import *  # noqa: F401, F403
