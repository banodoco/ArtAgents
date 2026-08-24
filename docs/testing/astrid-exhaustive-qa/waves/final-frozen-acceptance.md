# Final frozen-surface LIVE AGENT UX acceptance

Date: 2026-08-23 (Europe/Berlin)  
Surface: public Astrid help/docs, eight-family CLI gateway, and Python SDK only  
Environment: fresh disposable root, local fixtures, no credentials, no paid/cloud calls

## Verdict

**Conditional pass for the kernel/media/project/recovery surface; fail for the complete maker outcome. Score: 5.5/10.**

The local product kernel is unusually coherent for a fresh maker: project routing, CAS timeline saves, content-addressed media, references, reusable shots, receipts, hash identities, backup portability, restore rebasing, doctor, and SDK event readback all worked. The acceptance is not a clean end-to-end pass because the central “make a visible rendered video” step did not complete. The documented managed-project timeline visualization is also absent from the CLI census and had to be reached through `sdk.invoke`.

## Fresh-maker journey and timing

The run took about 10 minutes wall time, including a few deliberate wrong turns and dependency-free fixture generation.

1. Read the core skill and public CLI/docs. `python3 -m astrid --help` and `help` exposed exactly eight families: `projects timelines media tasks runs serve doctor backup`; nested mounts were `timelines shots` and `media references`. No source, tests, git history, or prior QA reports were consulted.
2. Created project `frozen-maker` (“Frozen Maker”), selected it at workspace scope, and read it back with `projects current`. The selected project id was `3518d6ee-1e1e-5387-a370-b59226078ed1`; selection resolved correctly from the workspace preference.
3. Created default timeline `primary`, id `ff56bd2c-4aff-5ab9-8ee7-adf8384d46fc`, ULID `y2sfe0qa0w9dy45kf77qxmvm1c`.
4. Generated local 1-second audiovisual fixtures with ffmpeg: `av.mp4` (video+audio), `red.png` (image), and `tone.wav` (audio). Imported all three through `media import`, receiving stable media ids and SHA-256 identities:
   - video `8bdffe00-4025-5ea8-b485-2bc3e2c9304d`, hash `356869c3d785f18c...`
   - image `7c52f494-816c-5ad8-a776-513836b7a49d`, hash `1aa9731bec304438...`
   - audio `70448da8-9fc4-55f3-b926-e958d3bb2303`, hash `b4255475916d8f9...`
5. Created name-addressed reference `Aria` (reference id `12b559ac-3a00-5cb9-99f2-d9a58871bfc6`), associated the imported video, created reusable shot `Opening shot` (shot id `8d0c00bd-7e77-53a2-b183-caffb04ecc82`), added the image, and confirmed `shots show` returned ordered item/media details from a fresh read.
6. Saved a public timeline document with visual and audio tracks and two clips. `timelines show`, `history`, and `diff` reflected the CAS version and event history. The first save without `clipType` was rejected later by visualization (fixture mistake); adding explicit `image`/`audio` clip types produced a valid timeline.
7. `rendering.timeline_storyboard` succeeded through the SDK as run `dfb3f697a76f4233eee3f3d970`, task `aaf276a38e712afe99d81e45ca`, with `preview.png`, `preview.html`, and `preview.json`. It was a structural success, but the fixture had no `pinnedShotGroups`, so the storyboard correctly rendered “NO INPUT IMAGES”; this is a fixture omission, not evidence of missing media.
8. `rendering.timeline_visualize` succeeded through the SDK as run `63dde1144e1e812fd046cffb52`, task `6c92f9032ab0391db5337f40cf`, with two PNG pages, two SVG pages, ground truth, structure Markdown, action index, asset index, diagnostics, and reading guide. A second fresh invocation by timeline ULID (`8e8af1b3ec88a1938374bd2b99`, task `a0869ef3c7a154f4a9fb690254`) also succeeded. The PNG was visually inspected and showed TL01, visual/audio lanes, clip ids, time scale, and the frozen snapshot banner.
9. Structured invalid preflight via `astrid.sdk.invoke_result` returned `ok=false`, `CapabilityValidationError`, `sdk_category=validation`, and no run id for invalid format `not-a-format`; it admitted no run.
10. Tried the real `rendering.render` path. First attempt failed because project-scoped inputs outside the project root are rejected. Moving the timeline/registry into the project exposed the next real constraint: canonical managed media lives under `$projects_root/.astrid/media`, outside the per-project root. Copying fixture bytes into the project then reached Remotion but failed with browser CORS (`localhost:3000` versus the local `127.0.0.1` asset server). The ffmpeg backend also rejected the attempted image/audio/video clip-kind combinations. Runs `6ff74cb6aa0f54769e4bfdb65a2c`, `aab2cbcf83d1d87f5442308bee`, and `315be438a2d4dcb8e3570f7a6f` are truthful failed runs with no MP4 output.
11. Added the same video as `external_local`, verified it, created a self-contained backup, deleted the original external source, and restored into a new disposable root. Backup reported one external dependency and one external snapshot; restore reported one rebased external locator and zero unresolved locators. Restored `media show` preserved the original locator in `metadata.backup_provenance.external_local` and pointed the external realm at the verified backup-owned bytes. Restored `media verify` passed and restored `doctor --json` passed all required checks: paths, media, SQLite quick-check, foreign keys, and `core/references/shots/timeline` schema versions.
12. On the restored root, archived the timeline and reference, rediscovered them with inclusive lists, unarchived timeline by slug `primary` and reference by exact name `Aria` without ids, and repeated timeline unarchive to receive `changed:false`.
13. Read restored run events through `astrid.read_events(..., verify=True)`. Both successful runs returned `EventStreamRecord(source="kernel")`, proving the SDK used the canonical SQLite fallback after restore rather than a filesystem projection. Task event streams independently showed the complete queued → claimed → started → completed chain and output hashes.
14. Documented one successful orchestrator dry run: `video_editing.hype` returned `ok=true`, a planned command/plan, `dry_run=true`, and no run id or side effects.

## Identity, hash, provenance, and event truth

- Project, timeline, reference, shot, media, run, and task identities remained stable across fresh reads and restore.
- Managed media `content_hash` values matched the generated fixture SHA-256 values. The external video retained hash `356869c3d785f18c...` before backup, in `backup.json`, and after restore.
- The restored video metadata recorded both `original_locator=/tmp/.../external/av.mp4` and the backup-owned restored locator under `restored-projects/.astrid/media/sha256/...`.
- Successful visualization task completion events listed every output content hash and media id; `runs show --evidence` returned the same child output manifest.
- `tasks events` for visualization and storyboard exposed the full lifecycle with chained `event_hash`/`previous_event_hash`. `runs events` exposed the run-created event; detailed lifecycle truth is currently task-level.

## First-attempt outcomes and manual hops

Successful first attempts: project create, selection/current, timeline create, all three media imports, reference create/associate, shot create/add/show/list, timeline save after adding required clip types, storyboard SDK invocation, visualization SDK invocation with explicit `filmstrip=off`, invalid preflight, external import/verify, backup, restore, doctor, archive/return, restored event readback, and orchestrator dry run.

Wrong turns/manual hops: fresh-root doctor correctly returned a nonzero “database missing” state before bootstrap; nested help must be invoked at the nested mount rather than with project options before the nested verb; the first renderer input files were outside project ownership; managed-media paths are outside the renderer’s allowed per-project root; an initial visualization replayed the same idempotent failed request until the input changed; the first visualization fixture omitted `clipType`; `media relocate --realm external_local` returned `not_found` for a future path despite help text saying future references are accepted, so external media was added with the documented `media import --realm external_local`; the storyboard fixture omitted pinned shot groups; and `projects select` wrote the expected workspace preference file-side.

## Severity-ranked residuals

### P1 — real product gap: no successful public render of canonical/local media

The core maker outcome is blocked. `rendering.render` first rejects the canonical managed-media locator because it is outside the project root, then reaches Remotion with project-local copies but fails to load the image due CORS. The alternate ffmpeg attempts rejected the supplied clip kinds and produced no visible MP4. This is not an optional cloud dependency: the invocation was local, the Remotion adapter was installed enough to execute, and all failures were runtime protocol/ownership behavior.

### P1 — public visualization discovery gap

The skill/docs describe `astrid timelines visualize`, but `python3 -m astrid timelines --help` lists no `visualize` verb and the CLI invocation exits with argparse code 2. The capability is usable through the public SDK and produced strong artifacts, but a new CLI-only maker cannot discover or reach it from the frozen gateway census.

### P2 — run-level observability is thinner than task-level truth

`runs show` correctly derived success and output manifests, while `tasks events` contained the full lifecycle/hash chain. `runs events` returned only `core.run.created` in this acceptance. This is consistent and truthful, but a maker seeking direct run evidence must make an extra task lookup.

### P2 — relocation help/behavior mismatch

`media relocate --realm external_local` help says an existing or future reference is accepted, but a future external path returned `not_found`. `media import --realm external_local` worked and is a viable route, so this is a recovery UX inconsistency rather than data loss.

### Fixture limitations (not product findings)

The visualization registry omitted content hashes, so the generated pack labeled assets `integrity_state=unsupported`; the source media itself was imported and verified correctly. The storyboard timeline did not contain `pinnedShotGroups`, so its honest preview had no input images. These fixture choices should not be scored as kernel/media failures.

## Cleanup

All acceptance data and generated processes were disposable. The temporary projects root, external fixtures, backup, restored root, local HTTP process, dry-run artifacts, and workspace project-selection preference were removed after evidence capture. No source, tests, git state, or product code were changed; this report is the sole durable artifact.
