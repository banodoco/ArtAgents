# v10 legacy-data migration (`scripts/migrations/v10/`)

Migrates the pre-kernel legacy tree under `projects/` into the live kernel
database at `projects/.astrid/astrid.sqlite3` using only `AstridClient` and
the SDK/repositories — **no raw SQL writes, no importer tables**. The
legacy tree is never written; only the kernel DB and the managed media
tree (`projects/.astrid/media/sha256/…`) mutate.

## Scope

**Migrated**

- real projects (all non-`agentic-*` dirs under `projects/`), with
  `project.json` timestamps preserved in `settings.legacy`;
- timeline containers (`timelines/<ulid>/assembly.json` + `registry.json`),
  preserving the directory ULID as `timeline_ulid` (and `timeline_id`);
  `assembly.jsonl` is provenance recorded in `config._v10_migration`, never
  replayed as events;
- legacy timeline docs: `timeline.json` + `assets.json`, and
  `hype.timeline.json` + `hype.assets.json` pairs (derived ULID when no
  container ULID exists);
- media files referenced by the migrated timelines/runs, imported into the
  `managed_local` realm (copy-to-managed, SHA-256 dedupe; `external_local`
  references in place via `--realm`);
- completed generation/hype runs (`run.json` status `completed`/`success`)
  as one kernel run (`kind=tool_id`) + one child task, with the legacy
  `run.json` stuffed into `input` and one evidence item
  (`observation`, `data={legacy_path, status, argv}`). See **Fidelity
  paths** below.

**Skipped**

- `agentic-*` test projects (and their task-mode runs);
- `builtin.agent_probe` runs; failed / running / skipped run records;
- unreferenced media (cataloged in `inventory.json` only, never ingested —
  ~8.5 GB stays on disk);
- repo-root `runs/`, `sessions/`, identity/cli-usage, shots/references.

## Idempotency

Every mutation carries a stable receipt key
`v10-migrate:{family}:{stable-id}`; the kernel receipt gates make reruns
replay with zero new rows and a changed request under the same key fail as
`idempotency_mismatch`:

| family      | key                                  | stable id            |
|-------------|--------------------------------------|----------------------|
| project     | `v10-migrate:project:{slug}`         | directory slug       |
| media       | `v10-migrate:media:{slug}:{sha256}`  | byte SHA-256         |
| timeline    | `v10-migrate:timeline:{slug}:{ulid-or-path-hash}` | container ULID / config-path hash |
| run         | `v10-migrate:run:{slug}:{run_id}`    | legacy run_id        |

Claim/start/complete transitions use derived suffix keys
(`:claim`, `:start`, `:complete`, `:fail`). Cross-project run-id copies
collide globally; the second occurrence derives a deterministic ULID under
a `:id2` key.

## How to run

```bash
# 0. Read-only inventory (deterministic; SHA-256 computed for referenced
#    media only — the ~8.5 GB unreferenced tree is never read in full).
python3 scripts/migrations/v10/inventory.py \
    --root /Users/peteromalley/Documents/reigh-workspace/Astrid/projects

# 1. Read-only plan.
python3 scripts/migrations/v10/migrate_all.py --dry-run \
    --root /Users/peteromalley/Documents/reigh-workspace/Astrid/projects

# 2. Apply (guards + backup + phases + verify).
python3 scripts/migrations/v10/migrate_all.py --apply \
    --root /Users/peteromalley/Documents/reigh-workspace/Astrid/projects
```

`--apply` will not run unless the kernel DB has **zero project rows** and
refuses to clobber an existing backup. `--project SLUG` restricts all
phases to one project; `--realm external_local` opts out of the managed
copy.

Phases may also be run individually (`migrate_projects.py`, `migrate_media.py`,
`migrate_timelines.py`, `migrate_generations.py`, `verify.py`), each
dry-run by default. Inter-phase state:

- `inventory.json` — walk result (regenerate anytime; deterministic);
- `media_map.json` — referenced path → imported media id + prepared facts
  (written by `migrate_media`, consumed by timelines/generations/verify);
- `migration_report.json` — per-run fidelity path + task ids.

## How to resume

Every phase replays safely: re-run `migrate_all.py --apply` after a crash
(remove the `.bak` only after review; the DB-row guard prevents double
migration). A phase that failed mid-way resumes from its receipted
records: already-committed items replay under the same keys, remaining
items proceed. `migrate_media` additionally skips paths already present in
`media_map.json`.

## Fidelity paths (generations)

- **Fence path** (completed run with ≥1 importable artifact):
  `RunRepository.create` (one child) → system-actor `claim`/`start` →
  `complete` with the imported artifacts as `task_outputs` and
  `derived_from` relations to input media. Task ends `succeeded`; the run
  projection recomputes to `succeeded`.
- **Zero-child path** (completed run with no importable artifacts): the
  `complete` fence cannot be presented (it requires ≥1 materialized
  output), so the run is created with `children=[]` plus the same evidence;
  the run row stays `running`. **No raw SQL status writes ever.**
- If `complete` raises mid-way, the attempt is terminally `fail`ed with a
  `migration_complete_failed` error instead of being left running.

## Verify

`verify.py` (also the last phase of `--apply`) checks: counts vs
inventory; every referenced file has a media row with matching SHA-256 and
an on-disk location; every event stream's hash chain genesis→head;
no forbidden (legacy/importer) tables; legacy files still on disk.

## Stop-serve warning

`AstridClient.open` acquires the kernel DB's exclusive-owner lock (m4) and
fails closed when another owner holds it. **Stop `astrid serve` (and any
other owner) before `--apply`.** Do not run two migration processes
concurrently.
