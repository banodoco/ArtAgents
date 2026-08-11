# Astrid Timeline Observability (m7)

The `astrid timelines` CLI provides read-only commands for inspecting and
debugging event-sourced timelines. All commands work through backend
selection, so the same verbs inspect LocalFs and Supabase timelines
without changing the user's mental model.

## Dual-backend event model

Every Astrid timeline has a **canonical** event stream and optional
**derived** compatibility files:

| Layer | Role | Examples |
|-------|------|----------|
| Canonical | Authoritative event stream | `assembly.jsonl` (LocalFs), `public.timeline_events` (Supabase) |
| Derived | Compatibility projections | `assembly.json`, `display.json`, `assembly.checkpoint.json` |
| Identity | Backend selection + provenance | `assembly.identity.json` |

The canonical stream is the **source of truth**. Derived files are
repaired from the canonical stream on every Astrid-owned read path.
Observability verbs (m7) read through the canonical stream — they
never parse derived files directly.

## Backend selection

Commands route through `select_timeline_backend()` which reads the
identity sidecar's `backend` field:

- `"local_fs"` → `LocalFsBackend` (filesystem JSONL)
- `"supabase"` → `SupabaseBackend` (PostgreSQL table)

Timeline resolution chains three strategies:

1. **ULID-direct** — `is_ulid()` + `timeline_dir()`
2. **Event-stream UUID** — `_looks_like_uuid()` + `find_timeline_by_event_stream_id()`
3. **Slug** — `find_timeline_by_slug()`

Each strategy returns a `ResolvedTarget` with `timeline_id`,
`timeline_home`, `backend`, and `slug`. Not-found errors are
distinct per resolution strategy and never leak filesystem paths.

## Read-only guarantee

All m7 verbs are **strictly read-only**:

- ✅ Read events via `backend.read_events()`
- ✅ Verify hash chains via `backend.verify_chain()`
- ✅ Pure replay via `replay_projection()` (never writes files)
- ✅ Read ops log via `read_ops_log()` (optional surface)
- ❌ Do NOT append events
- ❌ Do NOT repair projections or write canonical files
- ❌ Do NOT create branches, perform undo, or change state

Recovery workflows (repair, compaction, undo) belong to m9.

## Operational failure logs

The optional `events_ops.jsonl` file in the timeline directory records
materialization failures from earlier milestones' append-then-materialize
pattern. Each line is a JSON object:

```json
{"ts": "2026-05-20T12:00:00Z", "event_id": "01...", "kind": "clip.added", "error": "disk full"}
```

- `read_ops_log(timeline_home)` returns `None` when the file is absent
  (graceful absence — never raises).
- `astrid timelines audit --include-ops` includes these entries in the
  audit report.
- The ops log is read-only for m7; m9 may add repair triggers.

## Cookbook recipes

### Audit before publish

```bash
# Verify chain integrity and projection parity
astrid timelines audit <slug> --include-ops

# Look for:
#   Hash chain: OK        ← no tampering
#   Head: OK              ← head metadata consistent
#   Projection: OK        ← assembly.json matches replay
#   Ops log: (no ops)     ← no materialization failures
```

If any check fails, diagnose the issue before publishing. A
projection mismatch means `assembly.json` is stale from a prior
append-then-materialize failure — regenerate it via `show_timeline()`
(which auto-repairs) before publishing.

### Preview a past cut

```bash
# See state after a specific event
astrid timelines preview <slug> --at <event-id>

# Write to a file (must be outside timeline home)
astrid timelines preview <slug> --at <event-id> --out /tmp/past-cut.json
```

The `--out` guard rejects paths inside the timeline home to prevent
accidental overwrites of canonical files.

### Who-edited rollups

```bash
# See which actors touched a timeline, grouped by event kind
astrid timelines who-edited <slug>
```

Output shows actor display names (or actor ids when display is absent),
total events per actor, and counts per event kind. Actor `via` fields,
session tokens, and raw auth metadata are never shown.

### Diagnosing stale-write failures

```bash
# Check for materialization failures from prior writes
astrid timelines audit <slug> --include-ops
```

If ops log entries appear (e.g., "simulated materialization failure"),
the canonical event stream advanced but the derived `assembly.json` or
`display.json` did not. The next `show_timeline()` or export will
auto-repair these files. For Supabase timelines, stale-write failures
may indicate a network partition or RLS misconfiguration.

## Migration note for pack authors

Managed timelines are always owned by a project and live under
`projects/<project-slug>/timelines/<timeline-ulid>/`. Standalone TimelineConfig
JSON remains a portable interchange format, but project-scoped executors must
consume it from within the selected project's tree (either a managed timeline
container or a derived file in one of that project's runs). Import standalone
work before treating it as managed project state.

If your pack writes timeline state directly (e.g., by mutating
`assembly.json` or `display.json` without going through the event log):

1. **Observability breaks**: `audit` will report projection parity
   failures because the canonical stream does not reflect the direct
   writes.
2. **Audit gaps**: Hash-chain verification only covers events in the
   canonical stream — direct file mutations are invisible to audit.
3. **Migration path**: Use `pack_write_gateway()` or the CRUD helpers
   (`create_timeline`, `rename_timeline`, clip/transition/effect/etc.
   edit functions) which append events through `EventLogBackend` and
   materialize derived files from the canonical stream.

Packs that write run-local artifacts (`hype.timeline.json`, pool build
outputs, arrangement files) do not need migration — only direct writes
to the timeline container directory (`timelines/<ulid>/`) are affected.

## Reference

- [Eventlog contract](eventlog/README.md) — canonical envelope, LocalFs
  layout, backend selection, and deferred Supabase target.
- [Projection module](projection.py) — `apply_event_to_assembly()`,
  `project_to_assembly()`, `replay_projection()`, and
  `regenerate_projection()`.
- [Observability module](observability.py) — `resolve_timeline_target()`
  and `read_ops_log()`.
- [CLI handlers](cli.py) — `cmd_history`, `cmd_diff`, `cmd_audit`,
  `cmd_preview`, `cmd_who_edited`.
