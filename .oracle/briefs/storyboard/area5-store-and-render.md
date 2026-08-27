# EXPLORER BRIEF

## NORTH STAR (complete)
# North Star — Astrid unified execution

## The desirable end state

Astrid v10 as **ONE store and ONE execution path**: every durable fact lives in the
SQLite kernel (projects, timelines, shots, references, tasks, runs, media, evidence,
receipts, events); every capability invocation — executor or orchestrator — runs as a
kernel run+task (admit → claim → start → execute → complete|fail) with hash-chained
events, receipts, attempts/leases, and managed outputs. `sdk.invoke` is the thin
admission wrapper. The filesystem `run.json` is at most a derived projection of the
kernel run — never an independent authority. Docs describe exactly what ships; the
suite and empirical process runs prove it.

## Enduring qualities and invariants to preserve

- **Single authority**: the kernel writer + UnitOfWork + receipts + events is the only
  state. No second store, no silent divergence path, no eventlog-only escape for an
  existing kernel timeline.
- **Every run is observable**: leases, attempts, retries, expiry, and the full event
  chain make any execution auditable, resumable, and replayable.
- **Honest docs**: no overclaims (e.g. "admitted tasks run" only when a driver ships);
  documented limitations are real limitations.
- **Elegance**: KISS / YAGNI. One generic adapter beats 50 bespoke ones; relax the
  completion contract minimally; cut scope that isn't pulling its weight.
- **Verified empirically**: every claim backed by a runnable process, test, or probe —
  not narrative.

## Anti-patterns to avoid

- A second ledger that must be kept "consistent by convention."
- Kernel/eventlog divergence (orphaned receipts, silent downgrades).
- Ghost verbs or docs that claim behavior that does not exist.
- Per-executor adapters where one generic path would do.
- Scope creep disguised as architecture (serve/GPU supervision beyond what execution needs).

## What aligned progress looks like

Each batch leaves the kernel as the single execution authority: more invocation paths
admitted as kernel tasks, fewer places that write run.json, docs and tests converging
on one ledger, and every gate (suite, process runs, oracle review) passing before the
next batch starts.


## AGENT GOAL (complete, frozen)
# Agent Goal — declarative storyboard layer (megado run)

[North Star](./northstar.md) — adopted in place from prior campaign; sha256 recorded in custody.md. This run advances the ONE-store principle by making the kernel-managed timeline the compiled output of a versioned storyboard source, with generations/prompts/variations first-class instead of sidecar convention.

## Objective
Deliver a general, versioned **storyboard data layer** plus compiler inside the Astrid repo, proven end-to-end by re-rendering the existing Astrid intro (astrid-intro project) from it.

Deliverables
- D1 `storyboard.schema.json` + loader/validator: meta(canvas/style) ; sections[] with nav tabs-state, ordered typed blocks: title, bullets, text, image(gen|asset), vo(text), video(gen|asset), mink slot directive {pose,anchor,scale}; every gen carries full spec {prompt,model,refs,seed?} and resolution fields (media_id|content_hash|path) + variants[] + active_index.
- D2 Enrichment/linkage conventions documented + implemented where cheap: vo blocks ↔ transcript timing (plan.json), images ↔ prompts persisted beside assets, timeline asset entries use AssetEntry.generationId when the image came from an Astrid generation, section→shot registration via `timelines shots` mount behind a flag.
- D3 Compiler `scripts/build_storyboard.py`: storyboard.json → managed timeline config+registry → `timelines save <slug>` (+`--render`). Timing model: default constant hold; `timing.hold` per block/section overrides; optional `--vo-align plan.json` snapping section starts to VO segment times (independent-of-length editing requirement).
- D4 Intro application: author `build/astrid-intro.storyboard.json` (25 slides: verbatim vo_text+captions from plan.json/captions, pyramid title/bullets equivalents, image=final-slides png as asset, original codex prompt preserved under history) → compile → save → render → open.

## Non-goals
No UI editor; no kernel core schema changes beyond using existing fields/mounts; no migration of other projects; English only; no style redesign.

## Model policy (user-pinned)
- Oracle/planner/[XHARD]: **grok-4.6** (grok CLI). Fallback if unavailable: GPT-5.6 Sol via `codex exec`.
- Explorer/normal executor: **GLM-5.3 Flash** (`launch_hermes_agent.py --model=zhipu:glm-5.3`, fallback `zhipu:glm-5.2`).
No automatic routing; pinned models authoritative unless evidence shows unavailability (then report + fallback as declared above).

## Done criteria
1. Validator accepts sample + intro storyboards; rejects malformed (missing nav/blocks/dup slug).
2. Compiler compiles intro storyboard to a NEW managed timeline; `timelines show` reports ≥76 clips… expected exact = current main content parity (76 clips/50 assets ± documented deltas).
3. Render of that timeline ≈177±3s, plays, contains all 25 slide visuals (spot-check 3 frames).
4. One regeneration variant demonstrably recorded (variant entry + picked active) without changing bytes of others.
5. Evidence matrix maps every criterion → command/path/result. grok oracle PASS per batch + final review (≤3 passes).

## Validation commands
- `python3 scripts/build_storyboard.py validate build/astrid-intro.storyboard.json`
- compile/save/render pipeline as in D3/D4 against ASTRID_PROJECTS_ROOT=/Users/peteromalley/Documents/reigh-workspace/astrid-intro-projects
- focused pytest for schema/validator (new tests/test_storyboard_schema.py)

## Sync/authorization
Commit batches on branch megado/oracle-run-storyboard; push that branch to origin authorized at finish. Opening local videos/files authorized. Never merge to main.

## Stop conditions
Blocked if grok AND codex both unavailable for oracle (report + halt after safe checkpoint). Escalate scope expansion beyond D1–D5.



Verified session context: worktree Astrid-megado branch megado/oracle-run-storyboard; intro project root env ASTRID_PROJECTS_ROOT=/Users/peteromalley/Documents/reigh-workspace/astrid-intro-projects; main timeline config_version 13; deliverable D1-D5 per agent goal; KISS per North Star; you are read-only.

# AREA: area5-store-and-render
Answer these precisely with file:line evidence:
1. kernel exclusive-owner/bridge state
2. supported mutation route while serve may run
3. render asset containment for repo-external PNG/WAV
4. import-to-managed-media flow

Report: verified facts w/ evidence, unknowns, risks, suggested approach honoring ONE-store/KISS. Ranked, <300 words. Mechanical only.