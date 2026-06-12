"""Transitional compatibility shim — the canonical CAS now lives at
``astrid.core.io.cas``.

Import here works without deprecation noise so existing consumers don't
break during the transition.  New / updated code should import directly
from ``astrid.core.io.cas`` (or ``astrid.core.io``).
"""

from __future__ import annotations

from astrid.core.io.cas import (  # noqa: F401  — re-export
    cas_dir,
    cas_path,
    hash_file,
    intern,
    link_into_produces,
)

__all__ = ["cas_dir", "cas_path", "hash_file", "intern", "link_into_produces"]
