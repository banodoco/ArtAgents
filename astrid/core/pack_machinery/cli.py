"""Compatibility re-export shim for ``astrid.core.pack_machinery.cli``."""

from astrid.core.pack import cli as _canonical
from astrid.core.pack.cli import *  # noqa: F401,F403

__all__ = _canonical.__all__
