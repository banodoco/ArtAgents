"""Registry and standard composition tests (m1 plan step 2).

Covers the kernel-only (core) registry that does not require Astrid packs, the
explicit standard-Astrid composition that registers exactly timeline, shots,
and references without discovery or the capability-pack loader, duplicate and
undeclared vocabulary rejection, and malformed-manifest / dependency-grammar
errors. The plan-step-8 section at the bottom tests the runtime enforcement
of the composed vocabulary: stream/event/command declaration checks and
aggregate/type/project agreement for core and timeline streams, with
undeclared paths proven to change zero rows.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import astrid.packs as packs_package
from astrid.core.events.registry import (
    CORE_COMMAND_KINDS,
    CORE_CONFORMANCE_DIMENSIONS,
    CORE_EVENT_KINDS,
    CORE_PACK_ID,
    CORE_REPOSITORIES,
    CORE_STREAM_TYPES,
    STREAM_AGGREGATE_RULES,
    aggregate_rule_for,
    core_only_registry,
    core_schema_pack_manifest,
    register_core_vocabulary,
    validate_command_kind,
    validate_event_append,
    validate_event_kind,
    validate_stream_creation,
    validate_stream_type,
)
from astrid.core.migrations.catalog import CORE_MIGRATIONS, CORE_TABLES
from astrid.core.repositories.errors import (
    CommandVocabularyError,
    EventVocabularyError,
    StreamAgreementError,
    StreamVocabularyError,
)
from astrid.core.schema_packs.manifest import (
    SchemaPackManifestValidationError,
    parse_schema_pack_manifest,
)
from astrid.core.schema_packs.registry import (
    SchemaPackDuplicateError,
    SchemaPackRegistry,
    SchemaPackRegistryFrozenError,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.packs import (
    STANDARD_SCHEMA_PACKS,
    register_standard_schema_packs,
)

CORE_TABLE_COUNT = len(CORE_TABLES)
# 14 kernel + timelines + shots/shot_items/generations/generation_variants
# + the 3 reference tables.
STANDARD_TABLE_COUNT = CORE_TABLE_COUNT + 1 + 4 + 3


def _empty_manifest(id_: str = "probe") -> dict:
    """A minimal valid 11-field manifest mapping for duplicate-vocabulary probes."""
    return {
        "id": id_,
        "version": 1,
        "depends_on": [],
        "migrations": [],
        "stream_types": [],
        "event_kinds": [],
        "command_kinds": [],
        "repositories": [],
        "conformance": [],
        "cli_mounts": {},
        "bridge_mounts": [],
    }


# ---------------------------------------------------------------------------
# Kernel-only composition (no Astrid packs required)
# ---------------------------------------------------------------------------


def test_core_only_registry_builds_without_any_pack() -> None:
    frozen = core_only_registry()
    assert list(frozen.packs) == [CORE_PACK_ID]
    assert frozen.has_pack("timeline") is False
    assert frozen.has_pack("shots") is False
    assert frozen.has_pack("references") is False


def test_core_only_registry_declares_project_task_run_stream_types() -> None:
    frozen = core_only_registry()
    # The frozen registry sorts mappings by key; membership and ownership are
    # the contract, and declaration order is preserved on the manifest itself.
    assert set(frozen.stream_types) == set(CORE_STREAM_TYPES)
    assert core_schema_pack_manifest().stream_types == CORE_STREAM_TYPES
    for stream_type in CORE_STREAM_TYPES:
        assert frozen.stream_types[stream_type] == CORE_PACK_ID


def test_core_only_registry_declares_m1_core_event_and_command_kinds() -> None:
    frozen = core_only_registry()
    for kind in CORE_EVENT_KINDS:
        assert frozen.event_kinds[kind] == CORE_PACK_ID
    for kind in CORE_COMMAND_KINDS:
        assert frozen.command_kinds[kind] == CORE_PACK_ID


def test_core_only_registry_owns_exactly_the_audited_core_tables() -> None:
    frozen = core_only_registry()
    assert len(frozen.tables) == CORE_TABLE_COUNT == 14
    for table in CORE_TABLES:
        assert frozen.tables[table] == CORE_PACK_ID
    # The core manifest mirrors the catalog migration descriptor exactly.
    core_migration = CORE_MIGRATIONS[0]
    registered = frozen.migration(CORE_PACK_ID, core_migration.version)
    assert registered is not None
    assert registered.name == core_migration.name
    assert registered.path == core_migration.path
    assert set(registered.tables) == set(core_migration.owned_tables)


def test_core_manifest_passes_strict_11_field_validation() -> None:
    manifest = core_schema_pack_manifest()
    assert manifest.id == CORE_PACK_ID
    assert manifest.version == 1
    assert manifest.depends_on == ()
    assert manifest.stream_types == CORE_STREAM_TYPES
    assert manifest.event_kinds == CORE_EVENT_KINDS
    assert manifest.command_kinds == CORE_COMMAND_KINDS


# ---------------------------------------------------------------------------
# Standard composition: exactly timeline, shots, references, no discovery
# ---------------------------------------------------------------------------


def test_standard_composition_registers_exactly_three_packs() -> None:
    registry = SchemaPackRegistry()
    register_standard_schema_packs(registry)
    frozen = registry.freeze()
    assert list(frozen.packs) == ["references", "shots", "timeline"]
    assert frozen.has_pack(CORE_PACK_ID) is False  # core is registered separately


def test_standard_composition_declares_the_fixed_pack_order() -> None:
    assert STANDARD_SCHEMA_PACKS == ("timeline", "shots", "references")


def test_standard_composition_has_no_discovery_beyond_in_tree_manifests() -> None:
    packs_root = Path(packs_package.__file__).parent
    schema_pack_files = sorted(packs_root.glob("*/schema-pack.yaml"))
    discovered = sorted(path.parent.name for path in schema_pack_files)
    assert discovered == ["references", "shots", "timeline"]
    assert len(schema_pack_files) == len(STANDARD_SCHEMA_PACKS) == 3


def test_standard_composition_derives_20_table_catalog() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    frozen = registry.freeze()
    assert len(frozen.tables) == STANDARD_TABLE_COUNT == 22
    assert frozen.tables["timelines"] == "timeline"
    assert frozen.tables["shots"] == "shots"
    assert frozen.tables["shot_items"] == "shots"
    assert frozen.tables["generations"] == "shots"
    assert frozen.tables["generation_variants"] == "shots"
    assert frozen.tables["project_references"] == "references"
    assert frozen.tables["media_references"] == "references"
    assert frozen.tables["reference_links"] == "references"


def test_standard_composition_declares_pack_vocabulary_and_mounts() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    frozen = registry.freeze()

    assert frozen.stream_types["timeline.timeline"] == "timeline"
    assert frozen.event_kinds["timeline.created"] == "timeline"
    assert frozen.event_kinds["timeline.saved"] == "timeline"
    assert frozen.event_kinds["timeline.config_replaced"] == "timeline"
    assert frozen.command_kinds["timeline.create"] == "timeline"
    assert frozen.command_kinds["timeline.save"] == "timeline"
    assert frozen.command_kinds["timeline.replace_config"] == "timeline"
    assert frozen.event_kinds["shot.item_added"] == "shots"
    assert frozen.command_kinds["shot.add_item"] == "shots"
    assert frozen.event_kinds["reference.primary_changed"] == "references"
    assert frozen.command_kinds["reference.set_primary"] == "references"

    assert frozen.repositories["TimelineRepository"] == "timeline"
    assert frozen.cli_mounts["timelines"] == ("timeline", "timelines")
    assert frozen.cli_mounts["shots"] == ("shots", "timelines shots")
    assert frozen.cli_mounts["references"] == ("references", "media references")
    assert frozen.bridge_mounts["timelines"] == "timeline"


# ---------------------------------------------------------------------------
# Duplicate and undeclared vocabulary rejection
# ---------------------------------------------------------------------------


def test_duplicate_pack_registration_is_rejected() -> None:
    registry = SchemaPackRegistry()
    register_standard_schema_packs(registry)
    with pytest.raises(SchemaPackDuplicateError):
        register_standard_schema_packs(registry)


def test_duplicate_core_registration_is_rejected() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    with pytest.raises(SchemaPackDuplicateError):
        register_core_vocabulary(registry)


def test_duplicate_stream_type_across_core_and_pack_is_rejected() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    conflicting = _empty_manifest(id_="intruder")
    conflicting["stream_types"] = ["core.project"]
    with pytest.raises(SchemaPackDuplicateError, match="stream type 'core.project'"):
        registry.register_pack(parse_schema_pack_manifest(conflicting))


def test_duplicate_event_kind_within_registry_is_rejected() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    conflicting = _empty_manifest(id_="intruder")
    conflicting["event_kinds"] = ["core.project.created"]
    with pytest.raises(SchemaPackDuplicateError, match="event kind 'core.project.created'"):
        registry.register_pack(parse_schema_pack_manifest(conflicting))


def test_duplicate_command_kind_within_registry_is_rejected() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    conflicting = _empty_manifest(id_="intruder")
    conflicting["command_kinds"] = ["core.project.create"]
    with pytest.raises(SchemaPackDuplicateError, match="command kind 'core.project.create'"):
        registry.register_pack(parse_schema_pack_manifest(conflicting))


def test_duplicate_declaration_reports_all_collisions_atomically() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    conflicting = _empty_manifest(id_="intruder")
    conflicting["stream_types"] = ["core.project"]
    conflicting["event_kinds"] = ["core.project.created"]
    conflicting["command_kinds"] = ["core.project.create"]
    with pytest.raises(SchemaPackDuplicateError) as excinfo:
        registry.register_pack(parse_schema_pack_manifest(conflicting))
    message = str(excinfo.value)
    assert "stream type 'core.project'" in message
    assert "event kind 'core.project.created'" in message
    assert "command kind 'core.project.create'" in message
    # No partial state was recorded: the intruder pack is absent afterwards.
    assert "intruder" not in registry.freeze().packs


def test_frozen_registry_rejects_late_registration() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    registry.freeze()
    with pytest.raises(SchemaPackRegistryFrozenError):
        register_core_vocabulary(registry)


# ---------------------------------------------------------------------------
# Malformed manifests and dependency grammar
# ---------------------------------------------------------------------------


def test_malformed_manifest_missing_top_level_field_is_rejected() -> None:
    mapping = _empty_manifest()
    del mapping["command_kinds"]
    with pytest.raises(SchemaPackManifestValidationError, match="command_kinds"):
        parse_schema_pack_manifest(mapping)


def test_malformed_manifest_extra_top_level_field_is_rejected() -> None:
    mapping = _empty_manifest()
    mapping["surprise"] = True
    with pytest.raises(SchemaPackManifestValidationError, match="surprise"):
        parse_schema_pack_manifest(mapping)


def test_unnamespaced_vocabulary_is_rejected() -> None:
    mapping = _empty_manifest()
    mapping["event_kinds"] = ["saved"]
    with pytest.raises(SchemaPackManifestValidationError, match="namespaced dotted name"):
        parse_schema_pack_manifest(mapping)


def test_dependency_grammar_error_is_rejected() -> None:
    mapping = _empty_manifest()
    mapping["depends_on"] = ["core=1"]
    with pytest.raises(SchemaPackManifestValidationError, match="<pack> >= <positive integer>"):
        parse_schema_pack_manifest(mapping)


# ---------------------------------------------------------------------------
# Plan step 8: runtime vocabulary enforcement against the frozen registry
# ---------------------------------------------------------------------------

TS = "2026-08-15T00:00:00.000000+00:00"


def _insert_project(executor, project_id: str) -> None:
    """Insert a minimal valid projects row through any typed executor."""
    executor.execute(
        "INSERT INTO projects (id, slug, name, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (project_id, project_id, project_id, TS, TS),
    )


def _insert_stream(
    executor,
    stream_id: str,
    project_id: str,
    stream_type: str = "core.project",
    aggregate_id: str | None = None,
) -> None:
    """Insert a minimal valid event_streams row through any typed executor."""
    executor.execute(
        "INSERT INTO event_streams "
        "(id, project_id, stream_type, aggregate_id, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (stream_id, project_id, stream_type, aggregate_id or project_id, TS),
    )


def _build_standard_frozen():
    """Compose core + the three in-tree packs and freeze (as conftest does)."""
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    return registry.freeze()


@pytest.fixture
def standard_writer(tmp_path):
    """A fresh writer over a standard-Astrid database at ``<tmp>/std.sqlite3``."""
    db_path = tmp_path / "std.sqlite3"
    w = DatabaseWriter(db_path, _build_standard_frozen())
    try:
        yield w
    finally:
        w.close()


# -- declaration checks -----------------------------------------------------


def test_step8_every_declared_stream_type_has_an_aggregate_rule() -> None:
    frozen = _build_standard_frozen()
    assert set(frozen.stream_types) == set(STREAM_AGGREGATE_RULES)
    for stream_type in frozen.stream_types:
        rule = aggregate_rule_for(frozen, stream_type)
        assert rule.declaring_pack == frozen.stream_types[stream_type]


def test_step8_declared_core_vocabulary_validates() -> None:
    frozen = core_only_registry()
    for stream_type in CORE_STREAM_TYPES:
        assert validate_stream_type(frozen, stream_type) == stream_type
    for kind in CORE_EVENT_KINDS:
        assert validate_event_kind(frozen, kind) == kind
    for kind in CORE_COMMAND_KINDS:
        assert validate_command_kind(frozen, kind) == kind


def test_step8_declared_timeline_vocabulary_validates() -> None:
    frozen = _build_standard_frozen()
    assert validate_stream_type(frozen, "timeline.timeline") == "timeline.timeline"
    assert validate_event_kind(frozen, "timeline.created") == "timeline.created"
    assert validate_event_kind(frozen, "timeline.saved") == "timeline.saved"
    assert validate_event_kind(frozen, "timeline.config_replaced") == "timeline.config_replaced"
    assert validate_command_kind(frozen, "timeline.create") == "timeline.create"
    assert validate_command_kind(frozen, "timeline.save") == "timeline.save"
    assert validate_command_kind(frozen, "timeline.replace_config") == "timeline.replace_config"


def test_step8_undeclared_stream_type_is_rejected() -> None:
    frozen = _build_standard_frozen()
    with pytest.raises(StreamVocabularyError, match="core.mystery"):
        validate_stream_type(frozen, "core.mystery")
    with pytest.raises(StreamVocabularyError, match="timeline.nonexistent"):
        validate_stream_type(frozen, "timeline.nonexistent")


def test_step8_unnamespaced_stream_type_is_rejected() -> None:
    frozen = _build_standard_frozen()
    with pytest.raises(StreamVocabularyError, match="namespaced"):
        validate_stream_type(frozen, "project")


def test_step8_undeclared_event_kind_is_rejected() -> None:
    frozen = _build_standard_frozen()
    with pytest.raises(EventVocabularyError, match="core.project.deleted"):
        validate_event_kind(frozen, "core.project.deleted")
    with pytest.raises(EventVocabularyError, match="namespaced"):
        validate_event_kind(frozen, "deleted")


def test_step8_undeclared_command_kind_is_rejected() -> None:
    frozen = _build_standard_frozen()
    with pytest.raises(CommandVocabularyError, match="core.project.destroy"):
        validate_command_kind(frozen, "core.project.destroy")
    with pytest.raises(CommandVocabularyError, match="namespaced"):
        validate_command_kind(frozen, "destroy")


# -- aggregate/type/project agreement ---------------------------------------


def test_step8_core_project_stream_requires_aggregate_equal_project() -> None:
    frozen = _build_standard_frozen()
    rule = validate_stream_creation(
        frozen, project_id="proj-1", stream_type="core.project", aggregate_id="proj-1"
    )
    assert rule.subject_type == "project"
    assert rule.aggregate_is_project is True
    with pytest.raises(StreamAgreementError, match="aggregate id"):
        validate_stream_creation(
            frozen,
            project_id="proj-1",
            stream_type="core.project",
            aggregate_id="other-aggregate",
        )


def test_step8_timeline_stream_creation_accepts_timeline_aggregate() -> None:
    frozen = _build_standard_frozen()
    rule = validate_stream_creation(
        frozen,
        project_id="proj-1",
        stream_type="timeline.timeline",
        aggregate_id="timeline-abc",
    )
    assert rule.subject_type == "timeline"
    assert rule.aggregate_is_project is False


def test_step8_declared_core_path_validates_end_to_end() -> None:
    frozen = _build_standard_frozen()
    validate_stream_creation(
        frozen, project_id="proj-1", stream_type="core.project", aggregate_id="proj-1"
    )
    validate_event_append(
        frozen,
        project_id="proj-1",
        stream_project_id="proj-1",
        stream_type="core.project",
        aggregate_id="proj-1",
        subject_type="project",
        subject_id="proj-1",
        event_kind="core.project.created",
        command_kind="core.project.create",
    )


def test_step8_declared_timeline_path_validates_end_to_end() -> None:
    frozen = _build_standard_frozen()
    validate_stream_creation(
        frozen,
        project_id="proj-1",
        stream_type="timeline.timeline",
        aggregate_id="timeline-abc",
    )
    validate_event_append(
        frozen,
        project_id="proj-1",
        stream_project_id="proj-1",
        stream_type="timeline.timeline",
        aggregate_id="timeline-abc",
        subject_type="timeline",
        subject_id="timeline-abc",
        event_kind="timeline.created",
        command_kind="timeline.create",
    )


def test_step8_cross_pack_event_on_core_stream_is_rejected() -> None:
    frozen = _build_standard_frozen()
    with pytest.raises(StreamAgreementError, match="declared by pack"):
        validate_event_append(
            frozen,
            project_id="proj-1",
            stream_project_id="proj-1",
            stream_type="core.project",
            aggregate_id="proj-1",
            subject_type="project",
            subject_id="proj-1",
            event_kind="timeline.created",
        )


def test_step8_cross_pack_command_on_timeline_stream_is_rejected() -> None:
    frozen = _build_standard_frozen()
    with pytest.raises(StreamAgreementError, match="declared by pack"):
        validate_event_append(
            frozen,
            project_id="proj-1",
            stream_project_id="proj-1",
            stream_type="timeline.timeline",
            aggregate_id="timeline-abc",
            subject_type="timeline",
            subject_id="timeline-abc",
            event_kind="timeline.created",
            command_kind="core.project.create",
        )


def test_step8_event_subject_must_match_stream_aggregate() -> None:
    frozen = _build_standard_frozen()
    with pytest.raises(StreamAgreementError, match="subject_type"):
        validate_event_append(
            frozen,
            project_id="proj-1",
            stream_project_id="proj-1",
            stream_type="core.project",
            aggregate_id="proj-1",
            subject_type="task",
            subject_id="proj-1",
            event_kind="core.project.created",
        )
    with pytest.raises(StreamAgreementError, match="subject id"):
        validate_event_append(
            frozen,
            project_id="proj-1",
            stream_project_id="proj-1",
            stream_type="core.project",
            aggregate_id="proj-1",
            subject_type="project",
            subject_id="other-subject",
            event_kind="core.project.created",
        )


def test_step8_event_project_must_match_stream_project() -> None:
    frozen = _build_standard_frozen()
    with pytest.raises(StreamAgreementError, match="disagrees with the stream project"):
        validate_event_append(
            frozen,
            project_id="proj-2",
            stream_project_id="proj-1",
            stream_type="core.project",
            aggregate_id="proj-1",
            subject_type="project",
            subject_id="proj-1",
            event_kind="core.project.created",
        )


# -- zero-row-change proofs against a real database --------------------------


def test_step8_undeclared_stream_creation_changes_zero_rows(
    standard_writer: DatabaseWriter,
) -> None:
    standard_writer.submit(lambda session: _insert_project(session, "proj-a"))
    observed: list[tuple[str, str]] = []
    uow = UnitOfWork(
        standard_writer,
        on_statement=lambda kind, sql, params: observed.append((kind, sql)),
    )
    frozen = _build_standard_frozen()
    with pytest.raises(StreamVocabularyError):
        uow.run(
            lambda u: (
                validate_stream_creation(
                    frozen,
                    project_id="proj-a",
                    stream_type="core.nonexistent",
                    aggregate_id="proj-a",
                ),
                # Never reached: validation fails before any SQL mutation.
                u.execute(
                    "INSERT INTO event_streams "
                    "(id, project_id, stream_type, aggregate_id, created_at) "
                    "VALUES ('s', 'proj-a', 'core.nonexistent', 'proj-a', ?)",
                    (TS,),
                ),
            )
        )
    # The observer saw no statement at all: only the transaction envelope ran.
    assert [kind for kind, _ in observed] == ["begin_immediate", "rollback"]
    counts = standard_writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM event_streams")[0],
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one(
                "SELECT event_head_seq FROM projects WHERE id = 'proj-a'"
            )[0],
        )
    )
    assert counts == (0, 0, 0)


def test_step8_rejected_event_append_changes_zero_rows(
    standard_writer: DatabaseWriter,
) -> None:
    standard_writer.submit(
        lambda session: (
            _insert_project(session, "proj-b"),
            _insert_stream(
                session, "stream-b", "proj-b", "core.project", "proj-b"
            ),
        )
    )
    observed: list[tuple[str, str]] = []
    uow = UnitOfWork(
        standard_writer,
        on_statement=lambda kind, sql, params: observed.append((kind, sql)),
    )
    frozen = _build_standard_frozen()
    with pytest.raises(StreamAgreementError, match="declared by pack"):
        uow.run(
            lambda u: (
                validate_event_append(
                    frozen,
                    project_id="proj-b",
                    stream_project_id="proj-b",
                    stream_type="core.project",
                    aggregate_id="proj-b",
                    subject_type="project",
                    subject_id="proj-b",
                    event_kind="timeline.created",
                ),
                # Never reached: the cross-pack append fails validation first.
                u.append_event(
                    stream_id="stream-b",
                    project_id="proj-b",
                    event_id="ev-b",
                    subject_type="project",
                    subject_id="proj-b",
                    changes_json="[]",
                    kind="timeline.created",
                    schema_version=1,
                    idempotency_key="k-b",
                    txn_id="txn-b",
                    actor_kind="local",
                    payload_json='{"data": {}}',
                    created_at=TS,
                ),
            )
        )
    assert [kind for kind, _ in observed] == ["begin_immediate", "rollback"]
    counts = standard_writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
            session.query_one(
                "SELECT event_head_seq FROM projects WHERE id = 'proj-b'"
            )[0],
            session.query_one(
                "SELECT head_seq FROM event_streams WHERE id = 'stream-b'"
            )[0],
        )
    )
    assert counts == (0, 0, 0, 0)


def test_step8_declared_core_path_commits_inside_uow(
    standard_writer: DatabaseWriter,
) -> None:
    """The declared path passes the guards and commits atomically."""
    standard_writer.submit(
        lambda session: (
            _insert_project(session, "proj-c"),
            _insert_stream(
                session, "stream-c", "proj-c", "core.project", "proj-c"
            ),
        )
    )
    uow = UnitOfWork(standard_writer)
    frozen = _build_standard_frozen()
    result = uow.run(
        lambda u: (
            validate_stream_creation(
                frozen,
                project_id="proj-c",
                stream_type="core.project",
                aggregate_id="proj-c",
            ),
            validate_event_append(
                frozen,
                project_id="proj-c",
                stream_project_id="proj-c",
                stream_type="core.project",
                aggregate_id="proj-c",
                subject_type="project",
                subject_id="proj-c",
                event_kind="core.project.created",
                command_kind="core.project.create",
            ),
            u.append_event(
                stream_id="stream-c",
                project_id="proj-c",
                event_id="ev-c",
                subject_type="project",
                subject_id="proj-c",
                changes_json="[]",
                kind="core.project.created",
                schema_version=1,
                idempotency_key="k-c",
                txn_id="txn-c",
                actor_kind="local",
                payload_json='{"data": {}}',
                created_at=TS,
            ),
        )
    )
    assert result[-1] == (1, 1)  # (project_seq, stream_seq)
    row = standard_writer.submit(
        lambda session: session.query_one(
            "SELECT kind, subject_type, subject_id FROM events "
            "WHERE stream_id = 'stream-c'"
        )
    )
    assert tuple(row) == ("core.project.created", "project", "proj-c")


# ---------------------------------------------------------------------------
# m2 plan step 1: task, run, and media vocabulary plus the core manifest
# repository/conformance surface
# ---------------------------------------------------------------------------

M2_TASK_EVENT_KINDS = (
    "core.task.created",
    "core.task.claimed",
    "core.task.started",
    "core.task.expired",
    "core.task.cancelled",
    "core.task.failed",
    "core.task.retried",
    "core.task.completed",
)
M2_TASK_COMMAND_KINDS = (
    "core.task.create",
    "core.task.claim",
    "core.task.start",
    "core.task.expire",
    "core.task.cancel",
    "core.task.fail",
    "core.task.retry",
    "core.task.complete",
)
M2_RUN_EVENT_KINDS = (
    "core.run.created",
    "core.run.cancelled",
    "core.run.retried",
    "core.run.closed",
)
M2_RUN_COMMAND_KINDS = (
    "core.run.create",
    "core.run.cancel",
    "core.run.retry",
    "core.run.close",
)
M2_MEDIA_EVENT_KINDS = (
    "core.media.imported",
    "core.media.location_replaced",
    "core.media.related",
)
M2_MEDIA_COMMAND_KINDS = (
    "core.media.import",
    "core.media.replace_location",
    "core.media.relate",
)


def test_m2_core_media_stream_type_is_registered() -> None:
    frozen = core_only_registry()
    assert "core.media" in CORE_STREAM_TYPES
    assert frozen.stream_types["core.media"] == CORE_PACK_ID
    assert validate_stream_type(frozen, "core.media") == "core.media"


def test_m2_core_media_aggregate_rule_uses_media_subject() -> None:
    frozen = core_only_registry()
    rule = aggregate_rule_for(frozen, "core.media")
    assert rule.subject_type == "media"
    assert rule.aggregate_is_project is False
    assert rule.declaring_pack == CORE_PACK_ID


def test_m2_media_stream_creation_accepts_media_aggregate() -> None:
    frozen = _build_standard_frozen()
    rule = validate_stream_creation(
        frozen,
        project_id="proj-1",
        stream_type="core.media",
        aggregate_id="media-abc",
    )
    assert rule.subject_type == "media"
    assert rule.aggregate_is_project is False
    # Unlike core.project, a media stream is not project-aggregate, so the
    # media aggregate id is free to differ from the project id (the media id).
    rule_any_aggregate = validate_stream_creation(
        frozen,
        project_id="proj-1",
        stream_type="core.media",
        aggregate_id="proj-1",
    )
    assert rule_any_aggregate.subject_type == "media"


def test_m2_media_event_on_media_stream_validates_end_to_end() -> None:
    frozen = _build_standard_frozen()
    validate_stream_creation(
        frozen, project_id="proj-1", stream_type="core.media", aggregate_id="media-abc"
    )
    validate_event_append(
        frozen,
        project_id="proj-1",
        stream_project_id="proj-1",
        stream_type="core.media",
        aggregate_id="media-abc",
        subject_type="media",
        subject_id="media-abc",
        event_kind="core.media.imported",
        command_kind="core.media.import",
    )


def test_m2_task_and_run_event_kinds_are_declared() -> None:
    frozen = core_only_registry()
    for kind in M2_TASK_EVENT_KINDS + M2_RUN_EVENT_KINDS:
        assert kind in CORE_EVENT_KINDS
        assert frozen.event_kinds[kind] == CORE_PACK_ID
        assert validate_event_kind(frozen, kind) == kind


def test_m2_task_and_run_command_kinds_are_declared() -> None:
    frozen = core_only_registry()
    for kind in M2_TASK_COMMAND_KINDS + M2_RUN_COMMAND_KINDS:
        assert kind in CORE_COMMAND_KINDS
        assert frozen.command_kinds[kind] == CORE_PACK_ID
        assert validate_command_kind(frozen, kind) == kind


def test_m2_media_event_and_command_kinds_are_declared() -> None:
    frozen = core_only_registry()
    for kind in M2_MEDIA_EVENT_KINDS:
        assert kind in CORE_EVENT_KINDS
        assert frozen.event_kinds[kind] == CORE_PACK_ID
        assert validate_event_kind(frozen, kind) == kind
    for kind in M2_MEDIA_COMMAND_KINDS:
        assert kind in CORE_COMMAND_KINDS
        assert frozen.command_kinds[kind] == CORE_PACK_ID
        assert validate_command_kind(frozen, kind) == kind


def test_m2_vocabulary_is_unique_and_namespaced() -> None:
    # No duplicate names within or across the kind families.
    assert len(CORE_EVENT_KINDS) == len(set(CORE_EVENT_KINDS))
    assert len(CORE_COMMAND_KINDS) == len(set(CORE_COMMAND_KINDS))
    assert set(CORE_EVENT_KINDS).isdisjoint(CORE_COMMAND_KINDS)
    for kind in CORE_EVENT_KINDS + CORE_COMMAND_KINDS:
        assert kind.count(".") >= 1, kind
        assert kind.split(".", 1)[0] == "core", kind


def test_m2_heartbeat_has_no_command_or_event_kind() -> None:
    # Heartbeat is the narrow non-event attempt-liveness exception (v10
    # section 5.1): it must never appear in the core vocabulary.
    assert not any("heartbeat" in kind for kind in CORE_EVENT_KINDS)
    assert not any("heartbeat" in kind for kind in CORE_COMMAND_KINDS)


def test_m2_core_manifest_declares_the_kernel_repositories() -> None:
    manifest = core_schema_pack_manifest()
    assert manifest.repositories == CORE_REPOSITORIES
    assert "ProjectRepository" in manifest.repositories
    assert "TaskRepository" in manifest.repositories
    assert "MediaRepository" in manifest.repositories
    assert "RunRepository" in manifest.repositories
    frozen = core_only_registry()
    for name in CORE_REPOSITORIES:
        assert frozen.repositories[name] == CORE_PACK_ID, name


def test_m2_core_manifest_declares_seven_conformance_dimensions() -> None:
    manifest = core_schema_pack_manifest()
    assert manifest.conformance == CORE_CONFORMANCE_DIMENSIONS
    assert len(CORE_CONFORMANCE_DIMENSIONS) == 7
    assert set(CORE_CONFORMANCE_DIMENSIONS) == {
        "replay",
        "mismatch_before_mutation",
        "same_project",
        "vocabulary",
        "writer_ownership",
        "crash_atomicity",
        "hash_chain",
    }


def test_m2_core_manifest_declares_only_required_stream_types() -> None:
    manifest = core_schema_pack_manifest()
    assert set(manifest.stream_types) == {
        "core.project",
        "core.task",
        "core.run",
        "core.media",
    }
    assert set(manifest.stream_types) == set(CORE_STREAM_TYPES)


# ---------------------------------------------------------------------------
# m3 plan step 1: run continuation, evidence vocabulary, and the references
# and shots aggregate streams with their pack-owned repositories
# ---------------------------------------------------------------------------

M3_CORE_EVENT_KINDS = (
    "core.run.continued",
    "core.evidence.recorded",
)
M3_CORE_COMMAND_KINDS = ("core.run.continue",)

M3_REFERENCE_STREAM_TYPE = "reference.reference"
M3_REFERENCE_EVENT_KINDS = (
    "reference.created",
    "reference.archived",
    "reference.media_associated",
    "reference.primary_changed",
    "reference.linked",
)
M3_REFERENCE_COMMAND_KINDS = (
    "reference.create",
    "reference.archive",
    "reference.associate",
    "reference.set_primary",
    "reference.link",
)

M3_SHOT_STREAM_TYPE = "shot.shot"
M3_SHOT_EVENT_KINDS = (
    "shot.created",
    "shot.item_added",
    "shot.item_removed",
    "shot.reordered",
)
M3_SHOT_COMMAND_KINDS = (
    "shot.create",
    "shot.add_item",
    "shot.remove_item",
    "shot.reorder",
)


def test_m3_core_run_continuation_and_evidence_vocabulary_is_declared() -> None:
    frozen = core_only_registry()
    for kind in M3_CORE_EVENT_KINDS:
        assert kind in CORE_EVENT_KINDS
        assert frozen.event_kinds[kind] == CORE_PACK_ID
        assert validate_event_kind(frozen, kind) == kind
    for kind in M3_CORE_COMMAND_KINDS:
        assert kind in CORE_COMMAND_KINDS
        assert frozen.command_kinds[kind] == CORE_PACK_ID
        assert validate_command_kind(frozen, kind) == kind


def test_m3_references_manifest_declares_aggregate_stream_and_repository() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    frozen = registry.freeze()

    assert frozen.stream_types[M3_REFERENCE_STREAM_TYPE] == "references"
    assert validate_stream_type(frozen, M3_REFERENCE_STREAM_TYPE) == M3_REFERENCE_STREAM_TYPE
    assert frozen.repositories["ReferenceRepository"] == "references"


def test_m3_references_manifest_declares_lifecycle_media_and_link_vocabulary() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    frozen = registry.freeze()

    for kind in M3_REFERENCE_EVENT_KINDS:
        assert kind in frozen.event_kinds, kind
        assert frozen.event_kinds[kind] == "references", kind
        assert validate_event_kind(frozen, kind) == kind
    for kind in M3_REFERENCE_COMMAND_KINDS:
        assert kind in frozen.command_kinds, kind
        assert frozen.command_kinds[kind] == "references", kind
        assert validate_command_kind(frozen, kind) == kind
    # The frozen v10 example vocabulary stays declared (normative names).
    assert "reference.primary_changed" in M3_REFERENCE_EVENT_KINDS
    assert "reference.set_primary" in M3_REFERENCE_COMMAND_KINDS


def test_m3_shots_manifest_declares_aggregate_stream_and_repository() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    frozen = registry.freeze()

    assert frozen.stream_types[M3_SHOT_STREAM_TYPE] == "shots"
    assert validate_stream_type(frozen, M3_SHOT_STREAM_TYPE) == M3_SHOT_STREAM_TYPE
    assert frozen.repositories["ShotRepository"] == "shots"


def test_m3_shots_manifest_declares_item_mutation_vocabulary() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    frozen = registry.freeze()

    for kind in M3_SHOT_EVENT_KINDS:
        assert kind in frozen.event_kinds, kind
        assert frozen.event_kinds[kind] == "shots", kind
        assert validate_event_kind(frozen, kind) == kind
    for kind in M3_SHOT_COMMAND_KINDS:
        assert kind in frozen.command_kinds, kind
        assert frozen.command_kinds[kind] == "shots", kind
        assert validate_command_kind(frozen, kind) == kind
    # The frozen v10 example vocabulary stays declared (normative names).
    assert "shot.item_added" in M3_SHOT_EVENT_KINDS
    assert "shot.add_item" in M3_SHOT_COMMAND_KINDS


def test_m3_reference_and_shot_streams_have_aggregate_rules() -> None:
    frozen = _build_standard_frozen()
    reference_rule = aggregate_rule_for(frozen, M3_REFERENCE_STREAM_TYPE)
    assert reference_rule.declaring_pack == "references"
    assert reference_rule.subject_type == "reference"
    assert reference_rule.aggregate_is_project is False
    shot_rule = aggregate_rule_for(frozen, M3_SHOT_STREAM_TYPE)
    assert shot_rule.declaring_pack == "shots"
    assert shot_rule.subject_type == "shot"
    assert shot_rule.aggregate_is_project is False


def test_m3_every_declared_stream_type_still_has_an_aggregate_rule() -> None:
    frozen = _build_standard_frozen()
    assert set(frozen.stream_types) == set(STREAM_AGGREGATE_RULES)
    for stream_type in frozen.stream_types:
        rule = aggregate_rule_for(frozen, stream_type)
        assert rule.declaring_pack == frozen.stream_types[stream_type]


def test_m3_reference_stream_creation_and_event_append_validate_end_to_end() -> None:
    frozen = _build_standard_frozen()
    validate_stream_creation(
        frozen,
        project_id="proj-1",
        stream_type=M3_REFERENCE_STREAM_TYPE,
        aggregate_id="reference-abc",
    )
    validate_event_append(
        frozen,
        project_id="proj-1",
        stream_project_id="proj-1",
        stream_type=M3_REFERENCE_STREAM_TYPE,
        aggregate_id="reference-abc",
        subject_type="reference",
        subject_id="reference-abc",
        event_kind="reference.created",
        command_kind="reference.create",
    )
    # A core event can never land on a pack stream (and vice versa).
    with pytest.raises(StreamAgreementError, match="declared by pack"):
        validate_event_append(
            frozen,
            project_id="proj-1",
            stream_project_id="proj-1",
            stream_type=M3_REFERENCE_STREAM_TYPE,
            aggregate_id="reference-abc",
            subject_type="reference",
            subject_id="reference-abc",
            event_kind="core.project.created",
        )


def test_m3_shot_stream_creation_and_event_append_validate_end_to_end() -> None:
    frozen = _build_standard_frozen()
    validate_stream_creation(
        frozen,
        project_id="proj-1",
        stream_type=M3_SHOT_STREAM_TYPE,
        aggregate_id="shot-abc",
    )
    validate_event_append(
        frozen,
        project_id="proj-1",
        stream_project_id="proj-1",
        stream_type=M3_SHOT_STREAM_TYPE,
        aggregate_id="shot-abc",
        subject_type="shot",
        subject_id="shot-abc",
        event_kind="shot.created",
        command_kind="shot.create",
    )
    # The pack stream requires the pack subject type, never a core subject.
    with pytest.raises(StreamAgreementError, match="subject_type"):
        validate_event_append(
            frozen,
            project_id="proj-1",
            stream_project_id="proj-1",
            stream_type=M3_SHOT_STREAM_TYPE,
            aggregate_id="shot-abc",
            subject_type="task",
            subject_id="shot-abc",
            event_kind="shot.created",
        )


def test_m3_colliding_pack_stream_type_is_rejected() -> None:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    conflicting = _empty_manifest(id_="intruder")
    conflicting["stream_types"] = [M3_REFERENCE_STREAM_TYPE]
    with pytest.raises(SchemaPackDuplicateError, match=M3_REFERENCE_STREAM_TYPE):
        registry.register_pack(parse_schema_pack_manifest(conflicting))
    # No partial state: the intruder pack is absent afterwards.
    assert "intruder" not in registry.freeze().packs


def test_m3_pack_vocabulary_is_namespaced_and_owned() -> None:
    frozen = _build_standard_frozen()
    for kind in M3_REFERENCE_EVENT_KINDS + M3_SHOT_EVENT_KINDS:
        assert kind.count(".") >= 1, kind
        assert frozen.event_kinds[kind] in ("references", "shots"), kind
    for kind in M3_REFERENCE_COMMAND_KINDS + M3_SHOT_COMMAND_KINDS:
        assert kind.count(".") >= 1, kind
        assert frozen.command_kinds[kind] in ("references", "shots"), kind
    # No duplicate names within or across the kind families.
    all_kinds = (
        M3_REFERENCE_EVENT_KINDS
        + M3_REFERENCE_COMMAND_KINDS
        + M3_SHOT_EVENT_KINDS
        + M3_SHOT_COMMAND_KINDS
    )
    assert len(all_kinds) == len(set(all_kinds))
    assert set(all_kinds).isdisjoint(CORE_EVENT_KINDS)
    assert set(all_kinds).isdisjoint(CORE_COMMAND_KINDS)


def test_standard_catalog_is_frozen_at_22_tables() -> None:
    """Manifest ownership, not DDL: pack vocabulary adds no tables."""
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    frozen = registry.freeze()
    assert len(frozen.tables) == CORE_TABLE_COUNT + 1 + 4 + 3 == 22
    assert frozen.tables["project_references"] == "references"
    assert frozen.tables["media_references"] == "references"
    assert frozen.tables["reference_links"] == "references"
    assert frozen.tables["shots"] == "shots"
    assert frozen.tables["shot_items"] == "shots"
    assert frozen.tables["timelines"] == "timeline"
    for table in CORE_TABLES:
        assert frozen.tables[table] == CORE_PACK_ID
