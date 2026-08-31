"""Pure kernel schema inventory used by static gates.

This is declaration data only. Astrid's live process does not parse or apply
SQLite migrations; historical database work belongs to the standalone offline
migrator in the runtime repository.
"""

from __future__ import annotations

from dataclasses import dataclass

CORE_PACK = "core"
CORE_MIGRATION_VERSION = 1
CORE_MIGRATION_NAME = "initial"
CORE_MIGRATION_PATH = "sql/core/0001_initial.sql"


@dataclass(frozen=True)
class MigrationDescriptor:
    pack: str
    version: int
    name: str
    path: str
    owned_tables: frozenset[str]


CORE_TABLES = frozenset({
    "schema_migrations", "projects", "event_streams", "events",
    "command_receipts", "runs", "evidence_items", "tasks",
    "task_dependencies", "execution_attempts", "task_outputs", "media",
    "media_locations", "media_relations",
})
CORE_MIGRATIONS = (MigrationDescriptor(
    pack=CORE_PACK, version=CORE_MIGRATION_VERSION, name=CORE_MIGRATION_NAME,
    path=CORE_MIGRATION_PATH, owned_tables=CORE_TABLES,
),)
CORE_INDEXES = frozenset({
    "tasks_run_ordinal", "task_one_primary_result", "events_project_changes",
    "events_stream_kind_seq", "events_subject", "tasks_claim_order",
    "tasks_project_status", "tasks_run_status", "task_dependencies_reverse",
    "attempts_lease_expiry", "task_outputs_media", "media_project_page",
    "media_relations_to", "media_one_variant_parent", "evidence_run_time",
    "evidence_task",
})
PARTIAL_INDEXES = frozenset({
    "tasks_run_ordinal", "task_one_primary_result", "tasks_run_status",
    "media_one_variant_parent", "evidence_task",
})
KERNEL_MEDIA_TABLES = frozenset({"media", "media_locations", "media_relations"})
OPEN_STREAM_TYPE = True
FORBIDDEN_TABLES = frozenset({
    "run_steps", "run_step_tasks", "plans", "steps", "plan_steps", "step_tasks",
    "sessions", "threads", "leases", "identity", "variants", "selections",
    "accounts", "billing", "sync", "sync_state", "importer", "import_state",
    "legacy_aliases", "change_cursor", "event_chain", "audit_ledger", "current_run",
})


def declared_core_table_count() -> int:
    return len(CORE_TABLES)


def declared_core_index_count() -> int:
    return len(CORE_INDEXES)


__all__ = [
    "CORE_INDEXES", "CORE_MIGRATIONS", "CORE_MIGRATION_NAME",
    "CORE_MIGRATION_PATH", "CORE_MIGRATION_VERSION", "CORE_PACK", "CORE_TABLES",
    "FORBIDDEN_TABLES", "KERNEL_MEDIA_TABLES", "MigrationDescriptor",
    "OPEN_STREAM_TYPE", "PARTIAL_INDEXES", "declared_core_index_count",
    "declared_core_table_count",
]
