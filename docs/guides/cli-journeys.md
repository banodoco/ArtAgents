# CLI journeys — runtime-backed product commands

This guide walks the five product families (`projects`, `media`, `tasks`,
`runs`, `timelines`), the two nested mounts (`media references`, `timelines
shots`), and the runtime health/backup routes. Examples use `--json` where the
command returns an SDK envelope. The Banodoco workspace runtime is the sole
authority for all durable state; the Astrid checkout has no live project store.

Normative references: `docs/astrid-first-sprint-plan-20260813.md` (Sprints 5–6),
`docs/contracts/platform-contract.md` (envelope contract).

---

## Runtime preamble

Configure the installed local workspace runtime before issuing product
commands. The first product command starts or reconnects it through the
explicit launcher boundary:

```bash
export BANODOCO_LOCAL_SOURCE_MANIFEST=/path/to/astrid-source-profile.json
python3 -m astrid projects list --json
```

The SDK's explicit `AstridClient.open(...)` accepts a loopback endpoint and
credential directly; it does not discover or infer either value. Run commands
from any directory; project, object, receipt, and event state remains in the
runtime. `astrid doctor` is read-only and does not trigger first-run bootstrap.

```bash
# 1. Confirm the CLI is reachable (prints the product census).
python3 -m astrid --help

# 2. Run the read-only first-run diagnostic (state=uninitialized is expected
#    before the first project exists).
python3 -m astrid doctor --json

# 3. Inspect a concrete family and verb without side effects.
python3 -m astrid projects --help
python3 -m astrid timelines save --help
```

Notes:

- **Neutral runtime handoff for product commands.** Product families below
  cross the generated workspace client, and the configured neutral launcher
  starts or reconnects it on first use.
- **One verb = one SDK call.** Every handler parses arguments, makes exactly
  one SDK service call, and renders the result. There is no SQL or domain
  logic in the CLI layer.
- **`--json` is the stable product machine surface.** Product and nested-mount
  commands print exactly one five-key envelope (see below) to `stdout`; the
  read-only `doctor --json` diagnostic has its documented check/state shape;
  human operational commands print concise summaries instead.

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

## 1. `projects` — create / list / show / update / select / current

```bash
# create — one client.projects.create call (slug immutable, idempotency key returned)
python3 -m astrid projects create demo --name "Demo" --json

# list — one client.projects.list call (slug ascending)
python3 -m astrid projects list --json

# show — one client.projects.show call by id or slug
python3 -m astrid projects show demo --json

# update — one client.projects.update call (name and/or settings delta)
python3 -m astrid projects update demo --name "Demo Renamed" --json

# select — persist a workspace/user project-routing preference
python3 -m astrid projects select demo --scope workspace --json

# current — inspect the selected project and supplying preference scope
python3 -m astrid projects current --json
```

Pass `--project` explicitly to ordinary project-scoped commands. `runs open`
can instead consume the runtime `select/current` preference;
`ASTRID_PROJECTS_ROOT` routing is historical and is not Stage1 authority.

---

## 2. `media` — import / list / show / verify / relate

```bash
# import — accepts ONLY a file or directory; one exact-media result per file
python3 -m astrid media import ./shot.png --project demo --json
python3 -m astrid media import ./assets --project demo --json

Video/audio containers are strictly checked with `ffprobe` before admission.
An undecodable `.mp4`/`.wav` (including a Git-LFS pointer) returns a typed
`validation_error` with no media row, event, receipt, or managed bytes; install
the ffmpeg package when `ffprobe` is unavailable and retry. Generic files and
images retain their extension-based import classification.

# list — project-scoped (created_at, then id)
python3 -m astrid media list --project demo --json

# show — exact project-scoped media id
python3 -m astrid media show M_01ABC --project demo --json

# verify — fingerprint-verified; requires --realm (all matching locations)
python3 -m astrid media verify M_01ABC --project demo --realm managed_local --json
# verify one runtime object precisely
python3 -m astrid media verify M_01ABC --project demo --realm managed_local --json

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
python3 -m astrid tasks show --project demo T_01ABC --json

# cancel — one nonterminal task (no executor fence is exposed)
python3 -m astrid tasks cancel --project demo T_01ABC --json

# retry — one eligible failed/expired task
python3 -m astrid tasks retry --project demo T_01ABC --json

# events — the task's ordered core.task stream events
python3 -m astrid tasks events --project demo T_01ABC --json
```

`tasks retry` retries a single task. Batch retry over a run group is the
`runs retry` surface (next section), not a `tasks` flag.

### VibeComfy: inspect → typed edit → validate → run

VibeComfy graph work stays inside the `tasks` family. The original ComfyUI UI
JSON remains authoritative; `vibecomfy.inspect` produces a readable projection,
and `vibecomfy.edit` applies typed deltas to a fresh output workflow. Neither is
a top-level CLI family, and the projection is never accepted as mutation input.

First import the UI workflow and this operations document with `media import`.
Record each returned managed-object SHA-256 digest:

```json
{
  "schema_version": 1,
  "expected_revision": 0,
  "ops": [
    {"op": "edit_node", "target": "ksampler", "field": "steps", "value": 24},
    {"op": "set_node_mode", "target": "preview", "mode": "bypassed"}
  ]
}
```

```bash
python3 -m astrid media import ./workflow.ui.json --project demo --json
python3 -m astrid media import ./operations.json --project demo --json

# Inspect. Substitute the exact digest returned for workflow.ui.json.
python3 -m astrid tasks create --project demo \
  --capability vibecomfy.inspect \
  --spec '{"inputs":{},"input_digests":[{"name":"workflow","digest":"sha256:<WORKFLOW_SHA256>"}]}' \
  --input-manifest '["sha256:<WORKFLOW_SHA256>"]' --json
python3 -m astrid tasks show --project demo <INSPECT_TASK_ID> --json

# Apply all leaf operations as one atomic VibeComfy edit_batch.
python3 -m astrid tasks create --project demo \
  --capability vibecomfy.edit \
  --spec '{"inputs":{},"input_digests":[{"name":"workflow","digest":"sha256:<WORKFLOW_SHA256>"},{"name":"operations","digest":"sha256:<OPERATIONS_SHA256>"}]}' \
  --input-manifest '["sha256:<WORKFLOW_SHA256>","sha256:<OPERATIONS_SHA256>"]' --json
python3 -m astrid tasks show --project demo <EDIT_TASK_ID> --json

# Copy the edit task's workflow output digest; validate that exact object.
python3 -m astrid tasks create --project demo \
  --capability vibecomfy.validate \
  --spec '{"inputs":{},"input_digests":[{"name":"workflow","digest":"sha256:<EDITED_WORKFLOW_SHA256>"}]}' \
  --input-manifest '["sha256:<EDITED_WORKFLOW_SHA256>"]' --json
python3 -m astrid tasks show --project demo <VALIDATE_TASK_ID> --json

# After validation succeeds, run the same immutable workflow object.
python3 -m astrid tasks create --project demo \
  --capability vibecomfy.run \
  --spec '{"inputs":{},"input_digests":[{"name":"workflow","digest":"sha256:<EDITED_WORKFLOW_SHA256>"}]}' \
  --input-manifest '["sha256:<EDITED_WORKFLOW_SHA256>"]' --json
python3 -m astrid tasks show --project demo <RUN_TASK_ID> --json
```

The inspect task emits `workflow-ir.py` and `inspection.json`. The edit task
emits `workflow.ui.json`, a fresh `workflow-ir.py`, and `edit-report.json` with
the input/output hashes, accepted revision, delta id, canonical typed delta,
and diagnostics. Accepted leaf operation names are `edit_node`, `add_node`,
`remove_node`, `upsert_link`, `remove_link`, and `set_node_mode`; the executor
supplies the outer atomic `edit_batch`. The task input manifest is the runtime's
authorization fence, so every digest in `spec.input_digests` must also appear
in `--input-manifest`.

---

## 5. `runs` — list / show / cancel / retry / events / open

```bash
# list — project-scoped (started_at, then id)
python3 -m astrid runs list --project demo --json

# show — run read model with derived child progress (optional --evidence)
python3 -m astrid runs show --project demo RUN_01ABC --json
python3 -m astrid runs show --project demo RUN_01ABC --evidence --json

# With --evidence, successful child completion outputs are also returned:
# media ids, roles, labels, hashes, sizes, and safe relative paths for the
# render and provenance artifacts.

# cancel — drive every queued, blocked, or running child to terminal cancelled
python3 -m astrid runs cancel --project demo RUN_01ABC --json

# retry — batch retry (see semantics below)
python3 -m astrid runs retry --project demo RUN_01ABC --json
python3 -m astrid runs retry --project demo RUN_01ABC \
  --task T_01ABC --task T_02DEF --json

# events — the run's ordered core.run stream events
python3 -m astrid runs events --project demo RUN_01ABC --json

# open — latest successful render in the selected current project
python3 -m astrid runs open

# open one exact render; --project overrides the selected current project
python3 -m astrid runs open RUN_01ABC
python3 -m astrid runs open --project demo
```

`runs open` uses runtime run/task records and managed object bytes only. It
never scans checkout files or sorts filenames by modification time. "Latest"
means the newest successfully settled `rendering.render` run; Astrid does not
yet expose a separate editor-approved/current-deliverable promotion pointer.
Downloaded bytes are checked against their runtime SHA-256 and size before the
video is opened from a content-addressed local cache. Opening is currently
supported on macOS.

### Batch retry semantics (frozen)

`runs retry` has exactly two modes, and the decision is frozen:

- **All-failed-children (default).** With no `--task` flag, the command
  retries every eligible failed/expired child of the run
  (`selected_task_ids=None`).
- **Explicit subset.** Repeatable `--task <id>` restricts the retry to an
  exact ordinal subset (`selected_task_ids=[T_01ABC, T_02DEF, …]`).

There is no `--run` flag on `tasks retry`; the batch retry surface is
`runs retry`, and this is the frozen policy.

---

## 6. `timelines` — create / list / show / save / archive / recover / history / diff / visualize / render

```bash
# create — one client.timelines.create call (slug immutable)
python3 -m astrid timelines create --project demo primary \
  --name "Primary" --json

# list — active timelines (slug ascending)
python3 -m astrid timelines list --project demo --json

# show — by UUID, ULID, or slug
python3 -m astrid timelines show --project demo primary --json

# save — whole-document compare-and-swap (config and registry both required);
# create sets config_version 1, so a fresh timeline saves with --expected-version 1
python3 -m astrid timelines save --project demo primary \
  --config '{"tracks":[{"id":"main","kind":"visual","label":"Main"}],"clips":[],"output":{"resolution":"320x180","fps":30,"file":"primary.mp4"}}' \
  --registry '{"assets": {}}' --expected-version 1 --json

# archive — event-backed terminal mutation
python3 -m astrid timelines archive --project demo primary --json

# history — ordered lifecycle events (read)
python3 -m astrid timelines history --project demo primary --json

# diff — deterministic adjacent-version diffs (read)
python3 -m astrid timelines diff --project demo primary --json

# visualize — deterministic run-owned evidence (filmstrip off is the safe
# first pass when no verified rendered-video source is available)
python3 -m astrid timelines visualize primary --project demo \
  --format md --filmstrip off --json

# render — version-pinned canonical render; waits for completion by default
python3 -m astrid timelines render primary --project demo \
  --expected-version 1 --backend rendering.remotion \
  --output-name primary.mp4 --json

# queue only — explicit admission semantics, returned state is "admitted"
python3 -m astrid timelines render primary --project demo --detach --json
```

---

## 7. `timelines shots` — list / create / show / add / remove / reorder

The `shots` family is a manifest-declared **nested mount**: it is reachable
only beneath `timelines` (for example, `astrid timelines shots list`) and is never a
top-level command.

```bash
# list — every shot in a project (sort_key, then id)
python3 -m astrid timelines shots list --project demo --json

# show — inspect one shot's ordered item/media mapping from a fresh read
python3 -m astrid timelines shots show S_01ABC --project demo --json

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

Shots are project-level reusable records. The `timelines shots` nesting is a
CLI mount for discoverability, not an implicit timeline association, and shot
commands therefore do not take a timeline id. If a timeline document chooses
to reference a shot, that relationship lives in the document's own config;
removing a shot id from a document does not delete the reusable shot record.
`show` returns ordered item ids, media ids, positions, and best-effort media
name/path details so a fresh agent can inspect state without retaining a
mutation response.

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

Run the runtime health check before changing a project:

```bash
python3 -m astrid doctor --json
```

If it reports `state: "unavailable"`, start the runtime with
`banodoco-local up --profile astrid` and retry. Do not create a local database,
tail local event files, or edit runtime state by hand. An unexpected command
failure is returned as a typed error; preserve the idempotency key and retry
only when the error's recovery guidance permits it.

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

For missing or byte-mutated media, run runtime verification again. The service
rejects the read without rewriting the object; the public envelope reports the
typed `integrity_error` code for this failure.

```bash
python3 -m astrid media verify M_01ABC --project demo \
  --realm managed_local --json
```

When a runtime route is unavailable, the command reports the typed
`unavailable` condition and its next action. Backup operations are runtime-owned
gateway routes; use `backup create`, `backup restore`, `backup export`, or the
realm lifecycle operations with `--json` when automation needs the result.
