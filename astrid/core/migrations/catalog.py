"""Declared v10 kernel (core) schema catalog.

Pure, importable catalog data for the 14-table agent-agnostic kernel. This
module is a declaration only: it never opens a database and never parses SQL
to infer ownership. Catalog tests and the migration runner consume these
constants so that "14 kernel tables" and "16 named kernel indexes" derive
from one audited source of truth rather than a hardcoded universal count.

The normative source is ``unified-data-model-plan-v10-20260813.md`` section
2.2 (kernel subset). The corresponding DDL lives in
``sql/core/0001_initial.sql`` next to this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Pack and migration identity
# ---------------------------------------------------------------------------

CORE_PACK = "core"
"""Pack id recorded in ``schema_migrations.pack`` for kernel migrations."""

CORE_MIGRATION_VERSION = 1
CORE_MIGRATION_NAME = "initial"
CORE_MIGRATION_PATH = "sql/core/0001_initial.sql"
"""Migration file path, relative to the ``astrid/core/migrations`` package."""

CONNECTION_PRAGMAS: tuple[str, ...] = (
    "foreign_keys = ON",
    "journal_mode = WAL",
    "synchronous = NORMAL",
    "busy_timeout = 5000",
)
"""Writable connection-level PRAGMAs asserted on normal opens (v10 section 2.2)."""


@dataclass(frozen=True)
class MigrationDescriptor:
    """One forward-only migration's declared identity and ownership."""

    pack: str
    version: int
    name: str
    path: str
    owned_tables: frozenset[str]


CORE_MIGRATIONS: tuple[MigrationDescriptor, ...] = (
    MigrationDescriptor(
        pack=CORE_PACK,
        version=CORE_MIGRATION_VERSION,
        name=CORE_MIGRATION_NAME,
        path=CORE_MIGRATION_PATH,
        owned_tables=frozenset(
            {
                "schema_migrations",
                "projects",
                "event_streams",
                "events",
                "command_receipts",
                "runs",
                "evidence_items",
                "tasks",
                "task_dependencies",
                "execution_attempts",
                "task_outputs",
                "media",
                "media_locations",
                "media_relations",
            }
        ),
    ),
)


def core_sql_path() -> Path:
    """Return the absolute path of the core creation migration SQL file."""
    return Path(__file__).with_name("sql") / "core" / "0001_initial.sql"


# ---------------------------------------------------------------------------
# Declared kernel tables and indexes
# ---------------------------------------------------------------------------

CORE_TABLES = frozenset(CORE_MIGRATIONS[0].owned_tables)
"""Exactly the audited 14 kernel tables."""

CORE_INDEXES = frozenset(
    {
        "tasks_run_ordinal",
        "task_one_primary_result",
        "events_project_changes",
        "events_stream_kind_seq",
        "events_subject",
        "tasks_claim_order",
        "tasks_project_status",
        "tasks_run_status",
        "task_dependencies_reverse",
        "attempts_lease_expiry",
        "task_outputs_media",
        "media_project_page",
        "media_relations_to",
        "media_one_variant_parent",
        "evidence_run_time",
        "evidence_task",
    }
)
"""Exactly the 16 named kernel indexes transcribed from v10 section 2.2."""

PARTIAL_INDEXES = frozenset(
    {
        "tasks_run_ordinal",
        "task_one_primary_result",
        "tasks_run_status",
        "media_one_variant_parent",
        "evidence_task",
    }
)
"""Kernel indexes declared with a WHERE clause (partial indexes)."""

KERNEL_MEDIA_TABLES = frozenset({"media", "media_locations", "media_relations"})
"""Media is kernel citizenship: these tables belong to the core, not a pack."""

OPEN_STREAM_TYPE = True
"""``event_streams.stream_type`` has no DDL CHECK; vocabulary is registry-enforced."""


def declared_core_table_count() -> int:
    """Return the declared kernel table count (14)."""
    return len(CORE_TABLES)


def declared_core_index_count() -> int:
    """Return the declared kernel index count (16)."""
    return len(CORE_INDEXES)


# ---------------------------------------------------------------------------
# Forbidden schema vocabulary
# ---------------------------------------------------------------------------

FORBIDDEN_TABLES = frozenset(
    {
        # v9 plan/step machinery (deleted, never recreated).
        "run_steps",
        "run_step_tasks",
        "plans",
        "steps",
        "plan_steps",
        "step_tasks",
        # v9 session/thread/lease/identity file-state tables.
        "sessions",
        "threads",
        "leases",
        "identity",
        "variants",
        "selections",
        # Speculative platform / legacy / cursor tables.
        "accounts",
        "billing",
        "sync",
        "sync_state",
        "importer",
        "import_state",
        "legacy_aliases",
        "change_cursor",
        "event_chain",
        "audit_ledger",
        "current_run",
    }
)
"""Tables that must never appear in the core or any installed pack catalog.

Absence of these tables is affirmative evidence for the v10 "no dormant
platform" invariant (v10 section 5.1) and the m1 plan step 3 rule that no
plan, step, session, thread, lease, account, billing, sync, legacy-alias,
importer, or change-cursor table is added.
"""


__all__ = [
    "CONNECTION_PRAGMAS",
    "CORE_INDEXES",
    "CORE_MIGRATIONS",
    "CORE_MIGRATION_NAME",
    "CORE_MIGRATION_PATH",
    "CORE_MIGRATION_VERSION",
    "CORE_PACK",
    "CORE_TABLES",
    "FORBIDDEN_TABLES",
    "KERNEL_MEDIA_TABLES",
    "MigrationDescriptor",
    "OPEN_STREAM_TYPE",
    "PARTIAL_INDEXES",
    "core_sql_path",
    "declared_core_index_count",
    "declared_core_table_count",
]
