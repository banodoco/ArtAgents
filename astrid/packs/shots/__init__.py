"""Runtime-backed shots product mount.

The workspace runtime owns shot persistence and migrations. This package
contains only the executable nested CLI adapter and never hosts a repository,
schema, or local writer.
"""

from __future__ import annotations

# Product discovery imports only the CLI adapter; no local persistence symbols
# are exposed from this package.
