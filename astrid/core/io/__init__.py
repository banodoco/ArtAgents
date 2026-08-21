"""Stable I/O primitives.

Content-addressable storage for produces artifacts and related I/O utilities.

``astrid.core.io.inbox`` is also available here.  It must be imported
directly (``from astrid.core.io.inbox import ...``) rather than eagerly
re-exported from this package, because inbox currently carries a temporary
transitional dependency on the retired task-mode gate that would create a
circular import if loaded at package-init time.  See the inbox module
docstring for details.
"""

from __future__ import annotations

from .cas import cas_dir, cas_path, hash_file, intern, link_into_produces

__all__ = ["cas_dir", "cas_path", "hash_file", "intern", "link_into_produces"]
