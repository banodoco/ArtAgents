"""Declarative WGP task conversion (Batch B7, gate 4).

The reigh-worker contract (`source/task_handlers/tasks/task_conversion.py`,
doc 03 §3.4): whitelist the task params, default ``model`` from the
declarative ``TASK_TYPE_TO_MODEL`` preset table, force
``video_length=1`` for the t2i image family, and materialize LoRA URLs.
Everything here is pure data + one pure function so gate ④ can pin
byte-identical golden fixtures over it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

#: Source task type -> WGP model preset key (doc 03 §3.4). Declarative:
#: adding a capability is a table row, never an executor branch. The
#: orchestrator rows are deliberately absent — they coordinate children,
#: they never generate directly; converting one refuses typed.
TASK_TYPE_TO_MODEL: dict[str, str] = {
    "wan_2_2_t2i": "t2v_2_2",
    "wan_2_2_i2v": "i2v_14B",
    # Catalog-only legacy keys map too (doc 03 §3.4).
    "t2v": "t2v_2_2",
    "i2v": "i2v_14B",
    # Worker-child segment/stitch families ride the VACE lightning preset.
    "travel_segment": "wan_2_2_vace_lightning_baseline_2_2_2",
    "individual_travel_segment": "wan_2_2_vace_lightning_baseline_2_2_2",
    "join_clips_segment": "wan_2_2_vace_lightning_baseline_2_2_2",
    "join_final_stitch": "wan_2_2_vace_lightning_baseline_2_2_2",
    "travel_stitch": "wan_2_2_vace_lightning_baseline_2_2_2",
}

#: The full param whitelist (doc 03 §2.5). Nothing outside this set ever
#: reaches a WGP generation task.
PARAM_WHITELIST: frozenset[str] = frozenset(
    {
        "prompt",
        "model",
        "resolution",
        "video_length",
        "num_inference_steps",
        "guidance_scale",
        "seed",
        "negative_prompt",
        "image",
        "image_url",
        "mask_url",
        "video_guide",
        "video_mask",
        "image_start",
        "image_end",
        "image_refs",
        "audio_guide",
        "activated_loras",
        "loras",
        "additional_loras",
        "phase_config",
        "travel_chain_details",
        "orchestrator_details",
        "segment_image_download_dir",
        "portions_to_regenerate",
        "clip_list",
    }
)

T2I_TASK_TYPE = "wan_2_2_t2i"
"""The t2i image family forces ``video_length=1`` (doc 16 §3.1)."""


class ConversionRefused(Exception):
    """Typed refusal: unknown task type or non-mapping params."""


@dataclass(frozen=True, slots=True)
class GenerationTask:
    """The whitelisted, defaulted WGP-side task shape."""

    id: str
    model: str
    prompt: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "model": self.model,
            "prompt": self.prompt,
            "parameters": self.parameters,
        }


def resolve_model(task_type: str, params: Mapping[str, Any]) -> str:
    """Explicit ``model`` param wins; otherwise the declared preset."""
    explicit = params.get("model")
    if isinstance(explicit, str) and explicit:
        return explicit
    try:
        return TASK_TYPE_TO_MODEL[task_type]
    except KeyError:
        raise ConversionRefused(
            f"task type {task_type!r} has no TASK_TYPE_TO_MODEL preset; "
            "conversion is refused, not guessed"
        ) from None


def convert_task(
    params: Mapping[str, Any], *, task_id: str, task_type: str
) -> GenerationTask:
    """Whitelist → default → force: the whole conversion contract.

    - params outside :data:`PARAM_WHITELIST` are dropped;
    - ``model`` defaults from :data:`TASK_TYPE_TO_MODEL`;
    - the t2i family forces ``video_length=1``;
    - unknown task types refuse typed (mapping is exhaustive).
    """
    if not isinstance(params, Mapping):
        raise ConversionRefused("task params must be a JSON object")
    model = resolve_model(task_type, params)
    parameters = {
        key: value
        for key, value in params.items()
        if key in PARAM_WHITELIST
    }
    parameters["model"] = model
    if task_type == T2I_TASK_TYPE:
        parameters["video_length"] = 1
    prompt = parameters.get("prompt")
    if not isinstance(prompt, str):
        prompt = ""
    return GenerationTask(
        id=task_id, model=model, prompt=prompt, parameters=parameters
    )


def download_loras(
    parameters: Mapping[str, Any],
    dest_dir: Path,
    *,
    downloader: Callable[[str, Path], None],
) -> list[Path]:
    """Materialize LoRA task-param URLs into *dest_dir*.

    ``loras``/``additional_loras`` entries are either plain names (already
    cached upstream — passed through untouched) or URL strings downloaded
    through the injected *downloader* at conversion time (doc 03 §3.4).
    Returns the downloaded paths; deterministic order.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for key in ("activated_loras", "loras", "additional_loras"):
        entries = parameters.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, str) or not entry:
                continue
            if "://" not in entry:
                continue  # plain cache name: nothing to fetch
            name = entry.rstrip("/").rsplit("/", 1)[-1]
            target = dest_dir / name
            downloader(entry, target)
            downloaded.append(target)
    return downloaded


def fixture_digest(task: GenerationTask) -> str:
    """Canonical SHA-256 of a converted task (gate ④ byte identity)."""
    import json

    payload = json.dumps(task.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
