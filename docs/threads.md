# Threads

> ⚠️ **Threads are a retired user-facing concept.** The `astrid thread` CLI
> surface no longer exists. Threads remain only as an internal lineage model
> for legacy run records, variant sidecars, and iteration-video provenance.
> They are not a runtime binding contract for any current `astrid` command.
> See [docs/architecture.md](architecture.md) for the current public concepts.

Threads are retained as an internal lineage model for legacy run records,
variant sidecars, and iteration-video provenance. They are no longer a
user-facing runtime binding contract for generic `astrid executors run` or
`astrid orchestrators run` commands.

## Model

- `.astrid/threads.json` is compatibility state used by lineage readers.
- Legacy `run.json` records may still contain a scalar thread id and typed
  `parent_run_ids`.
- New generic executor and orchestrator runtime calls do not create thread
  records, do not select an active thread, and do not inject thread environment
  variables.
- Iteration-video tooling can still read the internal lineage index when a
  caller explicitly asks for a lineage id or `@active` inside that pack.
- `.astrid/iteration_cache/` stores per-run summaries for iteration videos; it
  is cache state, not session identity.

## Prefixes

Generic runtime prefix lines were retired in Sprint 1. Inspect and run output
should not include active-thread footers or thread banners. Existing prefix
helpers remain only for compatibility tests and historical iteration fixtures,
not as current CLI guidance.

## Privacy & Redaction

`runs/` is local output and should stay out of git. Legacy thread records redact
CLI values whose keys look secret-like, including `KEY`, `TOKEN`, `SECRET`,
`PASSWORD`, `PASSPHRASE`, `API_KEY`, and `BEARER`.

Brief snapshots are plaintext by default when the brief is outside the run's
private directory. To opt into path-based privacy for legacy records, put
sensitive inputs under `runs/<slug>/private/`; record builders keep hashes and
labels without storing the private path or plaintext.

## Concurrent Variant Selection

Variant producers can still write append-only selection events under
`.astrid/threads/<lineage-id>/selections.jsonl` and lock-protected group state
under `.astrid/threads/<lineage-id>/groups.json`.

Selections are append-only; the most recent write is authoritative on read;
prior selections are preserved as history but do not affect current keepers.
This behavior is lineage bookkeeping for pack utilities, not generic runtime
binding.

## Tier Firing Rules

There are no current generic executor/orchestrator thread tiers. The retired
thread banner, variant banner, lifecycle notices, fan-out hints, warning tiers,
and health-smell lines are not active user-facing runtime behavior.

## Inspect Before Render

Before rendering an iteration video, inspect the lineage:

```bash
python3 -m astrid.packs.video_editing.orchestrators.iteration_video.run inspect <lineage-id-or-active>
```

Inspect does not render and does not dispatch summarization. It reports detected
modalities, chosen renderers, quality, summary-cache hits and misses, and a
single estimated cost line. Use the pack-level no-content option for sensitive
lineage.

The render path is:

```text
iteration.prepare -> iteration.assemble -> rendering.render -> finalize
```

`iteration.assemble` writes canonical `iteration.*` files and render-compatible
`hype.timeline.json` plus `hype.assets.json`. `rendering.render` (legacy alias:
`builtin.render`) consumes that
exact `hype.*` pair and emits `hype.mp4`; the iteration-video orchestrator then
records `iteration.mp4` with the other canonical iteration outputs.

## Stale Locks

If a lineage utility times out waiting for `.astrid/threads.json.lock`, first
verify that no Astrid process is still running or writing lineage state. After
that process check, remove the stale lock file manually and rerun the lineage
utility. The index keeps a `.bak` copy for recovery if a previous write was
interrupted.

No lock-repair command ships.

## Deferred

These retired or deferred surfaces are not generic runtime behavior:

- Thread split, merge, attach, detach, or automatic repair commands.
- Generic executor/orchestrator thread selection flags.
- Generic runtime thread prefix lines, active-thread inspect footers, and
  thread environment inheritance.
- Extra renderers beyond the currently implemented iteration-video renderers.
- Cross-modal sub-pursuits or `--mode parallel|interleaved`; iteration video is
  chaptered.
- Natural-language parsing of `--direction`; it is a label only.
- `--why` reasoning output on iteration-video inspect.
- Brief-similarity heuristics, semantic-distance dilation, or browse UI.
- Warning novelty, fan-out hinting, and health-smell output.
