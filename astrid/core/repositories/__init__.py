"""Kernel repository implementations (m1 plan step 11; m2 plan step 1).

The first kernel repository vertical is the project repository: atomic,
idempotent project creation through the event append and receipt services,
with immutable read models and typed repository errors. Timeline, shots,
and references repositories belong to their packs and land with their
implementing milestones.

m2 adds three kernel repository verticals — the task repository (admission,
attempt lifecycle, completion), the media repository (import, locations,
relations), and the run repository (fan-out, group operations) — all
greenfield consumers of the same event append/receipt services. Their
modules land with their implementing tasks; the lazy export surface below
already declares their public names so the code-declared core manifest and
consumers can name the contract without importing the legacy executor
package (``astrid.core.execution``) or any pack.

The single typed error family lives in ``astrid.core.repositories.errors``
(plan step 8) and is re-exported eagerly. Repository surfaces are exposed
through a module-level ``__getattr__`` (the same lazy-export convention as
``astrid.core.generation.backends``) so that importing the kernel
vocabulary — ``astrid.core.events.registry`` imports this package for its
error types — never pulls in ``astrid.core.events.service`` and creates an
import cycle. The public names work exactly the same::

    from astrid.core.repositories import ProjectRepository, ProjectReadModel
"""

from __future__ import annotations

import importlib
from typing import Any

from astrid.core.repositories.errors import (
    CommandVocabularyError,
    EventVocabularyError,
    RepositoryError,
    StreamAgreementError,
    StreamVocabularyError,
)

__all__ = [
    "CORE_MEDIA_IMPORT_COMMAND_KIND",
    "CORE_MEDIA_IMPORTED_EVENT_KIND",
    "CORE_MEDIA_STREAM_TYPE",
    "CORE_EVIDENCE_RECORDED_EVENT_KIND",
    "CORE_EVIDENCE_RECORD_COMMAND_KIND",
    "CORE_PROJECT_CREATE_COMMAND_KIND",
    "CORE_PROJECT_CREATED_EVENT_KIND",
    "CORE_PROJECT_STREAM_TYPE",
    "CORE_RUN_CANCEL_COMMAND_KIND",
    "CORE_RUN_CANCELLED_EVENT_KIND",
    "CORE_RUN_CONTINUE_COMMAND_KIND",
    "CORE_RUN_CONTINUED_EVENT_KIND",
    "CORE_RUN_CREATE_COMMAND_KIND",
    "CORE_RUN_CREATED_EVENT_KIND",
    "CORE_RUN_STREAM_TYPE",
    "CORE_TASK_CANCEL_COMMAND_KIND",
    "CORE_TASK_CANCELLED_EVENT_KIND",
    "CORE_TASK_CLAIM_COMMAND_KIND",
    "CORE_TASK_CLAIMED_EVENT_KIND",
    "CORE_TASK_COMPLETE_COMMAND_KIND",
    "CORE_TASK_COMPLETED_EVENT_KIND",
    "CORE_TASK_CREATE_COMMAND_KIND",
    "CORE_TASK_CREATED_EVENT_KIND",
    "CORE_TASK_FAIL_COMMAND_KIND",
    "CORE_TASK_FAILED_EVENT_KIND",
    "CORE_TASK_STREAM_TYPE",
    "CommandVocabularyError",
    "DEFAULT_EVENT_READ_LIMIT",
    "EventNotFoundError",
    "EventReadError",
    "EventReadModel",
    "EventRepository",
    "EventRepositoryError",
    "EventVocabularyError",
    "EVIDENCE_KINDS",
    "EvidenceReadModel",
    "EvidenceRepository",
    "EvidenceRepositoryError",
    "EvidenceValidationError",
    "MAX_EVENT_READ_LIMIT",
    "MediaAlreadyExistsError",
    "MediaConflictError",
    "MediaLocationReadModel",
    "MediaNotFoundError",
    "MediaReadModel",
    "MediaRelationError",
    "MediaRelationReadModel",
    "MediaRelateReadModel",
    "MediaRepository",
    "MediaRepositoryError",
    "MediaValidationError",
    "ProjectAlreadyExistsError",
    "ProjectNotFoundError",
    "ProjectReadModel",
    "ProjectRepository",
    "ProjectRepositoryError",
    "ProjectSlugConflictError",
    "ProjectValidationError",
    "RepositoryError",
    "RunAlreadyExistsError",
    "RunContinuationReadModel",
    "RunFanOutReadModel",
    "RunNotFoundError",
    "RunReadModel",
    "RunRepository",
    "RunRepositoryError",
    "RunStaleHeadError",
    "RunValidationError",
    "StreamAgreementError",
    "StreamVocabularyError",
    "TaskAlreadyExistsError",
    "TaskAttemptReadModel",
    "TaskCancelReadModel",
    "TaskCompleteReadModel",
    "TaskFailReadModel",
    "TaskNotFoundError",
    "TaskOutputReadModel",
    "TaskReadModel",
    "TaskRepository",
    "TaskRepositoryError",
    "TaskValidationError",
]

_LAZY_PROJECT_NAMES = frozenset(
    {
        "CORE_PROJECT_CREATE_COMMAND_KIND",
        "CORE_PROJECT_CREATED_EVENT_KIND",
        "CORE_PROJECT_STREAM_TYPE",
        "ProjectAlreadyExistsError",
        "ProjectNotFoundError",
        "ProjectReadModel",
        "ProjectRepository",
        "ProjectRepositoryError",
        "ProjectSlugConflictError",
        "ProjectValidationError",
    }
)

_LAZY_TASK_NAMES = frozenset(
    {
        "CORE_TASK_CANCEL_COMMAND_KIND",
        "CORE_TASK_CANCELLED_EVENT_KIND",
        "CORE_TASK_CLAIM_COMMAND_KIND",
        "CORE_TASK_CLAIMED_EVENT_KIND",
        "CORE_TASK_COMPLETE_COMMAND_KIND",
        "CORE_TASK_COMPLETED_EVENT_KIND",
        "CORE_TASK_CREATE_COMMAND_KIND",
        "CORE_TASK_CREATED_EVENT_KIND",
        "CORE_TASK_FAIL_COMMAND_KIND",
        "CORE_TASK_FAILED_EVENT_KIND",
        "CORE_TASK_STREAM_TYPE",
        "TaskAlreadyExistsError",
        "TaskAttemptReadModel",
        "TaskCancelReadModel",
        "TaskCompleteReadModel",
        "TaskFailReadModel",
        "TaskNotFoundError",
        "TaskOutputReadModel",
        "TaskReadModel",
        "TaskRepository",
        "TaskRepositoryError",
        "TaskValidationError",
    }
)

_LAZY_MEDIA_NAMES = frozenset(
    {
        "CORE_MEDIA_IMPORT_COMMAND_KIND",
        "CORE_MEDIA_IMPORTED_EVENT_KIND",
        "CORE_MEDIA_STREAM_TYPE",
        "MediaAlreadyExistsError",
        "MediaConflictError",
        "MediaLocationReadModel",
        "MediaNotFoundError",
        "MediaReadModel",
        "MediaRelationError",
        "MediaRelationReadModel",
        "MediaRelateReadModel",
        "MediaRepository",
        "MediaRepositoryError",
        "MediaValidationError",
    }
)

_LAZY_RUN_NAMES = frozenset(
    {
        "CORE_RUN_CANCEL_COMMAND_KIND",
        "CORE_RUN_CANCELLED_EVENT_KIND",
        "CORE_RUN_CONTINUE_COMMAND_KIND",
        "CORE_RUN_CONTINUED_EVENT_KIND",
        "CORE_RUN_CREATE_COMMAND_KIND",
        "CORE_RUN_CREATED_EVENT_KIND",
        "CORE_RUN_STREAM_TYPE",
        "RunAlreadyExistsError",
        "RunContinuationReadModel",
        "RunFanOutReadModel",
        "RunNotFoundError",
        "RunReadModel",
        "RunRepository",
        "RunRepositoryError",
        "RunStaleHeadError",
        "RunValidationError",
    }
)

_LAZY_EVIDENCE_NAMES = frozenset(
    {
        "CORE_EVIDENCE_RECORDED_EVENT_KIND",
        "CORE_EVIDENCE_RECORD_COMMAND_KIND",
        "EVIDENCE_KINDS",
        "EvidenceReadModel",
        "EvidenceRepository",
        "EvidenceRepositoryError",
        "EvidenceValidationError",
    }
)

_LAZY_EVENT_NAMES = frozenset(
    {
        "DEFAULT_EVENT_READ_LIMIT",
        "EventNotFoundError",
        "EventReadError",
        "EventReadModel",
        "EventRepository",
        "EventRepositoryError",
        "MAX_EVENT_READ_LIMIT",
    }
)


def __getattr__(name: str) -> Any:
    if name in _LAZY_PROJECT_NAMES:
        module = importlib.import_module("astrid.core.repositories.projects")
        return getattr(module, name)
    if name in _LAZY_TASK_NAMES:
        module = importlib.import_module("astrid.core.repositories.tasks")
        return getattr(module, name)
    if name in _LAZY_MEDIA_NAMES:
        module = importlib.import_module("astrid.core.repositories.media")
        return getattr(module, name)
    if name in _LAZY_RUN_NAMES:
        module = importlib.import_module("astrid.core.repositories.runs")
        return getattr(module, name)
    if name in _LAZY_EVIDENCE_NAMES:
        module = importlib.import_module("astrid.core.repositories.evidence")
        return getattr(module, name)
    if name in _LAZY_EVENT_NAMES:
        module = importlib.import_module("astrid.core.repositories.events")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
