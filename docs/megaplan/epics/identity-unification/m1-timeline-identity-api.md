# M1 — Timeline identity API: three names, one resolver

## Outcome
The three timeline identifiers (slug, ULID, event-stream UUID) have three distinct field names and one resolver; ambiguity of `timeline_id` (ULID in Session model.py:51, UUID in identity sidecar timeline/paths.py:204) is retired with compat readers. Handoff artifact: `docs/contracts/timeline-identifiers.md`.

## Scope
1. `TimelineIdentifiers(slug, ulid, uuid)` dataclass + single `resolve_timeline(project, any_identifier)` entry point; existing translators (timeline/paths.py:86,127,151) become internals.
2. Renames with one-release compat (read old key, write new, touch-on-read sidecar migration): Session `timeline_id` → `timeline_ulid`; identity-sidecar `timeline_id` → `timeline_uuid`.
3. Migrate the direct translator call sites: session/cli.py:362,496,607,814 (attach/list/takeover/status) and any others found.
4. Conformance: bidirectional round-trip (slug↔ulid↔uuid) on a created timeline; grep-gate forbidding new direct internal-translator calls; characterization tests proving attach/status output unchanged.
5. The handoff contract doc.

## Locked decisions
Compat-first (no big-bang sidecar rewrite); threads/ internals untouched; migration tested against COPIES of real sidecars from ~/Documents/reigh-workspace/astrid-projects (37+ projects, multiple historical versions).

## Anti-scope
No project-resolution changes (M2); no run-id work (M3); no gateway auto-bind changes.
