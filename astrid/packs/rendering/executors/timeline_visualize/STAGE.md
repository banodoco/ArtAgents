# Timeline Visualize

`rendering.timeline_visualize` freezes one or more managed timeline generations
and produces a deterministic evidence pack for agent inspection. Default,
slug, UUID, ULID, and `all` selectors resolve only the canonical SQLite kernel
timeline; the current row is the snapshot projection and the immutable stream
head/version/hash pins provenance. A legacy filesystem event log is accepted
only through the explicit `timeline_source` compatibility input.
Leaf evidence manifests make this boundary explicit with
`inputs.source_mode`: `kernel` for current canonical selection, `legacy` only
when `timeline_source` was supplied, and `frozen` for navigation from an
existing view. `resolved_project` and `resolved_timelines` carry the exact
selected identities; the historical `timeline_source: [project_slug]` field
is retained only for frozen-v1 compatibility.

ULID spelling has one deliberate compatibility seam. Public v10 timeline
`create`, `list`, and `show` DTOs use the kernel's canonical lowercase
Crockford spelling. Frozen timeline-visualize v1 identity and snapshot fields
remain uppercase because their schema and immutable evidence packs require it.
New manifests therefore also include additive
`inputs.canonical_timeline_identities`, whose UUID/slug are unchanged and whose
ULID is lowercase for direct comparison with public kernel DTOs. Do not rewrite
`resolved_timelines` or `snapshots` in an existing pack; compare the additive
identity when present, or compare legacy ULIDs case-insensitively.
It is a first-class project executor, but it deliberately declares
`requires_timeline: false`: one run may cover several timelines and is never
bound to, or recorded in, a timeline `manifest.json`.

## Read-only contract

The executor reads kernel timeline rows/config/history or
`assembly.identity.json`, `assembly.jsonl`, and compatible read-only sidecars
beneath legacy selected project timelines. It does not call
timeline repair or CRUD paths, does not append events, and does not update
`manifest.json.contributing_runs`. Existing timeline manifests remain
byte-identical; a missing timeline manifest remains missing.

The managed run ledger owns operational identity and retention. Its metadata
contains sorted `timeline_ids`, `evidence: true`, and the executor contract
digest. Run GC preserves evidence runs by default; removing them requires an
explicit evidence-inclusive GC pass with `--apply` (ledger-level tooling, not
a gateway command).

## Pack layout

The run writes `agent-view/manifest.json` plus the mandatory machine bundle:

- `ground-truth.json`, `view-map.json`, and `action-index.json`
- `asset-index.json`, `transcript-index.json`, and `diagnostics.json`
- `reading-guide.md` and optional factual `structure.md`
- numbered `PG*.png`, optional matching `PG*.svg`, sampled `filmstrip/` media,
  and `pack-hashes.json`

For `--all`, `agent-view/manifest.json` is a project index and each selected
timeline has a deterministic `TLNN/` child pack. Run ULIDs, run paths, and wall
clock time are excluded from pack content identity.

## Inputs and navigation

Cold selectors mirror the timeline-navigation façade of the executor: optional
timeline reference (slug, UUID, or ULID), `--all`, `--shot`, `--range`, `--at`,
`--clip`, `--asset`, `--context`, `--neighbors`, `--layout`, repeatable
`--format`, `--filmstrip`, and `--rendered-video`. `project_slug` is the
executor-level project identity and is derived from `project=<slug>` for a
managed SDK invocation. `timeline_source` is the contained, repeatable SDK
handoff form: pass a managed timeline directory or any file inside that
directory. Without `timeline_source`, selectors also resolve canonical kernel
timelines created/saved through the public timeline SDK. The source form is
mutually exclusive with a timeline reference or `all`.

The command spelling is singular and repeatable while the SDK field is plural:

```bash
python3 -m astrid.packs.rendering.executors.timeline_visualize.run \
  --out /tmp/agent-view \
  --project-slug desert-plant-growth \
  --timeline-slug storyboard \
  --format png --format svg
# Equivalent: --format png,svg
```

For the normal project-scoped maker path, omit `out` and let Astrid manage the
run-owned output tree:

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "rendering.timeline_visualize",
    kind="executor",
    project="desert-plant-growth",
    inputs={
        "timeline_slug": "storyboard",  # UUID, ULID, or slug; omit for default
        "formats": ["png", "svg"],
        "layout": "both",
    },
)
assert result.ok
print(result.outputs)
```

The same path is available as the public nested timeline command. It is
synchronous, emits the standard five-key CLI envelope with run/kernel IDs and
durable output paths in `data`, and accepts either a slug, UUID, or ULID. The
project may be omitted when a project has been selected:

```bash
python3 -m astrid timelines visualize --project desert-plant-growth \
  --timeline-slug storyboard --format png,svg --format md --json
# Omit --timeline-slug for the project default; use --all for every active row.
```

`--format` is repeatable and comma-separated (`png`, `svg`, `md`, or `all`),
with `all` exclusive of other formats. `--timeline-source` is repeatable for
legacy project-owned managed directories/files and is mutually exclusive with
`--timeline-slug` and `--all`. Invalid ownership, selectors, and combinations
are returned as typed validation errors before a run/task is admitted.

The CLI/SDK `timeline_source` input is the explicit legacy path. The emitted
manifest's older `inputs.timeline_source` field is different: it is frozen-v1
compatibility data containing `[project_slug]`. It is intentionally retained,
but it is not evidence of which timeline path or authority was read. Use
`source_mode`, `resolved_project`, `resolved_timelines`, and
`canonical_timeline_identities` for provenance and cross-surface comparison.

Equivalent source-file addressing is safe when the file belongs to the
project's managed timeline directory:

```python
result = sdk.invoke(
    "rendering.timeline_visualize",
    kind="executor",
    project="desert-plant-growth",
    inputs={
        "timeline_source": [
            ".../desert-plant-growth/timelines/<timeline-ulid>/assembly.jsonl",
        ],
        "formats": ["md"],
    },
)
```

Do not pass `out` together with `project`: the project-scoped runner supplies
the private staging output and publishes the evidence pack under the managed
run. A source path outside the owning project's managed timeline directory is
rejected before execution.

Snapshot-safe `--from-view`/`--focus` navigation accepts the durable managed
manifest path returned by a successful visualization (Astrid rehydrates and
hash-verifies its kernel-owned companion outputs). It follows
`docs/architecture/timeline-visualization-agent-navigation.md`. That document
is the canonical agent navigation contract once R18 lands; the evidence pack's
`action-index.json` is the executable source of navigation actions.
