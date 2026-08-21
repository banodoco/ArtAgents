# Timeline Visualize

`rendering.timeline_visualize` freezes one or more managed timeline event-log
generations and produces a deterministic evidence pack for agent inspection.
It is a first-class project executor, but it deliberately declares
`requires_timeline: false`: one run may cover several timelines and is never
bound to, or recorded in, a timeline `manifest.json`.

## Read-only contract

The executor reads `assembly.identity.json`, `assembly.jsonl`, and compatible
read-only sidecars beneath the selected project timelines. It does not call
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
timeline slug, `--all`, `--shot`, `--range`, `--at`, `--clip`, `--asset`,
`--context`, `--neighbors`, `--layout`, repeatable `--format`, `--filmstrip`,
and `--rendered-video`. `project_slug` is the executor-level project identity;
`timeline_source` is the contained, repeatable SDK handoff form.

Snapshot-safe `--from-view`/`--focus` navigation follows
`docs/architecture/timeline-visualization-agent-navigation.md`. That document
is the canonical agent navigation contract once R18 lands; the evidence pack's
`action-index.json` is the executable source of navigation actions.
