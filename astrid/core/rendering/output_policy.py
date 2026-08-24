"""Shared public-output admission policy for timeline rendering.

The executor facade, managed SDK admission, and :class:`RenderService` all
use this module.  Keeping the decision here prevents the project route from
admitting a run that the lower-level render service will deterministically
reject later.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .contracts import RenderProfile

DEFAULT_RENDER_OUTPUT_NAME = "hype.mp4"


class RenderOutputPolicyError(ValueError):
    """A deterministic output-name/profile admission failure."""

    def __init__(
        self,
        message: str,
        *,
        recovery_command: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.recovery_command = recovery_command
        self.details = dict(details or {})


def validate_output_basename(name: Any) -> str:
    """Return a safe portable basename without imposing a media suffix."""

    if not isinstance(name, str):
        raise RenderOutputPolicyError(
            "output_name must be a string",
            recovery_command="supply a plain output filename and retry",
            details={"output_name": name},
        )
    if name == "":
        raise RenderOutputPolicyError(
            "output_name must not be empty",
            recovery_command="supply a plain output filename and retry",
            details={"output_name": name},
        )
    if name in {".", ".."} or name.startswith(".."):
        raise RenderOutputPolicyError(
            f"output_name must not traverse directories, got {name!r}",
            recovery_command="supply a plain output filename without traversal",
            details={"output_name": name},
        )
    if "/" in name or "\\" in name or name.startswith(os.sep):
        raise RenderOutputPolicyError(
            f"output_name must be a plain file name without path separators, got {name!r}",
            recovery_command="supply a basename such as final.mp4",
            details={"output_name": name},
        )
    if Path(name).name != name:
        raise RenderOutputPolicyError(
            f"output_name must be a plain file name, got {name!r}",
            recovery_command="supply a basename such as final.mp4",
            details={"output_name": name},
        )
    return name


def timeline_is_alpha_stamped(timeline: Mapping[str, Any] | str | Path) -> bool:
    """Return whether the exact public alpha-layer stamp is present.

    Paths fail closed when unreadable or malformed.  This narrow probe is an
    admission predicate only; normal timeline/schema validation remains with
    the renderer and managed-snapshot validator.
    """

    raw: Any = timeline
    if isinstance(timeline, (str, Path)):
        try:
            raw = json.loads(Path(timeline).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return False
    if not isinstance(raw, Mapping):
        return False
    metadata = raw.get("metadata")
    if not isinstance(metadata, Mapping):
        return False
    layer = metadata.get("astrid_layer")
    return isinstance(layer, Mapping) and layer.get("alpha") is True


def _profile_mapping(profile: RenderProfile | Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if profile is None:
        return None
    if isinstance(profile, RenderProfile):
        return profile.to_dict()
    return profile


def validate_render_output_policy(
    output_name: Any,
    *,
    timeline: Mapping[str, Any] | str | Path,
    profile: RenderProfile | Mapping[str, Any] | None,
) -> str:
    """Validate the shared filename/container/alpha contract.

    MP4 remains the default.  A MOV basename is reserved for an explicitly
    alpha-stamped layer and, when a profile is supplied, that profile must
    describe the truthful ProRes 4444 + PCM mux.  Other explicit containers
    retain the established suffix-matching contract.
    """

    name = validate_output_basename(output_name)
    lowered = name.lower()
    profile_data = _profile_mapping(profile)
    alpha = timeline_is_alpha_stamped(timeline)

    if lowered.endswith(".mov"):
        if not alpha:
            raise RenderOutputPolicyError(
                f"output_name {name!r} uses .mov, but the timeline is not stamped "
                "metadata.astrid_layer.alpha=true",
                recovery_command=(
                    "use a .mp4 output name for an opaque timeline, or add the exact "
                    "alpha-layer stamp before requesting MOV"
                ),
                details={
                    "output_name": name,
                    "required_timeline_stamp": "metadata.astrid_layer.alpha=true",
                },
            )
        if profile_data is not None:
            required = {
                "time_base": [1, 90000],
                "container": "mov",
                "video_codec": "prores",
                "video_profile": None,
                "video_level": None,
                "pixel_format": "yuva444p12le",
                "audio_codec": "pcm_s16le",
                "audio_sample_rate": 48000,
                "audio_channel_layout": "stereo",
            }
            mismatches = [
                f"{field}={profile_data.get(field)!r} (requires {expected!r})"
                for field, expected in required.items()
                if profile_data.get(field) != expected
            ]
            if mismatches:
                raise RenderOutputPolicyError(
                    "alpha MOV output has an incompatible explicit render profile: "
                    + "; ".join(mismatches),
                    recovery_command=(
                        "omit --profile to use the authoritative alpha profile, or request "
                        "MOV/ProRes/yuva444p12le with PCM s16le at 48 kHz stereo"
                    ),
                    details={"output_name": name, "profile_mismatches": mismatches},
                )
        return name

    expected = ".mp4"
    if profile_data is not None:
        container = profile_data.get("container")
        if isinstance(container, str) and container:
            expected = f".{container.lower()}"
    if not lowered.endswith(expected):
        raise RenderOutputPolicyError(
            f"output_name must end in {expected} for the selected render profile; got {name!r}",
            recovery_command=f"retry with output_name ending in {expected}",
            details={"output_name": name, "required_suffix": expected},
        )
    return name


__all__ = [
    "DEFAULT_RENDER_OUTPUT_NAME",
    "RenderOutputPolicyError",
    "timeline_is_alpha_stamped",
    "validate_output_basename",
    "validate_render_output_policy",
]
