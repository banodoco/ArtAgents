# Live timeline round-trip: Lunar Launch

## Environment and scope

- Date: 2026-08-23 (Europe/Berlin)
- Surface: live `python3 -m astrid` CLI usage only; no pytest, no programmatic tests, and no source inspection.
- Isolated root: `/tmp/astrid-live-timeline-RYPzxS` (fresh `mktemp -d` root; no existing project data intentionally targeted).
- The host filesystem was at 100% capacity during setup (`158MiB` reported available), which materially affected the first attempt.
- Goal: create project `Lunar Launch` / `lunar-launch`, default timeline `Rough Cut`, add `opening`, `approach`, `landing`, `celebration` in that order, then move `celebration` after `opening`, remove `approach`, and explain the change using history/diff.

## Chronological action log

1. Ran `ASTRID_PROJECTS_ROOT=<root> python3 -m astrid --help`. This was a good census: it exposed the five product families, operational families, and the nested `timelines shots` mount.
2. Read family help for `projects`, `timelines`, and `timelines shots`. `timelines save` clearly advertised whole-document CAS (`--expected-version`); `history` and `diff` were discoverable. `shots create` creates a named shot, while `shots add/remove/reorder` operate on media items inside a shot.
3. Ran `doctor --json`. On the first fresh `/tmp` root it reported `sqlite_quick_check failed: disk I/O error` and `foreign_key_check failed: disk I/O error`. The subsequent `projects show` produced an unstructured `OperationalError` (“disk I/O error”, recovery “retry the command”) twice. This was a serious environmental/app error-path interruption, not a bad user command.
4. Retried against the same isolated root after the transient disk pressure eased. `doctor --json` then passed all checks. The earlier project creation had actually committed despite the failed follow-up read; retrying `projects create lunar-launch` returned a typed `conflict`, which made that partial-success state understandable only after inspection.
5. `projects show lunar-launch --json` succeeded and confirmed `{slug: lunar-launch, name: Lunar Launch}`.
6. Created the default timeline with `timelines create rough-cut --project lunar-launch --name 'Rough Cut' --default --json`. It returned timeline id `6d43b554-8002-5eb7-9a54-1d2e63a0048c`, ULID `8rhjgkwps2wr34tp2jjz0gtg25`, and `config_version: 1`.
7. Created four named shots with `timelines shots create --project lunar-launch --name ... --json` in order: `opening`, `approach`, `landing`, `celebration`. `timelines shots list` returned the same creation/sort order.
8. Friction/discoverability moment: the CLI does not expose a command that says “add this shot to a timeline.” The nested shot operations concern media items inside a shot, not timeline ordering. Following the public surface, I used the timeline’s documented whole-document save and represented the timeline order in `config.shots` as the four returned shot IDs. This succeeded, but the schema/relationship is not explained by `--help`.
9. Saved version 1 → 2 with `config.shots = [opening, approach, landing, celebration]`, `registry = {}`, `--expected-version 1`. The save returned `config_version: 2`.
10. Applied the creative change with version 2 → 3, saving `config.shots = [opening, celebration, landing]` and `--expected-version 2`. This moved `celebration` immediately after `opening` and removed `approach` from the timeline document. The save returned `config_version: 3`.
11. Ran `timelines show`, `timelines history`, `timelines diff`, and a final `timelines shots list`.

## Final state evidence

Timeline `Rough Cut` is default and at `config_version: 3`. Its final ordered shot IDs resolve as:

1. `opening` — `194f5958-4d97-5acd-aa62-6bc30380effb`
2. `celebration` — `161dcd23-e0a4-5ef3-bc4e-27970a71e1bd`
3. `landing` — `c871dbb1-1eb3-55fb-964c-2bf38dc9ba05`

`approach` — `66815f92-d6d4-5272-a2f4-4336f85b7230` — is absent from the final timeline config, but remains as a project-level shot in `timelines shots list`. This is a useful distinction: “remove from timeline” did not delete the reusable shot record.

History returned three versions:

- v1 `timeline.created`, config `{}`
- v2 `timeline.saved`, config gained `shots` with `[opening, approach, landing, celebration]`
- v3 `timeline.saved`, config `shots` changed to `[opening, celebration, landing]`

Diff returned:

- v1 → v2: document `added: ["shots"]`
- v2 → v3: document `changed: ["shots"]`; no registry changes

The exact semantic explanation therefore requires joining the diff’s IDs to the shot-list output; `diff` itself reports field-level JSON changes, not human-readable shot names or move/remove operations.

## Friction and severity

- **P0 / blocking in this run (environment-sensitive):** initial `doctor` and reads surfaced SQLite disk I/O errors, and a committed create was followed by an unstructured error. The retry guidance was correct but the error did not say whether the write committed. A user can accidentally retry and encounter a conflict.
- **P1 / high UX ambiguity:** “timeline shots” sounds like a timeline collection, but `shots create` creates project-level shots and `shots add/remove/reorder` manipulate media items within a shot. There is no help text or example connecting named shots to a timeline’s `config`.
- **P1 / high interpretive burden:** `timelines save` accepts arbitrary JSON, so `config.shots` worked without validation or a documented contract. This is powerful but leaves agents guessing at the canonical representation.
- **P2 / moderate:** `history` and `diff` are easy to find and useful, but only expose versions and JSON keys/IDs. They do not say “celebration moved” or “approach removed,” so the agent must manually join IDs to names.
- **P2 / moderate:** JSON envelopes are consistent on success and typed conflict, but the earlier “unstructured - this is a bug” output was noisy and not JSON despite `--json`.

## What I wished Astrid had said

“A timeline is a whole document. Named shots live at project scope; put their IDs in `config.shots` to define timeline order. Use `timelines save` with the current `config_version` for an atomic reorder/removal. Removing an ID from `config.shots` detaches it from the timeline but does not delete the shot. `diff` reports IDs/fields; use `shots list` to resolve names.”

For storage failures: “The previous write may have committed; run the read-only show/list command before retrying the mutation.”

## Replay recommendations

- Keep the clean-root replay as a canonical agent-UX scenario, with an explicit expected final order and a check that `approach` remains reusable at project scope.
- Add a documented example to `timelines --help` (or a `timelines shots attach/detach` convenience surface) showing the relationship between project shots and timeline `config.shots`.
- Make `history/diff` optionally resolve shot IDs to names and label array changes as moves/additions/removals.
- Preserve `--expected-version` guidance in the normal create/edit flow and document the read-before-retry rule after operational failures.
