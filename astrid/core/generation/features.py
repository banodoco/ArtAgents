"""Canonical feature list for the generation ecosystem.

Each feature is a string whose presence in a *mode's* ``supports`` list means
the (model, mode, backend) cell honors it.  Features live on the mode (per-mode
semantics — SD-003), not on the model.  A mode may support a feature on one
backend and not another; the per-backend ``param_map`` encodes the actual
mapping.

.. note::
    Both image- and video-modality features are listed here as of Sprint 04.
    Future sprints will add audio-modality features to the same canonical list.
    Edit is now a *mode* of image, not a separate modality (SD-007).
"""

from __future__ import annotations

from typing import Literal

Feature = Literal[
    "prompt",
    "negative_prompt",
    "seed",
    "count",
    "size",
    "image_ref",
    "image_end_ref",
    "strength",
    "guidance_scale",
    "steps",
    "frames",
    "fps",
    "duration",
    "resolution",
    "loras",
    "shift",
    "enable_safety_checker",
    "enable_prompt_expansion",
    "acceleration",
]

IMAGE_FEATURES: tuple[Feature, ...] = (
    "prompt",
    "negative_prompt",
    "seed",
    "count",
    "size",
    "image_ref",
    "strength",
    "guidance_scale",
    "steps",
)

VIDEO_FEATURES: tuple[Feature, ...] = (
    "prompt",
    "negative_prompt",
    "seed",
    "count",
    "size",
    "image_ref",
    "image_end_ref",
    "strength",
    "guidance_scale",
    "steps",
    "frames",
    "fps",
    "duration",
    "resolution",
    "loras",
    "shift",
    "enable_safety_checker",
    "enable_prompt_expansion",
    "acceleration",
)
