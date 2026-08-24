# Live UX wave: archive, pause, and return without remembered IDs

## Scope and method

- Black-box live CLI usage only; no source inspection, test execution, or
  programmatic SDK calls.
- Fresh `ASTRID_PROJECTS_ROOT` under `/tmp`.
- Phase A and Phase B used separate fresh shell contexts. Phase B retained no
  reference or timeline IDs; it started from the project slug, `projects show`,
  the project `plan.md`, and public help/list surfaces.
- Fixture: one 68-byte `tiny.png` imported into project `return-later`.

## Phase A — create, edit, then pause/archive

1. `projects create return-later --name "Return Later"` succeeded and created a
   project `plan.md` skeleton.
2. `media import tiny.png --project return-later` succeeded. The media row had
   one managed-local location, a stable content hash, and no duplicate rows.
3. `media references create --project return-later --kind character --name
   Seed --media <media-id>` succeeded. The reference had one primary canonical
   media association.
4. `timelines create primary --project return-later --name Primary --default`
   succeeded with config version 1.
5. `timelines save primary ... --expected-version 1` succeeded, changing the
   config to include `paused_note: "return later"` and advancing the version to
   2.
6. `media references archive <reference-id>` succeeded and explicitly reported
   `preserved: {events: 1, media_references: 1, reference_links: 0}`.
7. `timelines archive primary` succeeded and advanced the timeline to archive
   version 3.

After archiving, both active lists were empty. The inclusive reference list
contained `Seed`; `media list` still contained exactly one imported media row.

## Phase B — return with no remembered IDs

### What was discoverable

- `projects show return-later --json` succeeded and showed the project’s
  `settings.default_timeline_id`, even though the timeline was archived.
- `plan.md` remained the untouched empty skeleton. It did not tell a returning
  agent that `Seed` or `primary` existed, had been paused, or had been archived.
- `media references list --project return-later` returned `[]` by default.
- `media references list --project return-later --include-archived` found the
  archived `Seed` record. Its name/kind/timestamps were visible, but the list
  required extracting the UUID before `references show` could reveal the media
  association and full metadata.
- `media list --project return-later` found the original media row and its
  managed-local location, so the bytes were preserved and not duplicated.
- `timelines list --project return-later` returned `[]`; timeline help describes
  it as listing active timelines and provides no `--include-archived` option.
- The project’s `default_timeline_id` was the practical discovery path. Showing
  that UUID returned `primary` with the saved config, including
  `paused_note: "return later"`.
- `timelines history <id>` preserved the full lifecycle: created v1, saved v2,
  and archived v3. The archive event’s history payload has `config: null`, but
  the normal timeline `show` read model still returns the last saved config.

### Recovery decision

Recovery was deliberately read-only. No `unarchive` command is present in
`timelines --help` or `media references --help`; probing either spelling is a
usage error. No supported restore/recreate operation was invented, and no
second `Seed` reference or second media import was created. The archived
reference and timeline remain intact and inspectable, with original identity
and media association preserved.

## Severity-ranked UX critique

### P1 — archived timelines are not discoverable from the normal list

The returning agent sees an empty timeline list and receives no inclusive-read
switch in help. The only reliable route in this run was an incidental-looking
`default_timeline_id` left in project settings. If that pointer were absent or
stale, the archived timeline’s slug/name would be effectively hidden. Add an
explicit archived-inclusive timeline list (parallel to references), and expose
archive status in the project show/plan orientation output.

### P1 — no supported restore/unarchive path or recovery guidance

Both help surfaces expose archive but no undo/restore command, and neither
explains whether archive is terminal, reversible, or recoverable by a future
agent. This forces a risky choice between stopping truthfully and recreating a
new identity. Add a documented, idempotent `unarchive`/restore operation, or
state clearly that archive is terminal and provide a canonical export/recreate
procedure that preserves identity and avoids duplicate media.

### P1 — the per-project plan does not preserve return context

The generated `plan.md` remains empty despite creating, editing, and archiving
work. A returner starting with the recommended show/plan orientation gets no
human-readable record of the paused timeline, reference, or recovery path.
Provide an opt-in or automatic project activity summary, or at minimum update
the plan with current focus/open threads when project state changes.

### P2 — reference discovery needs an explicit flag and then an ID hop

The reference experience is better than timelines: help explicitly says
`--include-archived`, and `show` includes archived records. Still, the default
list hides the item and `show Seed` does not resolve by name; the agent must
list inclusively, extract a UUID, then show by ID. Support stable project-local
name/slug lookup with an ambiguity-safe response, or make the inclusive list
the natural recovery surface when the project is paused.

### P2 — default pointer semantics are surprising after archive

`projects show` continued to expose `settings.default_timeline_id` after that
timeline was archived, while `timelines list` returned no active timeline. This
is useful for recovery but confusing: the project appears to point at a timeline
that normal listing says does not exist. Mark the pointer as archived in the
project read model and explain whether a new default should be selected.

### P3 — archive history and read model disagree on retained config shape

The archived timeline’s normal `show` retained the last config, but the archive
history row represented the terminal version with `config: null` and
`registry: null`. That is internally understandable, yet an agent comparing
history to current state could infer that the config was lost. Make the archive
event explicitly reference the prior version or retain a clearly labeled
snapshot.

### P3 — help is accurate but not task-oriented

The census and family help are concise and correctly list the commands, but
they do not include a “return to archived work” recipe. A short recovery
example showing inclusive reference listing, archived timeline discovery, and
the absence/presence of restore would substantially reduce agent hesitation.

## Verdict

**Data preservation: PASS.** The imported bytes, content hash, reference
association, timeline identity, saved config, and lifecycle history survived
archiving. **Duplicate safety: PASS for a cautious agent.** The live run made
no duplicate media or reference. **Return ergonomics: CONDITIONAL/P1.** A
careful agent can recover read-only state, but archived timeline discovery is
fragile and there is no supported reversible action or clear recovery guidance.
The workflow is not safe for autonomous “resume editing” until archived-list
and restore semantics are made explicit.

