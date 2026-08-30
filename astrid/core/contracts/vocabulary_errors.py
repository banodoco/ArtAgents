"""Shared vocabulary and stream-agreement errors."""

from __future__ import annotations

from astrid.core.contracts.writer import WriterError


class RepositoryError(WriterError):
    """Base error for repository semantic violations."""


class StreamVocabularyError(RepositoryError):
    """Raised when a stream type is not declared or not namespaced."""

    def __init__(self, *, stream_type: str, reason: str) -> None:
        self.stream_type = stream_type
        self.reason = reason
        super().__init__(f"stream vocabulary violation for {stream_type!r}: {reason}")


class EventVocabularyError(RepositoryError):
    """Raised when an event kind is not declared or not namespaced."""

    def __init__(self, *, event_kind: str, reason: str) -> None:
        self.event_kind = event_kind
        self.reason = reason
        super().__init__(f"event vocabulary violation for {event_kind!r}: {reason}")


class CommandVocabularyError(RepositoryError):
    """Raised when a command kind is not declared or not namespaced."""

    def __init__(self, *, command_kind: str, reason: str) -> None:
        self.command_kind = command_kind
        self.reason = reason
        super().__init__(f"command vocabulary violation for {command_kind!r}: {reason}")


class StreamAgreementError(RepositoryError):
    """Raised when aggregate/type/project agreement is violated."""

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
        self.stream_type = stream_type
        self.aggregate_id = aggregate_id
        self.project_id = project_id
        self.subject_type = subject_type
        self.subject_id = subject_id
        self.detail = detail
        super().__init__(f"stream agreement violation for {stream_type!r}: {detail}")


ACTOR_KINDS: frozenset[str] = frozenset({"local", "system", "executor"})


__all__ = [
    "ACTOR_KINDS",
    "CommandVocabularyError",
    "EventVocabularyError",
    "RepositoryError",
    "StreamAgreementError",
    "StreamVocabularyError",
]
