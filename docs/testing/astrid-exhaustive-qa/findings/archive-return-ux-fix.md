# Archive/return UX root fix

## Live failure reproduced

Using a fresh disposable `ASTRID_PROJECTS_ROOT`, the public gateway reproduced
the wave exactly:

- `timelines list --project return-later` hid the archived timeline;
- `timelines list --include-archived` was rejected by argparse;
- `timelines unarchive` and `media references unarchive` did not exist;
- the only timeline recovery clue was the UUID in
  `projects show ... settings.default_timeline_id`.

No source or tests were used to find that failure. The initial evidence is in
`waves/live-archive-return-1.md`.

## Product changes

### Timelines

- Added public `timelines list --include-archived`. Inclusive rows carry an
  explicit `archived_at`; the normal active-list bridge row remains unchanged.
- Added public `timelines unarchive <uuid|ulid|slug>` and SDK/repository support.
- Recovery appends `timeline.unarchived`; current archive state is the latest
  archive/unarchive transition, so a recovered timeline can be saved or
  archived again without rewriting history.
- The first recovery returns `status: active`, `changed: true`, the stable
  timeline id, timestamp, and new config version with a receipt. Repeating it
  returns `changed: false`, the same version, no event, and no receipt.
- History now includes the unarchive transition.

### References

- Added public `media references unarchive <id|exact-name>` and SDK/repository
  support.
- Exact id wins. Exact project-local name is accepted only for recovery; if it
  matches more than one reference, the command fails closed with candidate ids
  and a concrete inclusive-list retry recipe.
- The first recovery clears only `archived_at`, refreshes `updated_at`, appends
  `reference.unarchived`, and reports preserved media/reference/link/event
  counts. Identity and all associations remain unchanged.
- Repeating recovery returns `status: active`, `changed: false`, no event, and
  no receipt.

Both new event and command kinds are declared in their owning schema-pack
manifests. The root gateway remains exactly eight families; recovery is a verb
within the existing timeline and nested reference families.

## Deliberate boundary

`projects show` was not made pack-aware. Enriching the core project service
with a timeline-pack read would cross Astrid's core/pack ownership boundary and
turn this focused fix into a composition redesign. Inclusive timeline listing
is now the canonical public recovery read. `plan.md` is not auto-edited; that
was explicitly outside this fix.

## Fresh two-shell live proof

Disposable root:
`/tmp/astrid-archive-return-proof.qzUHOZ/projects`

Phase A used only public CLI commands to create project `return-later`, import
one PNG, create reference `Seed`, create/save default timeline `primary`, then
archive the reference and timeline. The timeline reached version 3 after
create/save/archive.

Phase B was a new shell with only the root and project slug:

```text
projects show return-later
timelines list --project return-later
timelines list --project return-later --include-archived
media references list --project return-later --include-archived
timelines unarchive primary --project return-later
timelines unarchive primary --project return-later
media references unarchive Seed --project return-later
media references unarchive Seed --project return-later
timelines show/save/list/history ...
media references list/show ...
media list ...
```

Observed evidence:

- the normal timeline list was empty, while the inclusive list exposed
  `primary`, its original id, `is_default: true`, and `archived_at`;
- the inclusive reference list exposed `Seed` and its original id;
- first timeline recovery was `changed: true`, version 4; repeat was
  `changed: false`, still version 4;
- first reference recovery was `changed: true`; repeat was `changed: false`;
- a resumed timeline save succeeded at version 5 and retained the original id;
- history was exactly create v1, save v2, archive v3, unarchive v4, save v5;
- final active lists contained exactly one timeline and one reference;
- reference show retained the original reference id, association id, and media
  id; media list contained exactly one media row with the original hash.

Verdict: **PASS** for discover, unarchive twice, resume editing, preserved
identity/config/media, and duplicate safety.

A second fresh public-CLI root created two archived references named `Seed`.
`media references unarchive Seed --project demo --json` failed closed with
exit 1, `validation_error`, both candidate ids, and the exact inclusive-list
recovery command; neither reference was mutated.

## Regression verification

- Added `tests/v10/test_archive_return_recovery.py` for inclusive discovery,
  repeat no-op semantics, resume editing, identity/media preservation, and
  ambiguity-safe reference recovery.
- Updated the two CLI parser contract suites for the new verbs and
  `--include-archived` call-through.
- Focused result: `223 passed`.
- Ruff on every changed implementation/regression file: clean.
- A broader related run was `312 passed, 1 failed`; the failure is the existing
  unrelated `runaway` schema-pack discovery mismatch in
  `test_standard_composition_has_no_discovery_beyond_in_tree_manifests`.
- Authority lint still reports the campaign's pre-existing writer-construction
  findings in `astrid/core/project/kernel_admission.py` and
  `astrid/sdk/invocation.py`; neither is part of this archive/return change.
