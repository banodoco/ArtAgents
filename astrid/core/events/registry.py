"""Core stream, event, and command vocabulary with independent registration.

(m1 plan step 2; m2 plan step 1.) The kernel registers its own vocabulary
independently of any Astrid pack: core declares the ``core.project``,
``core.task``, ``core.run``, and ``core.media`` stream types plus the m1/m2
core event/command kinds, and only then may the explicit standard-Astrid
composition in ``astrid/packs/__init__.py`` register the in-tree schema
packs (v10 section 2.3 law 5; decision artifact section 4).

Rules kept here:

- Vocabulary names are namespaced dotted names; the composed registry rejects
  missing, duplicate, or non-namespaced declarations before any database opens.
- The kernel has no ``schema-pack.yaml`` file: its manifest and vocabulary are
  code-declared by ``astrid.core.schema_packs.core``. That lower-level module
  owns the explicit migration descriptor; this validator only consumes the
  resulting frozen registry and event-specific aggregate rules.
- This module never opens a database and never imports the capability-pack
  loader, discovery, or definition machinery (v10 section 2 "Boundary now,
  loader later").
- Heartbeat deliberately gets no command or event kind: it is the narrow
  non-event attempt-liveness exception (v10 section 5.1), so no heartbeat name
  may ever appear in the core vocabulary.

``core.task``, ``core.run``, and ``core.media`` stream types are registered now
because v10 section 2.3 requires core to register its stream types; m1
implements the project vertical only, so m1 core event/command kinds are the
project ones. m2 (plan step 1) registers the exact task lifecycle (admission,
claim, start, expiry, cancellation, failure, retry, completion), run fan-out
and group, and media (import, location replacement, relations) command/event
kinds the m2 repositories consume. m3 (plan step 1) adds the receipt-linked
run continuation vocabulary (``core.run.continue``/``core.run.continued``),
the kernel evidence event (``core.evidence.recorded``) and its receipt
command kind (``core.evidence.record``), and registers
aggregate agreement rules for the references and shots packs' own
stream types (``reference.reference`` and ``shot.shot``) so pack-owned
repositories can create and write
their aggregate streams without kernel DDL changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from astrid.core.contracts.vocabulary import (
    CommandVocabularyError,
    EventVocabularyError,
    StreamAgreementError,
    StreamVocabularyError,
)
from astrid.core.schema_packs.core import (
    CORE_COMMAND_KINDS,
    CORE_CONFORMANCE_DIMENSIONS,
    CORE_EVENT_KINDS,
    CORE_MANIFEST_VERSION,
    CORE_PACK_ID,
    CORE_REPOSITORIES,
    CORE_STREAM_TYPES,
    core_only_registry,
    core_schema_pack_manifest,
    register_core_vocabulary,
)
from astrid.core.schema_packs.registry import (
    FrozenSchemaPackRegistry,
)

# ---------------------------------------------------------------------------
# Runtime vocabulary enforcement (m1 plan step 8)
# ---------------------------------------------------------------------------
#
# These guards run before any SQL mutation. The frozen registry is the single
# source of which stream types, event kinds, and command kinds exist; the
# aggregate/type/project agreement rules below are the single, centrally
# defined statement of what each *declared* stream type means. Repository
# handlers never carry their own allowlists, so a handler can neither admit
# an undeclared name nor redefine the meaning of a declared stream type.

_NAMESPACED_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
"""Namespaced (dotted) vocabulary name, matching the manifest grammar."""


@dataclass(frozen=True, slots=True)
class StreamAggregateRule:
    """Aggregate/type/project agreement for one declared stream type.

    - ``subject_type`` is the ``events.subject_type`` every event on the
      stream must carry; ``subject_id`` must equal the stream's aggregate id.
    - ``aggregate_is_project`` marks streams whose aggregate is the project
      itself (``core.project``): for these, the aggregate id must equal the
      project id, so one project owns exactly one such stream.
    """

    stream_type: str
    declaring_pack: str
    subject_type: str
    aggregate_is_project: bool = False


STREAM_AGGREGATE_RULES: Mapping[str, StreamAggregateRule] = MappingProxyType(
    {
        "core.project": StreamAggregateRule(
            stream_type="core.project",
            declaring_pack=CORE_PACK_ID,
            subject_type="project",
            aggregate_is_project=True,
        ),
        "core.task": StreamAggregateRule(
            stream_type="core.task",
            declaring_pack=CORE_PACK_ID,
            subject_type="task",
        ),
        "core.run": StreamAggregateRule(
            stream_type="core.run",
            declaring_pack=CORE_PACK_ID,
            subject_type="run",
        ),
        "core.media": StreamAggregateRule(
            stream_type="core.media",
            declaring_pack=CORE_PACK_ID,
            subject_type="media",
        ),
        "timeline.timeline": StreamAggregateRule(
            stream_type="timeline.timeline",
            declaring_pack="timeline",
            subject_type="timeline",
        ),
        "reference.reference": StreamAggregateRule(
            stream_type="reference.reference",
            declaring_pack="references",
            subject_type="reference",
        ),
        "shot.shot": StreamAggregateRule(
            stream_type="shot.shot",
            declaring_pack="shots",
            subject_type="shot",
        ),
    }
)
"""Aggregate agreement rules for every stream type the composed registry
can declare today (core project/task/run/media, the timeline pack, and the
m3 references/shots packs). The rule table lives here —
the vocabulary module — not in repository handlers."""


def _require_namespaced(
    value: object,
    *,
    label: str,
    error: type[StreamVocabularyError]
    | type[EventVocabularyError]
    | type[CommandVocabularyError],
    identity: str,
) -> str:
    if not isinstance(value, str) or not _NAMESPACED_NAME_RE.fullmatch(value):
        raise error(
            **{identity: value},
            reason=(
                f"{label} must be a namespaced dotted name like "
                f"'core.project', got {value!r}"
            ),
        )
    return value


def validate_stream_type(
    registry: FrozenSchemaPackRegistry, stream_type: str
) -> str:
    """Reject a stream type that is not declared or not namespaced.

    Raises :class:`StreamVocabularyError` before any SQL mutation; returns
    the canonical stream type unchanged on success.
    """
    _require_namespaced(
        stream_type,
        label="stream type",
        error=StreamVocabularyError,
        identity="stream_type",
    )
    if stream_type not in registry.stream_types:
        raise StreamVocabularyError(
            stream_type=stream_type,
            reason="not declared by any registered pack",
        )
    return stream_type


def validate_event_kind(
    registry: FrozenSchemaPackRegistry, event_kind: str
) -> str:
    """Reject an event kind that is not declared or not namespaced."""
    _require_namespaced(
        event_kind,
        label="event kind",
        error=EventVocabularyError,
        identity="event_kind",
    )
    if event_kind not in registry.event_kinds:
        raise EventVocabularyError(
            event_kind=event_kind,
            reason="not declared by any registered pack",
        )
    return event_kind


def validate_command_kind(
    registry: FrozenSchemaPackRegistry, command_kind: str
) -> str:
    """Reject a command kind that is not declared or not namespaced."""
    _require_namespaced(
        command_kind,
        label="command kind",
        error=CommandVocabularyError,
        identity="command_kind",
    )
    if command_kind not in registry.command_kinds:
        raise CommandVocabularyError(
            command_kind=command_kind,
            reason="not declared by any registered pack",
        )
    return command_kind


def aggregate_rule_for(
    registry: FrozenSchemaPackRegistry, stream_type: str
) -> StreamAggregateRule:
    """Return the agreement rule for a declared stream type.

    Raises :class:`StreamVocabularyError` for undeclared stream types and
    :class:`StreamAgreementError` when a declared stream type has no rule —
    a declared stream with no kernel-known aggregate semantics can never be
    created or written, so vocabulary and semantics cannot drift apart.
    """
    validate_stream_type(registry, stream_type)
    rule = STREAM_AGGREGATE_RULES.get(stream_type)
    if rule is None:
        raise StreamAgreementError(
            stream_type=stream_type,
            detail=(
                f"no aggregate rule is registered for stream type "
                f"{stream_type!r}"
            ),
        )
    if rule.declaring_pack != registry.stream_types[stream_type]:
        raise StreamAgreementError(
            stream_type=stream_type,
            detail=(
                f"aggregate rule declares pack {rule.declaring_pack!r} but "
                f"the registry declares {registry.stream_types[stream_type]!r}"
            ),
        )
    return rule


def validate_stream_creation(
    registry: FrozenSchemaPackRegistry,
    *,
    project_id: str,
    stream_type: str,
    aggregate_id: str,
) -> StreamAggregateRule:
    """Validate one stream creation before any SQL mutation.

    Checks the stream type against the frozen registry and enforces
    aggregate/type/project agreement: for ``core.project`` the aggregate id
    must equal the project id. Returns the applicable
    :class:`StreamAggregateRule` so callers can reuse it for the first event
    append.
    """
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("project_id must be a non-empty string")
    if not isinstance(aggregate_id, str) or not aggregate_id:
        raise ValueError("aggregate_id must be a non-empty string")
    rule = aggregate_rule_for(registry, stream_type)
    if rule.aggregate_is_project and aggregate_id != project_id:
        raise StreamAgreementError(
            stream_type=stream_type,
            aggregate_id=aggregate_id,
            project_id=project_id,
            detail=(
                f"aggregate id {aggregate_id!r} must equal project id "
                f"{project_id!r} for {stream_type!r} streams"
            ),
        )
    return rule


def validate_event_append(
    registry: FrozenSchemaPackRegistry,
    *,
    project_id: str,
    stream_project_id: str,
    stream_type: str,
    aggregate_id: str,
    subject_type: str,
    subject_id: str,
    event_kind: str,
    command_kind: str | None = None,
) -> StreamAggregateRule:
    """Validate one event append before any SQL mutation.

    Enforces, all registry-driven and without handler-local allowlists:

    - the stream type and event kind are declared and namespaced;
    - the event kind's declaring pack equals the stream type's declaring
      pack (a ``timeline.*`` event can never land on a ``core.*`` stream);
    - the event subject is the stream's aggregate
      (``subject_type``/``subject_id`` match the agreement rule);
    - the event's project equals the stream's project;
    - for ``core.project`` streams, the aggregate id equals the project id;
    - when a ``command_kind`` is supplied, it is declared and belongs to the
      same pack as the stream type.

    Returns the applicable :class:`StreamAggregateRule`.
    """
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("project_id must be a non-empty string")
    if not isinstance(stream_project_id, str) or not stream_project_id:
        raise ValueError("stream_project_id must be a non-empty string")
    if not isinstance(aggregate_id, str) or not aggregate_id:
        raise ValueError("aggregate_id must be a non-empty string")
    if not isinstance(subject_type, str) or not subject_type:
        raise ValueError("subject_type must be a non-empty string")
    if not isinstance(subject_id, str) or not subject_id:
        raise ValueError("subject_id must be a non-empty string")
    rule = aggregate_rule_for(registry, stream_type)
    validate_event_kind(registry, event_kind)

    stream_pack = registry.stream_types[stream_type]
    event_pack = registry.event_kinds[event_kind]
    if event_pack != stream_pack:
        raise StreamAgreementError(
            stream_type=stream_type,
            aggregate_id=aggregate_id,
            project_id=project_id,
            subject_type=subject_type,
            subject_id=subject_id,
            detail=(
                f"event kind {event_kind!r} is declared by pack "
                f"{event_pack!r} but stream type {stream_type!r} is "
                f"declared by pack {stream_pack!r}"
            ),
        )

    if subject_type != rule.subject_type:
        raise StreamAgreementError(
            stream_type=stream_type,
            aggregate_id=aggregate_id,
            project_id=project_id,
            subject_type=subject_type,
            subject_id=subject_id,
            detail=(
                f"events on {stream_type!r} streams must have subject_type "
                f"{rule.subject_type!r}, got {subject_type!r}"
            ),
        )
    if subject_id != aggregate_id:
        raise StreamAgreementError(
            stream_type=stream_type,
            aggregate_id=aggregate_id,
            project_id=project_id,
            subject_type=subject_type,
            subject_id=subject_id,
            detail=(
                f"subject id {subject_id!r} must equal the stream aggregate "
                f"id {aggregate_id!r}"
            ),
        )
    if project_id != stream_project_id:
        raise StreamAgreementError(
            stream_type=stream_type,
            aggregate_id=aggregate_id,
            project_id=project_id,
            subject_type=subject_type,
            subject_id=subject_id,
            detail=(
                f"event project {project_id!r} disagrees with the stream "
                f"project {stream_project_id!r}"
            ),
        )
    if rule.aggregate_is_project and aggregate_id != project_id:
        raise StreamAgreementError(
            stream_type=stream_type,
            aggregate_id=aggregate_id,
            project_id=project_id,
            subject_type=subject_type,
            subject_id=subject_id,
            detail=(
                f"aggregate id {aggregate_id!r} must equal project id "
                f"{project_id!r} for {stream_type!r} streams"
            ),
        )
    if command_kind is not None:
        validate_command_kind(registry, command_kind)
        command_pack = registry.command_kinds[command_kind]
        if command_pack != stream_pack:
            raise StreamAgreementError(
                stream_type=stream_type,
                aggregate_id=aggregate_id,
                project_id=project_id,
                subject_type=subject_type,
                subject_id=subject_id,
                detail=(
                    f"command kind {command_kind!r} is declared by pack "
                    f"{command_pack!r} but stream type {stream_type!r} is "
                    f"declared by pack {stream_pack!r}"
                ),
            )
    return rule


__all__ = [
    "CORE_COMMAND_KINDS",
    "CORE_CONFORMANCE_DIMENSIONS",
    "CORE_EVENT_KINDS",
    "CORE_MANIFEST_VERSION",
    "CORE_PACK_ID",
    "CORE_REPOSITORIES",
    "CORE_STREAM_TYPES",
    "STREAM_AGGREGATE_RULES",
    "StreamAggregateRule",
    "aggregate_rule_for",
    "core_only_registry",
    "core_schema_pack_manifest",
    "register_core_vocabulary",
    "validate_command_kind",
    "validate_event_append",
    "validate_event_kind",
    "validate_stream_creation",
    "validate_stream_type",
]
