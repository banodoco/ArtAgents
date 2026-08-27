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

## Amendment 2 — test-path + scope-cut authorization
Authorized under the user's blanket no-questions mandate: focused tests live at tests/test_storyboard_schema.py (not tests/core/storyboard/); shots/gen-executor-branch/live-text-compilation cuts from the settled waves are ratified as v1 scope boundaries.

## Amendment 3 — oracle gates in-scope
Done criterion 5's per-batch grok gates and final review are IN SCOPE for this run and are executed by the host orchestrator.

## Amendment 4 — regeneration proof
Done criterion 4 upgraded: variant selection proof PLUS one real kernel-recorded regeneration (generation executor) imported and activated for at least one section.

## Supersession matrix (binding over base sections)
| Base clause | Final disposition |
| D1 storyboard.schema.json artifact | REPLACED: single Python validator module astrid/core/storyboard/loader.py |
| D1 ordered typed blocks title/bullets/text/image/vo/video/mink | FINAL: sections carry exactly image{variants,active_index} + vo{text,audio_asset}; other kinds unsupported-in-v1 (typed error) |
| D2 transcript/images/generations/variants/shots/clip linkage | FINAL: images+prompts via variants/provenance; vo timing via --vo-align plan.json; shots CUT (Amendment 1) |
| D1 resolution fields media_id/content_hash/path | KEPT — compiler-filled only (never persisted into authored JSON), asserted in compiled registry/output |
| AssetEntry.generationId propagation | OMITTED by policy (no qualifying id exists) |
| Synthesis r1 #4 variants restricted to {path,label}[] | SUPERSEDED by Amendment 4: gen variants carry source:"gen"+prompt(+model,refs)+alt_render_path; resolved records keep path/content_hash (+media_id when imported) |
| Done criterion 4 variant+active flip | UPGRADED by Amendment 4: includes one real kernel-recorded generation imported & activated (transient asset count 51 allowed mid-proof) |
