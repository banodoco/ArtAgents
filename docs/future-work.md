# Future Work

This document lists deferred pack-system work that is out of scope for the
current milestone chain (M0–M5). Each item is tracked for a future epic or
milestone and should not be treated as a bug or omission.

## Deferred Items

### 1. Remote Registry / Install System

A shared catalog for publishing, discovering, and installing packs from outside
the repository. Currently packs are discovered via local filesystem layout only
(`astrid/packs/` and user-configured content roots). A remote registry would
enable:

- Publishing packs to a shared index
- Versioned install/upgrade workflows
- Dependency resolution across remote packs
- Authenticated publish and trust verification

**Related epic:** Not yet filed.

### 2. Dependency Isolation Across Packs

Per-pack virtual environments and isolated dependency resolution to prevent
conflicts between packs. Currently all packs share the same Python environment.
A pack that requires `torch==2.0` cannot coexist with one that requires
`torch==2.4` unless the user manages environments externally.

**Related epic:** Not yet filed.

### 3. LLM-Powered Semantic Merge for Updates

Three-way merge of upstream pack updates with local forks and overrides. The
current update workflow (see `docs/update-workflow.md`) is manual: run
`dirty check`, review diffs, and manually reconcile. A semantic merge system
would use an LLM to:

- Detect upstream changes to forked capabilities
- Propose merge resolutions for conflicting edits
- Preserve local intent while incorporating upstream improvements

The `conflict` edit state and `upstream_version` provenance field exist in the
schema but are not yet computed or acted upon.

**Related epic:** Not yet filed.

### 4. Builtin-Training Placement Decisions

Several built-in executors (e.g., `builtin.train_lora`, `builtin.train_textual_inversion`)
reference training workflows. Their final placement — whether they remain in the
builtin pack, move to a dedicated training pack, or become adapter packs for
external training services — is deferred pending a related epic that will define
the training subsystem architecture.

**Related epic:** Training subsystem (pending).

### 5. Timeline/Thread Event-Sourcing Integration

The pack system currently operates independently of the timeline/thread
event-sourcing layer (see `docs/megaplan/epics/timeline-event-sourcing/`).
Future work should integrate pack capability execution with:

- Event-sourced execution history
- Thread-aware capability dispatch
- Timeline-scoped fork/override state
- Replay-able pack execution records

**Related epic:** Timeline/thread event-sourcing (in progress, see
`docs/megaplan/epics/timeline-event-sourcing/EPIC.md`).

## Tracking

These items are not tracked as GitHub issues. They are recorded here as deferred
scope acknowledged during M5 integration. When work begins on any of these,
create a milestone brief under `docs/megaplan/epics/` and remove the item from
this list.
