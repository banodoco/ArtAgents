# experiment_import

**Executor:** `iteration.experiment_import`
**Version:** 1.0
**Network:** false
**M1:** output_result_manifest: true

## Purpose

Import an unmanaged/legacy run root (for example the Discord-command POC
directory of timestamped submission subdirectories) into a provider-independent
experiment. Produces `experiment.json`, `import.report.json`, and a `runs/`
tree of synthesized manifests, imported run records, and independent
copy-on-write media. No absolute source path is
persisted — only the portable source subdirectory name survives.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `--root` | yes | Unmanaged run root directory. |
| `--out` | yes | Output directory. |
| `--mapping` | no | JSON of manual `subdir → {prompt, seed, label}` mappings. |
| `--rubric-file` | no | JSON rubric array. Defaults to a generic 0/1 rubric. |
| `--project-slug`, `--experiment-id`, `--title`, `--question` | no | Experiment metadata overrides. |

## Outputs

| File | Description |
|------|-------------|
| `experiment.json` | Experiment definition referencing synthesized run ids. |
| `import.report.json` | Honest report: counts, ambiguous/screenshot-only, dedup, gaps. |
| `runs/<run_id>/manifest.json` | Synthesized universal manifest per submission. |
| `runs/<run_id>/<media>` | Independent COW media clone (best-effort, no eager large copies). |
| `manifest.json` | Universal result manifest (M1). |

## Behavior

1. Walk `--root` subdirectories in sorted order (deterministic).
2. For each subdir, read `result.json` and synthesize a universal manifest
   (`astrid.core.experiments.capture.synthesize_discord_manifest`). Hash every
   resolvable download in place (read-only). Strip signed `sourceUrl`s.
3. No `result.json` + screenshots → truthful `unknown` (draft) record.
   No `result.json` + empty → `unknown` (draft) record with a `missing_manifest`
   capture gap.
4. Deduplicate recovery fetches only when `responseMessageId` and output
   SHA-256 sets agree.
5. Apply manual mappings with precedence; record `manual_mapping: true`.
6. Mark `ambiguous_prompt: true` whenever no prompt is recoverable; never guess.
7. Materialize `runs/<run_id>/` with the manifest, run record, and COW media.
8. Build `experiment.json` (one baseline case per subdir, `outcome` factor) and
   `import.report.json`.

## Rules

- **Never rewrite historical directories.** Source evidence is read-only.
- **No absolute source paths persisted.** Reports/manifests record only the
  portable source subdirectory name; the imported run tree already contains
  independent COW clones, so the absolute import root is neither needed nor safe.
- **No writable aliases or eager large-media copies.** Media uses COW cloning
  when supported; otherwise the local output is omitted and an honest capture
  gap is recorded.
- **No signed URLs or secrets persisted.** Only non-secret source-url counts.
- **Idempotent and byte-stable.** Synthetic run ids are deterministic;
  reruns produce byte-identical artifacts.
- **Ambiguous stays ambiguous.** Screenshot-only and empty submissions remain
  `unknown`/`draft`; the importer never promotes them to success or a guessed
  failure mode.

## Provider independence

The executor uses a capture adapter (`astrid.core.experiments.capture`) to turn
provider-specific artifacts into the universal manifest shape. The downstream
prepare/review path never branches on provider.

## Invocation

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "iteration.experiment_import",
        kind="executor", project="demo",
    inputs={"root": "path/to/discord-command-poc"},
)
```
