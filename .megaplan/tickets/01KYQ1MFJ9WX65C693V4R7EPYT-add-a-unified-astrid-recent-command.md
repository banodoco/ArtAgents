---
id: 01KYQ1MFJ9WX65C693V4R7EPYT
title: Add a unified astrid recent command
status: open
source: human
tags:
- cli
- ux
- projects
- observability
codebase_id: null
created_at: '2026-07-29T13:39:43.305765+00:00'
last_edited_at: '2026-07-29T13:39:43.305765+00:00'
epics: []
---

## Problem

Astrid has no single command that surfaces the newest project activity. Discovery is fragmented across `astrid projects ls`, `astrid status`, `astrid runs ls`, timelines, experiments, and generated media. This makes it hard for an agent or human to answer: what was made most recently in the selected project?

## Desired UX

Add a project-aware `astrid recent` command that presents a compact, newest-first activity feed spanning runs, generated image/video artifacts, timelines, and experiments.

- Require an attached session project or an explicit `--project`; never silently use the configured default.
- Clearly announce `project: <slug> (attached session)` or `project: <slug> (explicit --project)`.
- If no project is selected, exit with the standard actionable project chooser and exact `astrid projects select <slug>` / create commands.
- Show useful type, status, description/title, timestamp, origin, and artifact paths without overwhelming output.
- Include exact follow-up commands for inspecting the surfaced items.
- Support deterministic machine output with `--json`, plus `--limit` for concise human output.

## Acceptance criteria

1. `astrid recent [--project SLUG] [--limit N] [--json]` is documented and discoverable from help/status guidance.
2. Runs, timelines, experiments, and generated image/video artifacts are merged deterministically newest-first within one project.
3. Attached-session and explicit-project provenance is visible; a configured default is suggestion-only and never auto-selected.
4. Unbound invocation exits non-zero with the same ergonomic project-selection guidance used by other project-required actions.
5. Tests cover attached selection, explicit selection, unbound/default-not-selected behavior, ordering, media association, limits, and JSON output.

