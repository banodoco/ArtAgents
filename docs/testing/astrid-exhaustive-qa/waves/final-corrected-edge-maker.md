# Final corrected edge-maker LIVE acceptance pass

**Date:** 2026-08-23  
**Surface:** public eight-family CLI, public SDK/discovery, public docs/skill guidance  
**Scope guard:** fresh disposable roots; no source/tests/campaign reports; no cloud credentials or cloud calls.

## Verdict

**Conditional pass — strong maker loop with two material P1 residuals.** The corrected public surface supports a real local audiovisual maker flow, durable IDs, receipts, run/task linkage, reversible recovery, portable backup, cross-root restore, deduped media locations, and doctor-green integrity. The acceptance is not a clean pass because `rendering.timeline_visualize` cannot consume the kernel-created timeline through either documented project-default or standalone-file paths, and restored kernel runs do not have readable filesystem event logs through `astrid.read_events(..., verify=True)` even though CLI run/task read models remain present.

**Revised agent-UX score: 7.2/10.** The core flow feels coherent after the contract is known; first-output time and recovery cost are held down by render schema friction, selection-context friction, and the two residuals above.

## What worked

- Census matched the documented eight families: `projects`, `timelines`, `media`, `tasks`, `runs`, `serve`, `doctor`, `backup`; nested mounts `timelines shots` and `media references` were reachable.
- Created/selected `edge-demo`, default `primary` timeline, local MP4 + WAV external media, named `Blue Voice` reference with two associations (canonical video and inspired-by audio), `Opening Shot` with ordered video/audio items, and an `audio_for` relation.
- Timeline save/history/diff preserved version 1 → 2; after archive/unarchive, version 4 remained readable. Archive recovery by timeline slug and reference name worked, including idempotent `changed: false` repeats.
- `rendering.render` completed through the public SDK. `runs show --evidence` exposed result media `01m0r50gsz6me9w1cqt7kc2n81` and provenance media `01m0r50gt0m76w3vabpf9yf6bq`, with hashes and paths. The managed MP4 was 2.048 s, H.264/AAC, and a decoded frame visibly showed **FINAL EDGE TITLE**.
- Invalid generation preflight (`generation.generate_image`, unknown model) returned a structured validation error with `run_id: null`; no run was admitted and no network call was made.
- Backup captured 6 media artifacts and 2/2 external snapshots. After deleting the original source and project roots, restore rebased both external locators cross-root with zero unresolved files. Re-importing a copied restored video produced two external locations on the same media ID/hash, not a duplicate media row. Doctor returned `ok: true` with quick-check, FK, schema, managed media, and external integrity all green.
- Restored task `0079eb3d8d487464b330fd1367` points to run `224b4873189db5ae6252ec284d`; the run’s child output IDs and run/task status agree. Reference/shot/timeline/project IDs and provenance survived restore.
- SDK discovery found orchestrators and a documented dry-run of `stream_content.distill` succeeded with explicit `video`, `transcript`, and `brief` inputs; no run was admitted.

## Friction and wrong turns

- `projects current` without `--cwd` read the machine’s stale user preference (`north-star`) and failed, while `projects select ... --cwd <root>` and `current --cwd <root>` worked. This is recoverable but easy to hit in a fresh-root workflow.
- `media references associate` accepts an exact reference ID, not the human name accepted by unarchive/show; the initial name attempt returned `not_found`, then the ID path worked.
- First output took about **4 minutes from project creation to successful render**. Four render attempts failed before success: input outside project ownership; missing root `clips`; invalid `output` shape; and text lacking the structured schema/`clipType: text`. Diagnostics were actionable, but the quick-start docs do not make the render JSON contract sufficiently maker-friendly.
- The first successful render initially produced a black frame because a text-shaped clip without `clipType: text` was valid enough to execute but visually empty. The corrected clip rendered visibly.

## Residual severities

- **P1 — Timeline visualization is not reachable from the corrected public timeline flow.** `sdk.invoke("rendering.timeline_visualize", project="edge-demo", inputs={"timeline": ...})` failed with “no eligible managed timelines”; `timeline_source` pointing at the project-owned JSON failed because it was not inside a managed timeline directory. `timelines create/save/show` created a durable kernel timeline but no public managed-timeline directory projection for this executor. The requested visualization therefore could not be produced.
- **P1 — Event-log provenance does not survive portable restore.** Restored `runs show`, `runs events`, and `tasks show` work and preserve IDs/status, but `astrid.read_events("edge-demo", "224b...", projects_root=restore, verify=True)` returned `CapabilityPreconditionError: run ... not found`. The kernel read model is durable while the SDK filesystem event reader is not.
- **P2 — Selection context and identifier vocabulary are uneven.** Workspace selection is root/cwd-sensitive, and references are name-addressable for recovery but ID-only for association.
- **P2 — Render contract discoverability.** The final render was reliable once the compositor schema was inferred from diagnostics/reference docs, but a maker should not need several failed admissions to learn `clips`, `output.resolution`, structured `text`, and `clipType`.

## Cleanup

The disposable original source/project roots, restore root, backup root, decoded preview frames, and temporary transcript/brief were removed; the SDK dry-run produced no persisted output. No source files, tests, credentials, cloud state, or user processes were changed.
