"""Realistic-shape test orchestrator: research-and-write pattern.

Mirrors the shape of a real research / summarization pack: agent reads source
material, structures key findings, generates an outline, expands each section,
assembles a final report, then reviews. Heavy on attested steps with strict
schemas and explicit inter-step data flow — the same dependency chain shape
that real packs (hype, refine, editor_review) have but compressed to small
fixture-sized artifacts.

The probe target: does the agent thread `produces` from earlier steps into
later steps cleanly, or improvise paths / forget what step 2 wrote?
"""

from __future__ import annotations

from astrid.orchestrate import attested, orchestrator, repeat_for_each
from astrid.verify import json_file, json_schema


@orchestrator("builtin.mini_research")
def mini_research():
    return [
        # 1. Read 3 specific source files and extract key takeaways.
        attested(
            "read_sources",
            command="echo read_sources",
            instructions=(
                "Read these three files in this Astrid checkout and extract their "
                "key takeaways:\n"
                "  - astrid/core/task/preamble.py (1 takeaway: what the preamble enforces)\n"
                "  - astrid/core/task/gate.py (1 takeaway: what the gate checks)\n"
                "  - astrid/core/task/events.py (1 takeaway: how events are chained)\n"
                "Write a JSON file at:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/read_sources/v1/produces/sources.json\n"
                "Shape: {\"takeaways\": [{\"file\": \"<path>\", \"takeaway\": \"<1-2 sentences>\"}, ...]}\n"
                "Then ack."
            ),
            ack="agent",
            produces={
                "sources.json": json_schema(
                    {
                        "type": "object",
                        "required": ["takeaways"],
                        "properties": {
                            "takeaways": {
                                "type": "array",
                                "minItems": 3,
                                "items": {
                                    "type": "object",
                                    "required": ["file", "takeaway"],
                                    "properties": {
                                        "file": {"type": "string"},
                                        "takeaway": {"type": "string"},
                                    },
                                },
                            },
                        },
                    }
                ),
            },
        ),

        # 2. Outline a short report based on the takeaways.
        attested(
            "write_outline",
            command="echo write_outline",
            instructions=(
                "Read sources.json from the prior step:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/read_sources/v1/produces/sources.json\n"
                "Write a 3-section outline for a short report about Astrid's task-mode "
                "guarantees. Each section needs a unique short id (e.g. 'intro', "
                "'invariants', 'recovery').\n"
                "Write to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/write_outline/v1/produces/outline.json\n"
                "Shape: {\"sections\": [{\"id\": \"<short-id>\", \"title\": \"<one line>\", "
                "\"theme\": \"<one sentence>\"}, ...]}\n"
                "Then ack."
            ),
            ack="agent",
            produces={
                "outline.json": json_schema(
                    {
                        "type": "object",
                        "required": ["sections"],
                        "properties": {
                            "sections": {
                                "type": "array",
                                "minItems": 3,
                                "maxItems": 3,
                                "items": {
                                    "type": "object",
                                    "required": ["id", "title", "theme"],
                                    "properties": {
                                        "id": {"type": "string"},
                                        "title": {"type": "string"},
                                        "theme": {"type": "string"},
                                    },
                                },
                            },
                        },
                    }
                ),
            },
        ),

        # 3. Per-section expansion. Three fixed items (the outline ids are
        # known at author time, so we don't need from_-based dynamic items
        # for this probe — that's covered by classify_grid).
        attested(
            "write_section",
            command="echo write_section",
            instructions=(
                "Expand the section identified by $ASTRID_TASK_ITEM_ID into a "
                "short paragraph (3-5 sentences) drawing on the takeaways from "
                "read_sources and the outline's theme for this section.\n"
                "Read prior produces:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/read_sources/v1/produces/sources.json\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/write_outline/v1/produces/outline.json\n"
                "Write to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/write_section/v1/items/$ASTRID_TASK_ITEM_ID/produces/section.json\n"
                "Shape: {\"section_id\": \"<id>\", \"body\": \"<paragraph>\"}\n"
                "Ack with --item $ASTRID_TASK_ITEM_ID. Repeat for each item."
            ),
            ack="agent",
            produces={
                "section.json": json_schema(
                    {
                        "type": "object",
                        "required": ["section_id", "body"],
                        "properties": {
                            "section_id": {"type": "string"},
                            "body": {"type": "string"},
                        },
                    }
                ),
            },
            repeat=repeat_for_each(items=["intro", "invariants", "recovery"]),
        ),

        # 4. Assembly step. Reads ALL prior section outputs, combines.
        attested(
            "assemble",
            command="echo assemble",
            instructions=(
                "Read every section file:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/write_section/v1/items/<item-id>/produces/section.json\n"
                "for item-id in {intro, invariants, recovery}. Combine them in that "
                "order into a final assembled report.\n"
                "Write to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/assemble/v1/produces/report.json\n"
                "Shape: {\"sections\": [\"<intro body>\", \"<invariants body>\", "
                "\"<recovery body>\"], \"word_count\": <int>}\n"
                "Then ack."
            ),
            ack="agent",
            produces={
                "report.json": json_schema(
                    {
                        "type": "object",
                        "required": ["sections", "word_count"],
                        "properties": {
                            "sections": {
                                "type": "array",
                                "minItems": 3,
                                "maxItems": 3,
                                "items": {"type": "string"},
                            },
                            "word_count": {"type": "integer", "minimum": 1},
                        },
                    }
                ),
            },
        ),

        # 5. Review. One-step review with a structured verdict.
        attested(
            "review",
            command="echo review",
            instructions=(
                "Read the assembled report:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/assemble/v1/produces/report.json\n"
                "Produce a structured verdict. Required fields: \"verdict\" "
                "(one of 'ship' | 'revise'), \"concerns\" (array of strings, may be "
                "empty), \"strengths\" (array of strings, may be empty).\n"
                "Write to:\n"
                "  $ASTRID_PROJECTS_ROOT/$ASTRID_TASK_PROJECT/runs/$ASTRID_TASK_RUN_ID/"
                "steps/review/v1/produces/verdict.json\n"
                "Then ack."
            ),
            ack="agent",
            produces={
                "verdict.json": json_schema(
                    {
                        "type": "object",
                        "required": ["verdict", "concerns", "strengths"],
                        "properties": {
                            "verdict": {"type": "string", "enum": ["ship", "revise"]},
                            "concerns": {"type": "array", "items": {"type": "string"}},
                            "strengths": {"type": "array", "items": {"type": "string"}},
                        },
                    }
                ),
            },
        ),
    ]
