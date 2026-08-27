# SETTLED-PLAN CRITIQUE WAVE round 2 (final spec)

## NORTH STAR
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


## AGENT GOAL
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

## Amendment 1 — shots registration removed from D2
Authorized by the user's blanket no-questions mandate plus the settled-plan wave (synthesis disposition #1): both critics converged that section→shot registration is not 'cheap' on a mount lacking update/delete/unique-name guarantees. D2's shots clause is CUT from v1 scope; revisit only as an explicit future request.


## PLAN v6 FINAL SPEC
# Megado plan v6 FINAL SPEC — declarative storyboard layer

Normative language below is FINAL. Any conflict with older drafts loses; this file is the frozen source for Batch definitions.

## Canonical data model (normative)

Section = {
  id: slug,
  nav: { tabs[2]: {label,color_state}, active: 0|1 },
  timing?: { hold: seconds },                    # override only
  blocks: [ Block... ],                          # ordered
  provenance?: { prompt: string, generator?: {tool, backend} }   # OPTIONAL, preserved VERBATIM into registry entry.origin (JSON-encoded)
}

Block kinds:
- title { text }
- bullets { items: string[] }
- text { text }
- image {
    variants: [ Variant ],                       # >=1; BOTH asset-backed and gen-backed allowed together
    active_index: int                            # selects which variant renders; B5 proof flips 0<->1
  }
- vo { text, audio: { asset: "build/segments/<slug>.wav" } }
- video { variants: [ Variant ] , active_index: int }   # same Variant model, duration for gen
- mink { pose, anchor, scale }                  # INERT PROVENANCE ONLY — never compiled to any pixel/text output

Variant = when source=="asset": { source:"asset", path } ; when source=="gen":
{ source:"gen", prompt, model?, refs[]?, seed?, alt_render_path?, duration? }

Compiler resolution contract: EVERY variant resolves to a managed-media record
{ path:<CAS locator>, media_id:<kernel uuid>, content_hash:<sha256 hex> }.
- asset variants: MediaService.import_file(path)
- gen variants: IF alt_render_path exists on disk → import that bytes as the result (no paid call). ELSE invoke generation executor once and import returned bytes.
block.resolved[] = resolved records, order == variants; ACTIVE index picks rendered clip source.
Registry entries emitted: {"file": <CAS path>, "content_sha256": <digest>, "origin": json(section.provenance or {})}.
AssetEntry.generationId is intentionally ABSENT (exploration Area3: no qualifying id exists); presence-free validation is tested. Provenance lives in `origin`.

## Compiled output parity rule (intro application)

Sections whose ACTIVE variant pngs bake title/bullets/mink (the 25 HTML-shot slides) compile to EXACTLY:
3 clips/section (broll plate, caption, VO audio) + 1 brand wordmark clip TOTAL = 76 clips / 50 assets / 177.53s ±0.5s vs main v13.
Live storyboards (non-baked art) additionally compile title/bullets as text clips; mink NEVER compiles to text; her pixels come only from referenced art assets.

## Batch 0 (folded into B2 as golden tests)

Golden fixture: 25-section intro storyboard compiles to the parity numbers above (byte-stable config/registry).

## Batch 1 — Schema + loader + validator
Files: astrid/core/storyboard/{__init__,loader}.py + astrid/core/storyboard/storyboard.schema.json (+ tests/core/storyboard/)
Checks: version==1; unique section ids; nav.tabs length 2; nav.active in {0,1}; variants non-empty; active_index in range; every asset path resolves OR declares gen; gen requires prompt; provenance optional passthrough; resolved fields OPTIONAL pre-compile (schema allows nulls) and REQUIRED post-compile (compiler re-validation).
Acceptance: valid intro sample passes; malformed raises typed StoryboardError listing ALL problems.

## Batch 2 — Compiler + golden parity tests + timing model
File: scripts/build_storyboard.py — compile_storyboard(story, *, vo_plan=None) -> (config, registry)
Timing: default meta.timing.default_hold=3.0; section timing.hold overrides; --vo-align <plan.json> sets each section start to matching slug start (order-preserving); audio durations probed via ffprobe.
Include Batch-0-folded golden test asserting 76/50/177.53±0.5 on the committed 25-section fixture (intro sample committed at storyboards/intro-fixture.json minus real absolute paths — paths templated).

## Batch 3 — Kernel linkage + CLI
Managed import first (media.import_file), CAS save (`timelines save`, expected_version), thin CLI flags: validate | compile [--vo-align F] | --render. Integration tests (4): preflight-before-write; create→CAS-save→version bump; rerun byte-equality; variant resolution produces block.resolved + matching registry content_sha256 and validation succeeds with generationId absent.
No register-shots flag anywhere.

## Batch 4 — Author tracked intro storyboard
storyboards/astrid-intro.storyboard.json committed in repo: 25 sections mirroring current VO order/text; every image block variants exactly [final-html(asset), codex-pyramid(gen+alt_render_path)], active_index 0; original codex prompt preserved in section.provenance.prompt AND variant.gen.prompt.

## Batch 5 — Live compile, flip proof, render, spot-checks, evidence matrix
Sequence: import images+audio to managed media; compile (--vo-align) → save → flip active_index 1 → re-save (version bump proves independence) → flip back 0 → save → parity assertions script (25/76/50/duration) → `timelines render` astrid-intro-storyboard.mp4 → OCR 3 frames (open, idea1_vc, cta_agents) → evidence matrix .oracle/evidence/final-matrix.md.

## Batch 6 — Docs + sync
README storyboard usage snippet; commit history tidy; push branch; support final review.

Non-goals (binding): no UI editor; no kernel core schema changes beyond using existing fields/mounts; no migration of other projects; no generationId synthesis; no physical prompt sidecars; no register-shots flag.

Estimate: ~3–5 days elapsed-equivalent ⇒ below huge-run threshold.



# YOUR LENS
LENS: simplification — fewer steps/layers/handoffs? any speculative abstraction? rank concrete cuts.

Rules: no scope widening; rank CONCRETE cuts/simplifications citing sections; <250 words.
