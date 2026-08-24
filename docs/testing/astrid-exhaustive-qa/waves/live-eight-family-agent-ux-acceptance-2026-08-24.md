# Live eight-family agent UX acceptance — 2026-08-24

## Verdict

**PASS with one runtime/environment blocker and two minor UX questions.** This was a fresh disposable run rooted at `/private/tmp/astrid-live-acceptance.nPWj5g`; no user project was touched and no product code was edited. The restored copy was `/private/tmp/astrid-live-restored.99815`, with backup `/private/tmp/astrid-live-backup.99815`.

The CLI census and all eight families were reachable. Projects, timelines, media, tasks, runs, serve, doctor, and backup all admitted/read/mutated state through the public surface. The nested `media references` and `timelines shots` mounts also passed lifecycle checks.

## Exercised paths and evidence

- `doctor --json` on the empty root returned `state: uninitialized`, `ok: true`, exit 0. After data creation and after restore it returned `state: ready`, with SQLite quick-check, FK, schema, and media checks all `ok`.
- `projects`: create `demo`, list/show, update name to `Demo Renamed`, select/current, and missing-project recovery. Missing project returned typed `not_found` with a list-and-retry recovery message.
- `timelines`: create default `primary`, list/show/history/diff, CAS save v1→v2, stale save at expected version 1 (typed `stale_version`, no write), archive, inclusive list, unarchive, and idempotent second unarchive (`changed:false`).
- `media`: imported one managed-local and one external-local text file; list/show/verify; relocated external locator to a future path, observed typed integrity failure, restored locator; managed relocate by matching source; created a `derived_from` relation. Invalid relation kind was rejected at CLI parse with exit 2.
- `media references`: created `Alice` and `Studio`, listed/showed, renamed/metadata-updated `Alice` to `Alice Prime`, associated a second canonical media, linked `related_to`, changed primary, archived, inclusive-listed, unarchived by name, repeated unarchive (`changed:false`), and verified associations/links were preserved.
- `timelines shots`: created `Opening Shot`, listed/showed, added two media items (including position/source-frame/metadata), rejected incomplete reorder with a clear complete-permutation recovery, successfully reordered, removed an item while preserving media, and observed repeat-remove `not_found`.
- `tasks`: created standalone queued task `f78b5a10-8e70-52f1-9333-4246bc08f89b`, listed/showed/events, cancelled it, verified terminal state, and confirmed repeat cancel/retry fail closed with `terminal_state`.
- `runs`: `timelines visualize` admitted runs `81fae5c792edbec0051e101352` and `4aeac0d370bdc577a8fa9191b5`; `runs list/show --evidence/events` exposed child failure details and progress. `runs retry-failed` returned a generic `validation_error` because the failed child had no retry capacity; terminal cancel was rejected.
- `serve`: started on loopback port 62053 with `--no-open-editor`; `GET /health`, `/routes`, `/projects`, project timelines, and timeline read all returned 200/readable JSON. A concurrent CLI read failed closed with typed `unavailable/store_owned`, correctly directing the agent to HTTP routes or clean shutdown. Ctrl-C released ownership cleanly.
- `backup`: created a self-contained backup with one managed file and one external snapshot; restored to a new root; verified doctor, projects, two media rows, timeline, external locator rebasing, and schema/FK integrity. Restore over populated data failed safely without `--force`; `--force` then succeeded and doctor remained ready.
- SDK smoke: `astrid.discover(include_installed=False)` found 86 capabilities. `AstridClient.open(projects_root=...)` read restored projects/timelines/media through typed services; `DomainResult.data` contained the expected rows.

## Blocker / questionable UX

1. **Visualization success path is blocked in this checkout environment.** The first visualization failed with a useful canonical-config error (`top-level tracks and clips arrays`); after saving `{"tracks":[],"clips":[]}`, the next live invocation failed with `TimelineEventSchemaError`: `banodoco_timeline_schema is required for timeline validation — pip install -e packages/timeline-schema/python`. The failure is admitted as a run and visible in `runs show`, but no successful visualization artifact could be produced. Exact recovery is to install the schema package, then retry visualization with a canonical timeline.
2. `runs events <failed-run>` returned only the run-created event while `runs show --evidence` contained the child failure/attempt details. This is internally consistent if the command is intentionally the run stream, but an agent may expect terminal run events too; consider clarifying the help text or including a link/summary to child events.
3. `runs retry-failed` on a terminal failed run returned only `validation_error` / `the request failed validation`, while the task had no remaining attempts. A typed `retry_ineligible` with reason and recovery would be easier for an agent to act on.

## Reproduction commands

All commands used the public gateway, with `ASTRID_PROJECTS_ROOT=/private/tmp/astrid-live-acceptance.nPWj5g` unless a restored-root check is shown:

```sh
python3 -m astrid --help
python3 -m astrid doctor --json
python3 -m astrid projects create demo --name 'Demo Project' --json
python3 -m astrid timelines create primary --project demo --name 'Primary Timeline' --default --config '{"duration":2}' --registry '{}' --json
python3 -m astrid media import <temporary-file> --project demo --json
python3 -m astrid tasks create --project demo --capability acceptance.noop --spec '{"message":"hello"}' --max-attempts 2 --json
python3 -m astrid timelines visualize primary --project demo --format md --json
python3 -m astrid serve --host 127.0.0.1 --port 0 --projects-root /private/tmp/astrid-live-acceptance.nPWj5g --no-open-editor
python3 -m astrid backup create --projects-root /private/tmp/astrid-live-acceptance.nPWj5g --out /private/tmp/astrid-live-backup.99815
python3 -m astrid backup restore /private/tmp/astrid-live-backup.99815 --projects-root /private/tmp/astrid-live-restored.99815
ASTRID_PROJECTS_ROOT=/private/tmp/astrid-live-restored.99815 python3 -m astrid doctor --json
```

