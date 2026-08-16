"""Typed repository errors for semantic mutation guards (m1 plan step 8).

Every repository command validates its stream, event, and command vocabulary
against the frozen composed registry *before* any SQL mutation (see
``astrid.core.events.registry``). The typed errors in this module are the
single error surface for those guards, so handlers never invent their own
ad-hoc ``ValueError`` strings and callers can catch the whole semantic
repository family.

The hierarchy mirrors the kernel store family: the base
:class:`RepositoryError` subclasses
:class:`astrid.core.store.writer.WriterError` (as do
``UoWError`` and ``ReceiptError``), so a caller already handling writer
errors (busy, shutdown, transaction control) also catches repository
contract violations, while each concrete class stays distinguishable.

Categories:

- :class:`StreamVocabularyError` — a stream type is missing from the frozen
  registry or is not a namespaced dotted name.
- :class:`EventVocabularyError` — an event kind is missing or non-namespaced.
- :class:`CommandVocabularyError` — a command kind is missing or
  non-namespaced.
- :class:`StreamAgreementError` — the aggregate/type/project agreement for a
  core or pack stream is violated (for example an event whose subject is not
  the stream's aggregate, an event kind declared by a different pack than the
  stream type, or a ``core.project`` stream whose aggregate id is not the
  project id).

Duplicate declarations are impossible on this path by construction: the
registry builder rejects every duplicate class (pack id, table, migration,
stream type, event kind, command kind, repository, mount) before freezing
(``astrid.core.schema_packs.registry``), so the runtime guards reject
*missing* and *non-namespaced* names and defer duplicate rejection to the
registration-time guarantee.
"""

from __future__ import annotations

from astrid.core.store.writer import WriterError

__all__ = [
    "CommandVocabularyError",
    "EventVocabularyError",
    "RepositoryError",
    "StreamAgreementError",
    "StreamVocabularyError",
]


class RepositoryError(WriterError):
    """Base error for repository semantic violations.

    Subclasses :class:`astrid.core.store.writer.WriterError` so callers that
    handle the kernel store error family also catch repository contract
    violations, exactly like ``UoWError`` and ``ReceiptError`` do.
    """


class StreamVocabularyError(RepositoryError):
    """Raised when a stream type is not declared or not namespaced.

    Carries the offending ``stream_type`` and the reason so callers can
    distinguish an undeclared name from a malformed one.
    """

    def __init__(self, *, stream_type: str, reason: str) -> None:
        self.stream_type: str = stream_type
        self.reason: str = reason
        super().__init__(
            f"stream vocabulary violation for {stream_type!r}: {reason}"
        )


class EventVocabularyError(RepositoryError):
    """Raised when an event kind is not declared or not namespaced."""

    def __init__(self, *, event_kind: str, reason: str) -> None:
        self.event_kind: str = event_kind
        self.reason: str = reason
        super().__init__(
            f"event vocabulary violation for {event_kind!r}: {reason}"
        )


class CommandVocabularyError(RepositoryError):
    """Raised when a command kind is not declared or not namespaced."""

    def __init__(self, *, command_kind: str, reason: str) -> None:
        self.command_kind: str = command_kind
        self.reason: str = reason
        super().__init__(
            f"command vocabulary violation for {command_kind!r}: {reason}"
        )


class StreamAgreementError(RepositoryError):
    """Raised when aggregate/type/project agreement is violated.

    Carries the stream facts involved (stream type, aggregate id, project
    id, subject type/id when known) plus a human-readable ``detail`` so
    tests and logs can pin down exactly which agreement failed.
    """

    def __init__(
        self,
        *,
        stream_type: str,
        detail: str,
        aggregate_id: str | None = None,
        project_id: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        self.stream_type: str = stream_type
        self.aggregate_id: str | None = aggregate_id
        self.project_id: str | None = project_id
        self.subject_type: str | None = subject_type
        self.subject_id: str | None = subject_id
        self.detail: str = detail
        super().__init__(
            f"stream agreement violation for {stream_type!r}: {detail}"
        )

ACTOR_KINDS: frozenset[str] = frozenset({"local", "system", "executor"})
