# Output/Result contract M2 — exemption burndown (the long tail)

## Outcome
The M1 exemption list shrinks to only the principled entries (genuinely no-artifact, GPU-only, or paid-API executors with documented reasons); every other artifact-writing executor emits a conformant manifest. Reviewer checks: the M1 gate passes with the final exemption list, and each remaining exemption carries a one-line reason.

## Context
M1 (same directory) landed write_manifest(), the full-registry gate, and the core families (understanding, generate_image_openai, editorial core, training pool_build, scene_describe). This milestone is mechanical adoption using M1's choke point and patterns — the contract decisions are already made.

## Scope (the review-measured long tail, ~15+ executors)
editorial: triage, arrange, quality_zones, boundary_candidates, validate, refine, editor_review, human_review, human_notes, inspect_cut, script_pipeline (verify each actually writes artifacts; no-artifact verbs become reasoned exemptions instead).
iteration: assemble (6 declared outputs), prepare.
rendering: render, sprite_sheet, html_canvas_effect.
comfy_wrap.run (writes output.png), vibecomfy.run, video_editing.cut, media.clip_extract, moirae, fal.fal_foley, reigh.spatial_audio_page, reigh.reigh_data, youtube.youtube_audio.

## Locked decisions
M1's manifest schema and write_manifest() API are FROZEN inputs — any change they need is a defect report against M1, not a drive-by edit. Exemptions that survive must each state why (no artifact / GPU / paid). Tests offline per family (fake backends), under tmp_path.

## Done criteria
Gate green with final exemption list; exemption count reduced from M1's initial list to only-reasoned entries; no executor writes file artifacts without a manifest or a reason.

## Anti-scope
No schema changes, no CLI/SDK work, no new executor features — adoption only.
