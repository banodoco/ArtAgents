"""Realistic-shape test orchestrator: dynamic-items for_each pattern.

Mirrors the shape of LoRA-grid eval, scene-triage, batch classification: an
upstream step enumerates the items, a fan-out step classifies each one, a
downstream step aggregates. The probe target: does the agent handle the
``items_source = "from"`` mechanism cleanly — read items from a prior step's
produces, then ack per item with --item, then aggregate?

Real packs hit this shape constantly (every for_each over discovered scenes,
shots, candidates, etc.). agent_probe's for_each used static items; this
orchestrator tests the dynamic-items code path which is structurally
different in the gate.
"""

from __future__ import annotations

from astrid.orchestrate import attested, orchestrator, repeat_for_each
from astrid.verify import json_schema


@orchestrator("builtin.classify_grid")
def classify_grid():
    return [
        # 1. Enumerate items the for_each will iterate over. Real packs do
        # this from a triage / discovery step; here the agent invents 3-5
        # plausible Astrid pack names.
        attested(
            "enumerate_items",
            command="echo enumerate_items",
            instructions=(
                "Invent 4 plausible Astrid pack names (snake_case strings) that "
                "could plausibly exist (e.g. 'image_grade', 'caption_summary'). "
                "Use short slug-shaped strings — no spaces, lowercase, alphanumeric "
                "plus underscores only.\n"
                "Write to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/enumerate_items/v1/produces/items.json\n"
                "Shape: a bare JSON array (NOT an object): "
                "[\"pack_a\", \"pack_b\", \"pack_c\", \"pack_d\"].\n"
                "The for_each step downstream reads this file as a list of item ids.\n"
                "Then ack."
            ),
            ack="agent",
            produces={
                # Bare list — `for_each.from` reads this file as the items array
                # directly. The prior {items: [...]} object shape passed the
                # produces check but failed `for_each.from` with the confusing
                # "items must be unique strings" error (one DS agent in the v3
                # probe had to grep gate.py to diagnose). Plan-level contract
                # alignment matters more than schema convenience.
                "items.json": json_schema(
                    {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {
                            "type": "string",
                            "pattern": "^[a-z][a-z0-9_]*$",
                        },
                    }
                ),
            },
        ),

        # 2. For each invented pack name, classify what category it belongs to.
        # items_source = from a prior step's produces.
        attested(
            "classify",
            command="echo classify",
            instructions=(
                "For THIS item ($ASTRID_TASK_ITEM_ID), classify the hypothetical "
                "pack into one of these categories: 'video', 'image', 'audio', "
                "'text', 'metadata'. Provide one sentence of reasoning.\n"
                "Write to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/classify/v1/items/$ASTRID_TASK_ITEM_ID/produces/classification.json\n"
                "Shape: {\"pack\": \"<item-id>\", \"category\": \"<one of the 5>\", "
                "\"reason\": \"<one sentence>\"}\n"
                "Ack with --item $ASTRID_TASK_ITEM_ID. Repeat for each item that "
                "`astrid next` surfaces."
            ),
            ack="agent",
            produces={
                "classification.json": json_schema(
                    {
                        "type": "object",
                        "required": ["pack", "category", "reason"],
                        "properties": {
                            "pack": {"type": "string"},
                            "category": {
                                "type": "string",
                                "enum": ["video", "image", "audio", "text", "metadata"],
                            },
                            "reason": {"type": "string"},
                        },
                    }
                ),
            },
            repeat=repeat_for_each(from_="enumerate_items.produces.items.json"),
        ),

        # 3. Aggregate all the per-item classifications.
        attested(
            "aggregate",
            command="echo aggregate",
            instructions=(
                "Read every classification.json file written by the prior step:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/classify/v1/items/<each item-id>/produces/classification.json\n"
                "Tally category counts across all items.\n"
                "Write to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/aggregate/v1/produces/summary.json\n"
                "Shape: {\"by_category\": {\"video\": <int>, \"image\": <int>, "
                "\"audio\": <int>, \"text\": <int>, \"metadata\": <int>}, "
                "\"total\": <int>, \"items\": [\"<pack1>\", ...]}\n"
                "All five category keys must be present even if 0.\n"
                "Then ack."
            ),
            ack="agent",
            produces={
                "summary.json": json_schema(
                    {
                        "type": "object",
                        "required": ["by_category", "total", "items"],
                        "properties": {
                            "by_category": {
                                "type": "object",
                                "required": ["video", "image", "audio", "text", "metadata"],
                                "properties": {
                                    "video": {"type": "integer"},
                                    "image": {"type": "integer"},
                                    "audio": {"type": "integer"},
                                    "text": {"type": "integer"},
                                    "metadata": {"type": "integer"},
                                },
                            },
                            "total": {"type": "integer", "minimum": 4},
                            "items": {
                                "type": "array",
                                "minItems": 4,
                                "items": {"type": "string"},
                            },
                        },
                    }
                ),
            },
        ),
    ]
