"""Compatibility exports for repository semantic errors.

The vocabulary errors are contracts shared by the event and repository
layers. Their canonical home is :mod:`astrid.core.contracts.errors`; this
module keeps the historical repository import path stable for callers.
"""

from astrid.core.contracts.vocabulary import (
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
