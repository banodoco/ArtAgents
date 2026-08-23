"""Runaway schema pack (in-tree, explicitly registered).

The runaway pack owns the ``runaway_transitions`` table plus the namespaced
``runaway.*`` command vocabulary declared in ``schema-pack.yaml`` next to
this module. The table FK-integrates with the kernel run table
(``runs.id`` RESTRICT, ``projects.id`` CASCADE, ``tasks.id`` SET NULL) and
handles sharding for >256 transitions via ``continue_run`` (ordinal
contiguous globally, ``run_id`` per shard).

This package marker stays minimal: the composed registry and migration
runner consume the manifest file, and startup registers this pack through
the single explicit ``register_pack()`` path — never through discovery or
the capability-pack loader.
"""

from __future__ import annotations

from astrid.packs.runaway.prompts import build_prompt, prompts_for_manifest, sample_prompts
from astrid.packs.runaway.repository import (
    RUNAWAY_CREATE_COMMAND_KIND,
    RunawayAlreadyExistsError,
    RunawayCreateReadModel,
    RunawayNotFoundError,
    RunawayRepository,
    RunawayRepositoryError,
    RunawayTransitionReadModel,
    RunawayValidationError,
)

__all__ = [
    "RUNAWAY_CREATE_COMMAND_KIND",
    "RunawayAlreadyExistsError",
    "RunawayCreateReadModel",
    "RunawayNotFoundError",
    "RunawayRepository",
    "RunawayRepositoryError",
    "RunawayTransitionReadModel",
    "RunawayValidationError",
    "build_prompt",
    "prompts_for_manifest",
    "sample_prompts",
]
