"""Stable I/O primitives.

Content-addressable storage for produces artifacts and related I/O utilities.
"""

from __future__ import annotations

from .cas import cas_dir, cas_path, hash_file, intern, link_into_produces

__all__ = ["cas_dir", "cas_path", "hash_file", "intern", "link_into_produces"]
