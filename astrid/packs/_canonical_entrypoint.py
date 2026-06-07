"""Compatibility re-export shim for ``astrid.packs._canonical_entrypoint``.

The canonical implementation now lives in ``astrid.core.pack.entrypoint``.
Pack ``run.py`` files still import through this shim for backward compatibility.
"""

from astrid.core.pack.entrypoint import *  # noqa: F401,F403
