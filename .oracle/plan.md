# Megado plan v8 FINAL — declarative storyboard layer (single-authority model)

v8 resolves all prior findings: single unified variant/resolution model, VO audio sourcing, kernel-sole-authority clarification, gates enumerated, provenance schema defined. This text supersedes earlier drafts entirely.

## Roles/gates
Oracle: grok-4.6 (fallback GPT-5.6 Sol via codex). Explorer/executor normal: GLM-5.3 Flash (zhipu:glm-5.3, fallback zhipu:glm-5.2).
Every batch B1..B6 ends with a grok-4.6 gate whose brief embeds North Star + agent goal (incl Amendments 1-4) + batch delta; verdict PASS/issues → .oracle/checkins/batch-N.md. Final overall review after B6: GLM pass(es) + grok synthesis (≤3 total).

## Canonical authored input: storyboards/astrid-intro.storyboard.json (tracked)
AUTHORED INPUT ARTIFACT (analogous to scripts/prompts — source content + lineage). Execution/durable state lives ONLY in SQLite; this file is versioned source content, exempt from the every-durable-fact rule which governs execution/ledger data. It NEVER receives kernel-derived values (no media_id/content_hash/resolved write-backs — those live in compiled config/registry each render).

Section = {
  id, nav:{tabs[2],active}, 
  image:{ variants:[{source:"asset",path,label} | {source:"gen",prompt,model?,refs[],alt_render_path(required-in-v1),gen_kernel_run_id?,label}], active_index },
  vo:{text, audio_asset:"build/segments/<slug>.wav"},
  provenance?:{prompt,generator}
}
meta {title, canvas:"1920x1080@30", style:"pixel-terminal", timing.default_hold:3.0}

## Compiler (scripts/build_storyboard.py)
validate(story)->problems | compile(story,*,vo_plan=None)->(config,registry,resolution_report)
Resolution contract per variant:
 - source=asset → MediaService.import_file(path) → CAS
 - source=gen → import_file(alt_render_path) [v1 requires alt_render_path; NO paid gen branch]
resolution_report[slug] = section.image.resolved (mirrors variants order) → consumed ONLY into this render's registry/config (kernel-owned), never written back to the storyboard file.
Registry entries emitted per resolved asset: {"file":<CAS>,"content_sha256":<digest>,"origin":json(section.provenance||{}), "generationId": <variant.gen_kernel_run_id when present, else absent>}. gen_kernel_run_id is an AUTHORED lineage field captured at generation time (kernel run id from the sdk.invoke manifest); resolved identifiers (content_hash/media_id) remain compiler-output-side only and are never written into the authored storyboard. Absence-free validation applies to entries lacking gen_kernel_run_id; presence path is also validated (string).
Parity rule: baked-PNG active images compile exactly 3 clips/section + brand ⇒ intro compiles 76 clips / 50 assets / ~177.53s vs main v13 oracle. Non-baked apps may later add text-clip synthesis — out of v1 scope.

## Batches (each gated by grok check-in; commits between)
B1 validator+loader module astrid/core/storyboard/ + tests/test_storyboard_schema.py (schema embedded as Python validator module; loader handles str|Path env conventions too? no—only schema+load). Acceptance: intro sample valid; malformed lists ALL problems typed StoryboardError.
B2 compiler core + golden parity tests (25-section fixture referencing repo-relative test assets → 76/50/177.53±0.5; counts/order/normalized-hash compare) + ffprobe duration probing.
B3 CLI (validate|compile [--vo-align F] [--render]) + managed imports wired + integration tests: preflight-before-write; create→CAS-save→version bump; rerun byte-equality of saved config+registry.
B4 author storyboards/astrid-intro.storyboard.json from today's artifacts (plan.json texts/slugs + pyramid prompts + final-slides image paths); validate.
B5 intro application sequence (all saves target NEW managed timeline slug `storyboard-intro`; `main` remains untouched):
  1. compile(--vo-align plan.json) with all sections active_index=0 (final-html images) → managed imports (25 png + 25 wav = 50 assets) → save v1. Parity assert: 25/76/177.53±0.5.
  2. ex_glitch regeneration proof: sdk.invoke('generation.generate_image', flux-schnell, glitch prompt) → kernel run manifest records the paid generation → MediaService.import_file(output png) → append AUTHORED variant {source:"gen", prompt:<same glitch prompt>, label:"regen-glitch", alt_render_path:<fal png>, gen_kernel_run_id:<run_id from manifest>} → set ex_glitch active_index to it → save v2. Transient asset count 51 is expected and asserted.
  3. flip back: remove the regen-glitch authored variant and restore active_index=0 → save v3; assert config+registry byte-equal to the step-1 snapshot (excluding version metadata) → proves flip independence without drift.
     (The regeneration evidence persists in Batch 5 artifacts: kernel run manifest + imported managed media row remain in the kernel/CAS regardless of storyboard reversion.)
  4. render `storyboard-intro` latest version → OCR spot-checks(open,idea1_vc,cta_agents) → evidence matrix. Clip-count invariant stays exactly 76 per version because flips change only WHICH image resolves for one section, never clip structure.
B6 docs(README snippet)+final oracle review(≤3 passes: 1 GLM pass + grok synthesis)+push branch megado/oracle-run-storyboard+report.

## Validation commands
- validate/compile/render commands above against ASTRID_PROJECTS_ROOT=/Users/peteromalley/Documents/reigh-workspace/astrid-intro-projects
- pytest tests/test_storyboard_schema.py
Estimate ≤1 week ⇒ no huge-run policy.

Note: where this plan references batch gates, batches are B1..B6 (B0 folded into B2).
