"""Thread state primitives for Astrid creative runs.

DEPRECATED (Sprint 1): the user-facing ``astrid thread`` CLI verb was retired
in T8/T12. This package is retained as an INTERNAL library (DEC-001) because
orchestrator/executor runners and pack ``run.py`` files still depend on
``ThreadIndexStore`` and the variant-sidecar protocol.

m5a removed only the no-op thread wrapper surface (``astrid/threads/wrapper.py``
and its re-exports). The lineage modules (``ids``, ``index``, ``record``,
``schema``) remain in place.

TODO(m5b): retire astrid/threads/ entirely; depends on orchestrator/executor
runner rewrite and pack run.py migration off ThreadIndexStore + variant sidecars.
"""

from __future__ import annotations

from .ids import generate_group_id, generate_run_id, generate_thread_id, is_ulid
from .index import ThreadIndexError, ThreadIndexLockTimeout, ThreadIndexStore
from .record import build_run_record, finalize_run_record
from .schema import SCHEMA_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "ThreadIndexError",
    "ThreadIndexLockTimeout",
    "ThreadIndexStore",
    "build_run_record",
    "finalize_run_record",
    "generate_group_id",
    "generate_run_id",
    "generate_thread_id",
    "is_ulid",
]
