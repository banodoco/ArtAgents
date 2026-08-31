"""Deterministic prompt generation for typed timeline transition rows.

The prompt function is a pure source-side helper for the typed timeline
capability. It does not define a schema pack, migration, repository, or
workspace storage authority.
"""

from __future__ import annotations

from typing import Any, Mapping

PROMPT_TEMPLATE = (
    "{colour_name} neon piano chord, hard cut, 48fps, complementary colour "
    "{next_colour}, {timing_mode}, {segment_id}"
)
SAMPLE_COUNT = 10


def build_prompt(
    *,
    colour_name: str,
    timing_mode: str,
    segment_id: str,
    next_colour_name: str,
) -> str:
    """Return the deterministic prompt for one transition row."""
    return PROMPT_TEMPLATE.format(
        colour_name=colour_name,
        next_colour=next_colour_name,
        timing_mode=timing_mode,
        segment_id=segment_id,
    )


def prompts_for_manifest(
    transitions: list[Mapping[str, Any]],
) -> list[str]:
    """Generate prompts in the supplied transition order."""
    prompts: list[str] = []
    n = len(transitions)
    for idx, transition in enumerate(transitions):
        colour = str(
            transition.get("colour_name") or transition.get("colour") or "rose"
        )
        timing_mode = str(transition.get("timing_mode") or "literal_main_note")
        segment_id = str(transition.get("segment_id") or "S01")
        if idx + 1 < n:
            following = transitions[idx + 1]
            next_colour = str(
                following.get("colour_name") or following.get("colour") or "hold"
            )
        else:
            next_colour = "hold"
        prompts.append(
            build_prompt(
                colour_name=colour,
                timing_mode=timing_mode,
                segment_id=segment_id,
                next_colour_name=next_colour,
            )
        )
    return prompts


def sample_prompts(transitions: list[Mapping[str, Any]]) -> list[str]:
    """Return the deterministic prefix used by the focused fixture."""
    return prompts_for_manifest(transitions[:SAMPLE_COUNT])


__all__ = ["build_prompt", "prompts_for_manifest", "sample_prompts"]
