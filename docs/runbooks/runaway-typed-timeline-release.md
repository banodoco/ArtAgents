# Runaway typed-timeline release runbook

This runbook is the operator gate for the Runaway timing-v1 pack, the
typed-timeline mapper/renderer, and the local Reigh bridge. The canonical
store is `${ASTRID_PROJECTS_ROOT}/.astrid/astrid.sqlite3`; the original
`deliverables/` and `timeline/` files remain immutable migration inputs.

## Preconditions

1. Freeze the application wheel and record its SHA-256.
2. Stop all Astrid writers for the projects root. The bridge and migration
   must never run concurrently against the same owner lock.
3. Run `python3 -m astrid doctor --json --projects-root "$ROOT"` and require
   every check to be green.
4. Create and retain a validated backup:

   ```sh
   python3 -m astrid backup create --projects-root "$ROOT" --out "$BACKUP"
   ```

5. Record SHA-256 hashes for the source timing manifest and all existing
   `deliverables/` and `timeline/` files. Migration must not change them.

## Dry run and apply

Dry-run validation parses the complete manifest and audio timebase before it
opens a database. Any invalid frame order, duration, transition count, FPS,
or audio timebase is a hard stop.

```sh
python3 scripts/migrations/runaway_v1_migrate.py \
  --projects-root "$ROOT" \
  --manifest "$MANIFEST" \
  --audio-reactive "$AUDIO_REACTIVE" \
  --project-slug runaway-piano-colour-demo \
  --dry-run

python3 scripts/migrations/runaway_v1_migrate.py \
  --projects-root "$ROOT" \
  --manifest "$MANIFEST" \
  --audio-reactive "$AUDIO_REACTIVE" \
  --project-slug runaway-piano-colour-demo \
  --apply
```

Require 566 transitions, contiguous ordinals, one `runaway.created` event,
one command receipt, and one generic `measurement` evidence row whose
`data.subtype` is `runaway_timing_migrated`. Re-run the exact apply command;
it must return the same run and transition identities without adding rows.
Recompute the source-tree hashes and require an exact match.

The result also contains `migration_outcome` with schema
`astrid.migration_outcome.v1`. Hosts that call `migrate()` directly may pass
`outcome_callback` to receive exactly one success/failure observation. That
payload is deliberately limited to the fixed migration, mode, outcome, and
error-kind enums; it never includes a project, path, prompt, or exception
message, and a telemetry-sink failure cannot change the migration result.

## Editor bridge verification

Start only on loopback. Set a random bearer token when the caller supports
it; never expose this HTTP service on a LAN or public interface.

```sh
export ASTRID_BRIDGE_TOKEN="<random-secret>"
python3 -m astrid serve \
  --projects-root "$ROOT" \
  --host 127.0.0.1 \
  --port 9101 \
  --release-mode \
  --no-open-editor
```

Verify `/v1/health`, then traverse
`/v1/projects/runaway-piano-colour-demo/runaway-transitions?limit=256` until
`page.next_cursor` is null. Require `api_version=v1`, a stable `snapshot`,
566 unique ordered transitions, and the same `total_count` on every page.
The response must include `X-Astrid-Bridge-Version: v1`. Check that malformed,
cross-project, and modified cursors fail with `400 invalid_cursor`; missing or
bad bearer credentials fail with `401`; disallowed `Host`/`Origin` fail with
`403`; oversized request targets/bodies fail closed.

## Render acceptance

Map the admitted 566-row JSON artifact twice with both `runaway_colour` and
`runaway_text`. Require byte-identical canonical manifests and the release
goldens recorded in `tests/test_typed_timeline_ship_quality.py`. Render with
the real FFmpeg path, then use `ffprobe` to require 8085 video frames at 48
FPS, the declared canvas, a readable audio stream, and a zero decoder error
exit. Every path in the output manifest must be relative to the project-owned
output root; no absolute build-machine path may remain.

## Rollback

There is no destructive row-by-row down migration. If any post-apply gate
fails, stop every writer, preserve the failed store and logs for diagnosis,
and restore the pre-apply validated backup into an empty root:

```sh
python3 -m astrid backup restore "$BACKUP" --projects-root "$RESTORE_ROOT"
python3 -m astrid doctor --json --projects-root "$RESTORE_ROOT"
```

Swap the restored root into service only after doctor, source-hash, and bridge
health checks pass. Keep the failed database and the immutable source files;
never hand-edit receipts, events, evidence, or `runaway_transitions`.

## Release record

Attach the wheel hash, source hashes, backup location, dry-run/apply outputs,
idempotent replay counts, bridge pagination/security results, mapper goldens,
FFmpeg/ffprobe evidence, full pytest summary, operator, and UTC timestamps to
the release ticket. A missing item blocks promotion.
