"""Compatibility re-export shim for ``astrid.core.pack_machinery.validate``."""

from astrid.core.pack import validate as _canonical
from astrid.core.pack.validate import *  # noqa: F401,F403

__all__ = _canonical.__all__
