# Milestone 4: Pack Deletion, Examples, and Documentation

## Outcome

Move every remaining useful Seinfeld-pack capability into generic built-in homes or examples, document the workflow, and delete `astrid/packs/seinfeld/`.

## Scope

In scope:

- Add a Seinfeld example config that reproduces the existing two-bucket dataset behavior through the built-in dataset pipeline.
- Add an Always Sunny / Charlie conspiracy example config using the local run as reference material.
- Extract `seinfeld.script_pipeline` into a generic built-in creative-writing/script module.
  - The generic module should preserve the useful pipeline shape: parallel rough attempts, synthesis pass, voice/style pass, optional judge/select-best pass, markdown outputs, and manifest.
  - Seinfeld-specific writing rules, prompts, callbacks, and laugh-tag policy become a preset/example config, not built-in code.
  - The new built-in id is the one locked in M0.
- Document the end-to-end flow:
  - build dataset
  - review candidates
  - finalize manifest
  - run training
  - review checkpoint grid
  - register chosen artifact
- Remove or replace `seinfeld.dataset_build`, `seinfeld.lora_train`, and `seinfeld.script_pipeline` with documented generic commands. If compatibility shims are required, they must not require keeping `astrid/packs/seinfeld/`.
- Add migration notes for existing `runs/seinfeld-dataset` artifacts where practical.
- Move or archive Seinfeld-specific vocabulary, caption schemas, bucket definitions, training plans, RunPod notes, and quality docs into example/docs locations according to the M0 placement map.
- Audit Seinfeld training/dataset docs and manifests for stale prototype references, especially references to nonexistent or superseded tools such as `seinfeld.youtube_search`, `seinfeld.dataset_manifest`, direct guarded module execution, or Seinfeld-local generic review assets.
- Regenerate capability indexes and skill/agent docs after any renames, wrappers, or deprecations.
- Reconcile the final tree against the M0 placement map and either move misplaced generic code or document why the chosen home changed.
- Delete `astrid/packs/seinfeld/` once all useful components have moved or been intentionally archived.

Out of scope:

- Implementing additional trainer adapters.
- Large-scale migration of all historical run artifacts.
- New dataset source providers beyond the config shape already introduced.
- Building a general-purpose fiction IDE; the script module should be a reusable batch writing pipeline, not a full writing product.

## Locked Decisions

- Seinfeld is an example/preset, not a pack and not the generic engine.
- Always Sunny is a second example config to prove the abstraction is not Seinfeld-specific.
- Documentation should show canonical Astrid commands, not guarded direct module execution.
- The Always Sunny example should exercise at least one meaningful difference from Seinfeld, such as a single behavior bucket, different caption prompt, or direct URL source list, without code changes to the built-in orchestrators.
- The end state is no registered `seinfeld.*` tools and no `astrid/packs/seinfeld/` directory.

## Open Questions

- Exact location for example configs: `examples/training/`, pack-local examples, or both.
- Whether old Seinfeld command ids should be replaced by one-release migration commands outside the removed pack, or only documented.
- How much historical artifact compatibility is worth preserving.
- Exact generic id for the creative-writing/script module, if M0 does not settle on the suggested name.

## Constraints

- Do not delete existing Seinfeld pack code until every useful component has a generic/example/archive destination and migration docs are present.
- Keep examples lightweight and safe to run in smoke/dry-run mode.
- Do not commit source media or generated videos.

## Done Criteria

- Seinfeld dataset/training documentation points to the built-in pipeline.
- Seinfeld pack docs no longer present stale prototype-only executors as planned/current workflow.
- The final code/docs layout matches the M0 placement map, or the deviation is explicitly documented in migration notes.
- A generic built-in creative-writing/script pipeline exists and can run the former Seinfeld behavior through a preset/example without code under `astrid/packs/seinfeld/`.
- Always Sunny config exists as a runnable example for dataset review in dry-run/local-fixture mode.
- The Always Sunny example proves a non-Seinfeld config works without code changes to `builtin.dataset_build`.
- Old Seinfeld entrypoints are removed or replaced by migration commands that do not require keeping the Seinfeld pack.
- `astrid/packs/seinfeld/` no longer exists.
- `tests/packs/seinfeld/` is removed or migrated to generic builtin/example test locations.
- The `astrid/packs/seinfeld/script_pipeline/run.py` raw-urllib allowlist entry in `tests/test_no_duplicate_http.py` is removed or replaced by a generic built-in entry that satisfies the repository's HTTP-client policy.
- Capability indexes and AGENTS/SKILL docs contain no `seinfeld.*` capabilities.
- Capability index and relevant AGENTS/SKILL docs are updated.
- Tests or smoke commands prove example configs parse and reach expected dry-run outputs.

## Touchpoints

- `astrid/packs/seinfeld/` as the source to empty/delete.
- Built-in dataset/training orchestrators from prior milestones.
- New generic built-in creative-writing/script module.
- Generic review UI location.
- `examples/`
- `docs/`
- `SKILL.md` capability index generation.

## Anti-Scope

- Do not broaden into a full dataset marketplace.
- Do not add cloud orchestration unless already supported by the generic training-run flow.
