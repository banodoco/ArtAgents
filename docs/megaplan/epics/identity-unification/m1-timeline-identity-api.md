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
REVIEW-FOUND TRAPS (mandatory): (a) Session.to_dict() uses asdict() (model.py:57-58) — a field rename silently changes the on-disk JSON key; the transition serializer must WRITE BOTH keys (timeline_id + timeline_ulid) for one release, not just read both. (b) Exclusion list for the grep-gate: reigh bridge parameter names (core/reigh/timeline_io.py:85-173), threads/record.py:41-42 record_run(timeline_id=) (carries a UUID — naming collision, not a consumer), timeline/cli.py export reads of event-record timeline_id (L1445,2172). (c) Export-path non-interference assertion in the conformance tests.

## Anti-scope
No project-resolution changes (M2); no run-id work (M3); no gateway auto-bind changes.
