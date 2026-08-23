"""Deterministic prompt generation for Runaway timing transitions.

Each of the 566 transitions in timing-manifest.json currently has zero prompt
data. This module provides the typed, deterministic prompt list that the
runaway:timing-v1 migration inserts into ``runaway_transitions.prompt``.

Design: per segment-pair / colour / timing_mode, the template is
  "{colour} neon piano chord, hard cut, 48fps, complementary colour {next},
   {timing_mode}, {segment_id}"

The palette has 8 colours (rose, orange, gold, green, teal, blue, indigo,
violet) at OKLCH L=0.68, paired as complementary equal-lightness colours
([0,4], [1,5], [2,6], [3,7]). Transitions alternate between the pair inside
each segment, so the next colour is the literal next transition's colour.
For the final transition the next colour is "hold".

The template is deterministic and round-trippable: the same transition facts
always produce the same prompt, and the 10-sample slice used in tests is the
prefix of the full 566.
"""

from __future__ import annotations

from typing import Any, Mapping

# Full 566 design: expose the template so the migration can generate all.
PROMPT_TEMPLATE = (
    "{colour_name} neon piano chord, hard cut, 48fps, complementary colour {next_colour}, {timing_mode}, {segment_id}"
)

# 10-sample slice for quick testing; the migration generates the full list.
SAMPLE_COUNT = 10


def build_prompt(
    *,
    colour_name: str,
    timing_mode: str,
    segment_id: str,
    next_colour_name: str,
) -> str:
    """Return the deterministic prompt for one transition.

    Pure function: no I/O, no randomness, suitable for receipt-hashed
    idempotency checks. Trims nothing; the repository validates non-empty.
    """
    return PROMPT_TEMPLATE.format(
        colour_name=colour_name,
        next_colour=next_colour_name,
        timing_mode=timing_mode,
        segment_id=segment_id,
    )


def prompts_for_manifest(
    transitions: list[Mapping[str, Any]],
) -> list[str]:
    """Generate the full deterministic prompt list for a manifest's transitions.

    Transitions are assumed already ordered by the manifest's implicit ordinal
    (the array order). The next colour for each entry is the colour of the
    following transition, with "hold" for the final entry.
    """
    prompts: list[str] = []
    n = len(transitions)
    for idx, tr in enumerate(transitions):
        colour = str(tr.get("colour_name") or tr.get("colour") or "rose")
        timing_mode = str(tr.get("timing_mode") or "literal_main_note")
        segment_id = str(tr.get("segment_id") or "S01")
        if idx + 1 < n:
            nxt = transitions[idx + 1]
            next_colour = str(nxt.get("colour_name") or nxt.get("colour") or "hold")
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
    """Return the 10-sample slice (prefix) for tests."""
    return prompts_for_manifest(transitions[:SAMPLE_COUNT])
