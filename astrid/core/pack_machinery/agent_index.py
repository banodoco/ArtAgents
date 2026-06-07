"""Compatibility re-export shim for ``astrid.core.pack_machinery.agent_index``."""

from astrid.core.pack import agent_index as _canonical
from astrid.core.pack.agent_index import *  # noqa: F401,F403

__all__ = _canonical.__all__
