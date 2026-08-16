"""Kernel store: SQLite database opening and the dedicated single writer.

(m1 plan step 6.) Re-exports the writable/read-only open functions from
``astrid.core.store.database`` and the dedicated :class:`DatabaseWriter`
service from ``astrid.core.store.writer``.

Pack code never imports this module to open its own connections: packs
receive the kernel unit of work (plan step 7) and never own writers (v10
section 2.3 law 5; decision artifact section 4).
"""

from astrid.core.store.database import (
    PRAGMA_QUERIES,
    apply_connection_pragmas,
    inspect_connection_pragmas,
    open_database,
)
from astrid.core.store.writer import (
    DatabaseWriter,
    WriterBusyError,
    WriterError,
    WriterSession,
    WriterShutdownError,
)

__all__ = [
    "DatabaseWriter",
    "PRAGMA_QUERIES",
    "WriterBusyError",
    "WriterError",
    "WriterSession",
    "WriterShutdownError",
    "apply_connection_pragmas",
    "inspect_connection_pragmas",
    "open_database",
]
