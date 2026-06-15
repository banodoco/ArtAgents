"""Python DSL for authoring Astrid task-mode orchestrators (Phase 4).

Authors write `<pack>/<orch>.py` using the helpers exported here. The DSL
emits a JSON manifest that is byte-shape-equivalent to the schema accepted
by `astrid.core.task.plan.load_plan`.
"""

from __future__ import annotations

from astrid.core.verify import (
    all_of,
    audio_duration_min,
    file_nonempty,
    image_dimensions,
    json_file,
    json_schema,
)

from .compile import compile_to_path, compile_to_pipeline, dsl_to_pipeline
from .dsl import (
    OrchestrateDefinitionError,
    attested,
    code,
    nested,
    orchestrator,
    plan,
    repeat_for_each,
    repeat_until,
)

__all__ = [
    "OrchestrateDefinitionError",
    "all_of",
    "attested",
    "audio_duration_min",
    "code",
    "compile_to_path",
    "compile_to_pipeline",
    "dsl_to_pipeline",
    "file_nonempty",
    "image_dimensions",
    "json_file",
    "json_schema",
    "nested",
    "orchestrator",
    "plan",
    "repeat_for_each",
    "repeat_until",
]
