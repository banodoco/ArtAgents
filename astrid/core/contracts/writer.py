"""Writer error contracts shared without importing the SQLite writer."""

from __future__ import annotations


class WriterError(RuntimeError):
    """Base error for the dedicated single-writer service."""


class WriterBusyError(WriterError):
    """Raised when a write callback hit the SQLite busy timeout."""


class WriterShutdownError(WriterError):
    """Raised when work is submitted after the writer has been closed."""


class TransactionControlError(WriterError):
    """Raised when a caller attempts to control transactions directly."""


class WriterSidecarError(WriterError):
    """Raised when the WAL sidecar was replaced beneath the live writer."""


__all__ = [
    "TransactionControlError",
    "WriterBusyError",
    "WriterError",
    "WriterShutdownError",
    "WriterSidecarError",
]
