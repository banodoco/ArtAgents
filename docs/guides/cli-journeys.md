# CLI journeys — supported product and recovery commands

This guide walks the five product families (`projects`, `media`, `tasks`,
`runs`, `timelines`), the two nested mounts (`media references`, `timelines
shots`), and the local backup/diagnostic commands. Examples use `--json` where
the command returns an SDK envelope.

Normative references: `docs/astrid-first-sprint-plan-20260813.md` (Sprints 5–6),
`docs/contracts/astrid-sdk-v10.md` (envelope contract).

---

## Clean-machine preamble (zero configuration)

Astrid's product commands need no configuration file, credentials, or hosted
service. The only runtime prerequisite is a project to operate on, created
with the `projects` family below. Run commands from the repository root.

```bash
# 1. Confirm the CLI is reachable (prints the product census).
python3 -m astrid --help

# 2. Inspect a concrete family and verb without side effects.
python3 -m astrid projects --help
python3 -m astrid timelines save --help
```

Notes:

- **No server required for product commands.** The product families below run
  directly against the local store through one composed client. `serve` is
  only needed when an HTTP editor client is being used.
- **One verb = one SDK call.** Every handler parses arguments, makes exactly
  one SDK service call, and renders the result. There is no SQL or domain
  logic in the CLI layer.
- **`--json` is the stable machine surface.** In JSON mode the CLI prints
  exactly one envelope object (see below) to `stdout`; human mode prints one
  concise identity line instead.

---

## The five-key envelope

`--json` always emits exactly one JSON object with these five keys:

| Key               | Meaning                                                            |
| ----------------- | ------------------------------------------------------------------ |
| `ok`              | `true` on success, `false` on a typed SDK error                    |
| `data`            | the command's result payload (`null` on failure)                   |
| `error`           | a frozen error object (`{code, message, details}`) or `null`       |
| `receipt`         | the committed command receipt on mutations, `null` on reads/failure|
| `idempotency_key` | caller-supplied key, or the key the SDK generated before mutation  |

Success shape:

```json
{
  "ok": true,
  "data": {"id": "…", "slug": "demo"},
  "error": null,
  "receipt": {
    "receipt_id": "…",
    "command_kind": "…",
    "idempotency_key": "…",
    "request_hash": "…",
    "project_id": "…",
    "project_seq": [1, 1],
    "event_ids": ["…"],
    "result": {"…": "…"},
    "created_at": "…"
  },
  "idempotency_key": "…"
}
```

Failure shape:

```json
{
  "ok": false,
  "data": null,
  "error": {"code": "validation_error", "message": "…", "details": {"…": "…"}},
  "receipt": null,
  "idempotency_key": "…"
}
```

Exit codes are stable: `0` success (`ok=true`), `1` typed SDK error
(`ok=false`), `2` usage/parse error (argparse).

---

## 1. `projects` — create / list / show / update / select

```bash
# create — one client.projects.create call (slug immutable, idempotency key returned)
python3 -m astrid projects create demo --name "Demo" --json

# list — one client.projects.list call (slug ascending)
python3 -m astrid projects list --json

# show — one client.projects.show call by id or slug
python3 -m astrid projects show demo --json

# update — one client.projects.update call (name and/or settings delta)
python3 -m astrid projects update demo --name "Demo Renamed" --json

# select — persist a non-authoritative default-project preference
python3 -m astrid projects select demo --scope workspace --json
```

`select` is a file-side preference only (workspace scope by default, or
`--scope user`): it writes no receipt, performs no database mutation, and
carries no authority.

---

## 2. `media` — import / list / show / verify / relocate / relate

```bash
# import — accepts ONLY a file or directory; one exact-media result per file
python3 -m astrid media import ./shot.png --project demo --json
python3 -m astrid media import ./assets --project demo --json

# list — project-scoped (created_at, then id)
python3 -m astrid media list --project demo --json

# show — exact project-scoped media id
python3 -m astrid media show M_01ABC --project demo --json

# verify — fingerprint-verified; requires --realm
python3 -m astrid media verify M_01ABC --project demo --realm managed_local --json

# relocate — identity unchanged; requires --realm and --locator
python3 -m astrid media relocate M_01ABC --project demo \
  --realm external_local --locator "s3://bucket/shots/shot.png" --json

# relate — one typed relation edge; frozen five-kind --kind
python3 -m astrid media relate --project demo \
  --from M_01ABC --to M_02DEF --kind derived_from --json
```

Media relation `--kind` is restricted to the frozen five kinds:
`derived_from`, `variant_of`, `uses_as_input`, `mask_for`, `audio_for`.

---

## 3. `media references` — create / update / archive / associate / link / set-primary / list / show

The `references` family is a manifest-declared **nested mount**: it is
reachable only beneath `media` (for example, `astrid media references list`) and is
never a top-level command.

```bash
# create — one client.references.create call; frozen --kind, --name, --media
python3 -m astrid media references create --project demo \
  --kind character --name "Aria" --media M_01ABC --json

# update — name/description/metadata delta (kind and project stay immutable)
python3 -m astrid media references update R_01ABC --project demo \
  --name "Aria (S1)" --json

# archive — soft terminal mutation; every byte and association is preserved
python3 -m astrid media references archive R_01ABC --project demo --json

# associate — one exact media row with a frozen --role
python3 -m astrid media references associate R_01ABC --project demo \
  --media M_02DEF --role depicts --json

# link — one typed reference link; related_to is symmetric
python3 -m astrid media references link --project demo \
  --from R_01ABC --to R_02DEF --kind belongs_to --json

# set-primary — atomic primary-canonical replacement by association id
python3 -m astrid media references set-primary R_01ABC --project demo \
  --media-reference MR_01ABC --json

# list — active references by default; --include-archived is the explicit read
python3 -m astrid media references list --project demo --json
python3 -m astrid media references list --project demo --include-archived --json

# show — always includes archived references
python3 -m astrid media references show R_01ABC --project demo --json
```

Frozen vocabularies:

- `--kind` (create): `character`, `place`, `object`, `clothing`, `other`
- `--role` (associate): `canonical`, `used_as_input`, `depicts`, `inspired_by`
- `--kind` (link): `belongs_to`, `wears`, `located_in`, `associated_with`, `related_to`

These are the same tuples the repository enforces against the DDL `CHECK`
constraints — see `tests/v10/test_vocabulary_verification.py` for the
drift-detection proof.

---

## 4. `tasks` — create / list / show / cancel / retry / events

```bash
# create — admit one immutable task (spec is a JSON object)
python3 -m astrid tasks create --project demo \
  --capability gen.upscale --spec '{"size": 2}' --json

# list — project-scoped (created_at, then id)
python3 -m astrid tasks list --project demo --json

# show — one task's full immutable read model
python3 -m astrid tasks show T_01ABC --json

# cancel — one nonterminal task (no executor fence is exposed)
python3 -m astrid tasks cancel --project demo T_01ABC --json

# retry — one eligible failed/expired task
python3 -m astrid tasks retry --project demo T_01ABC --json

# events — the task's ordered core.task stream events
python3 -m astrid tasks events T_01ABC --json
```

`tasks retry` retries a single task. Batch retry over a run group is the
`runs retry-failed` surface (next section), not a `tasks` flag.

---

## 5. `runs` — list / show / cancel / retry-failed / events

```bash
# list — project-scoped (started_at, then id)
python3 -m astrid runs list --project demo --json

# show — run read model with derived child progress (optional --evidence)
python3 -m astrid runs show --project demo RUN_01ABC --json
python3 -m astrid runs show --project demo RUN_01ABC --evidence --json

# cancel — drive every eligible child to terminal cancelled
python3 -m astrid runs cancel --project demo RUN_01ABC --json

# retry-failed — batch retry (see semantics below)
python3 -m astrid runs retry-failed --project demo RUN_01ABC --json
python3 -m astrid runs retry-failed --project demo RUN_01ABC \
  --task T_01ABC --task T_02DEF --json

# events — the run's ordered core.run stream events
python3 -m astrid runs events --project demo RUN_01ABC --json
```

### Batch retry semantics (frozen)

`runs retry-failed` has exactly two modes, and the decision is frozen:

- **All-failed-children (default).** With no `--task` flag, the command
  retries every eligible failed/expired child of the run
  (`selected_task_ids=None`).
- **Explicit subset.** Repeatable `--task <id>` restricts the retry to an
  exact ordinal subset (`selected_task_ids=[T_01ABC, T_02DEF, …]`).

There is no `--run` flag on `tasks retry`; the batch retry surface is
`runs retry-failed`, and this is the frozen policy.

---

## 6. `timelines` — create / list / show / save / archive / history / diff

```bash
# create — one client.timelines.create call (slug immutable)
python3 -m astrid timelines create --project demo primary \
  --name "Primary" --json

# list — active timelines (slug ascending)
python3 -m astrid timelines list --project demo --json

# show — by UUID, ULID, or slug
python3 -m astrid timelines show --project demo primary --json

# save — whole-document CAS save (config and registry both required);
# create sets config_version 1, so a fresh timeline saves with --expected-version 1
python3 -m astrid timelines save --project demo primary \
  --config '{"width": 1920, "height": 1080}' \
  --registry '{"assets": {}}' --expected-version 1 --json

# archive — event-backed terminal mutation
python3 -m astrid timelines archive --project demo primary --json

# history — ordered lifecycle events (read)
python3 -m astrid timelines history --project demo primary --json

# diff — deterministic adjacent-version diffs (read)
python3 -m astrid timelines diff --project demo primary --json
```

---

## 7. `timelines shots` — list / create / add / remove / reorder

The `shots` family is a manifest-declared **nested mount**: it is reachable
only beneath `timelines` (for example, `astrid timelines shots list`) and is never a
top-level command.

```bash
# list — every shot in a project (sort_key, then id)
python3 -m astrid timelines shots list --project demo --json

# create — one empty shot
python3 -m astrid timelines shots create --project demo --name "Shot 1" --json

# add — insert one exact same-project media item at a validated position
python3 -m astrid timelines shots add S_01ABC --project demo \
  --media M_01ABC --position 0 --json

# remove — remove one item (its kernel media row and bytes are preserved)
python3 -m astrid timelines shots remove S_01ABC I_01ABC --project demo --json

# reorder — one whole-shot permutation; omissions/duplicates are rejected
python3 -m astrid timelines shots reorder S_01ABC --project demo \
  --items I_02DEF,I_01ABC --json
```

`reorder` accepts a repeatable/comma-separated `--items` list naming the
entire item-id permutation. A permutation that omits, duplicates, or adds an
item id is rejected by the service before any write.

---

## Exit codes

| Code | Meaning                                        |
| ---- | ---------------------------------------------- |
| `0`  | success (envelope `ok=true`)                   |
| `1`  | typed SDK error (envelope `ok=false`)          |
| `2`  | usage/parse error (argparse `SystemExit(2)`)   |

Scripts should parse the `--json` envelope for outcome details and treat the
process exit code as the coarse success/failure signal.

## 8. Diagnostics and failure recovery

Run the read-only doctor before changing a project:

```bash
python3 -m astrid doctor --json --projects-root ./projects
```

An unavailable local service or owner lock is reported as the typed
`unavailable` condition. Retry after the owning process exits; do not open a
second writer. A doctor result with `schema_versions: fail` indicates a
too-new migration or schema incompatibility. Keep the original project and
select a compatible checkout or restore a compatible backup.

Timeline saves are compare-and-swap operations. A stale expected version is
an HTTP `409 timeline_version_conflict` (or SDK `stale_version`) and changes
nothing. Load the current timeline, merge the local draft, and save again with
the returned version:

```bash
python3 -m astrid timelines show --project demo primary --json
python3 -m astrid timelines save --project demo primary \
  --config '{"width":1920,"height":1080}' \
  --registry '{"assets":{}}' --expected-version 1 --json
```

For missing or byte-mutated media, run verification again with the recorded
realm. The service rejects the read without rewriting the media; the public
envelope reports the typed `integrity_error` code for this failure.

```bash
python3 -m astrid media verify M_01ABC --project demo \
  --realm managed_local --json
```

Backups are staged and validated before publication. If a restore process is
interrupted, run the same restore command again or start the local bridge; the
startup path reads its durable journal before opening the writer and accepts
only the previous complete state or the complete restored state:

```bash
python3 -m astrid backup create --projects-root ./projects --out ./backup
python3 -m astrid backup restore ./backup --projects-root ./projects
python3 -m astrid backup restore ./backup --projects-root ./projects --force  # only when the target root already holds data
```
