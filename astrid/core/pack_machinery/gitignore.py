"""Compatibility re-export shim for ``astrid.core.pack_machinery.gitignore``."""

from astrid.core.pack import gitignore as _canonical
from astrid.core.pack.gitignore import *  # noqa: F401,F403

__all__ = _canonical.__all__
