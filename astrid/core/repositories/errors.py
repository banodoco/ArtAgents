"""Compatibility exports for shared repository contract errors."""

from astrid.core.contracts.vocabulary_errors import (
    ACTOR_KINDS,
    CommandVocabularyError,
    EventVocabularyError,
    RepositoryError,
    StreamAgreementError,
    StreamVocabularyError,
)

__all__ = [
    "ACTOR_KINDS",
    "CommandVocabularyError",
    "EventVocabularyError",
    "RepositoryError",
    "StreamAgreementError",
    "StreamVocabularyError",
]
