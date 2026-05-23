Push forward the Astrid built-in training cleanup chain.

Repository: /Users/peteromalley/Documents/reigh-workspace/Astrid-builtin-training-chain

Primary artifacts:
- docs/megaplan/epics/builtin-training/chain.yaml
- docs/megaplan/epics/builtin-training/briefs/
- docs/megaplan/epics/builtin-training/CONTRACTS.md  ← M0 handoff
- docs/megaplan/epics/builtin-training/PLACEMENT.md   ← M0 handoff
- docs/megaplan/epics/builtin-training/FIXTURES.md    ← M0 handoff

Locked IDs (M0):
- Dataset builder: builtin.dataset_build
- Training runner: builtin.training_run
- Creative writing/script pipeline: builtin.script_pipeline
- builtin.lora_train is NOT a generic built-in id.

Contract artifact paths (M0 handoff — cite these from M1-M4):
- CONTRACTS.md (master contract — all sections)
- contracts/interfaces.py (Python Protocols — single handoff location)
- contracts/schemas/*.json (JSON Schema files for all shapes)
- contracts/schema-version-parser-policy.md (parser behavior)
- contracts/fixtures/*.json (fixture JSON files, parser vectors, caption sidecars)
- PLACEMENT.md (module/file ownership map)
- FIXTURES.md (fixture strategy, paths, expected outputs)

Current-vs-target distinction (M0 verified):
- Current builtin.human_review: full /data.json, full-state overwrite POST /save,
  token-protected /save /submit /state.json on 127.0.0.1.
- Target (new M1/M2 work): paginated data reads, diff-based saves with
  base_state_version, stale-save detection, batch submit.

AI-Toolkit adapter requirement (M0):
- Training preflight expects flat clips[] with clip_file/path, clip_id,
  and sibling <clip_id>.caption.json sidecars.
- Canonical manifest (manifest.schema.json) is separate from the
  ai-toolkit adapter export (ai-toolkit-adapter-manifest.schema.json).

Seinfeld deletion policy (M0):
- astrid/packs/seinfeld/ is deleted by M4 after examples/presets exist.
- seinfeld.dataset_build → example config for builtin.dataset_build.
- seinfeld.lora_train → example config for builtin.training_run.
- seinfeld.script_pipeline → preset config for builtin.script_pipeline.
- No compatibility shim lives in the Seinfeld pack.
- Any temporary shim must live outside astrid/packs/seinfeld/ and be removed by M4.

Registry surface audit (M0 verified):
- EXISTS: seinfeld.dataset_build, seinfeld.lora_train, seinfeld.script_pipeline,
  builtin.human_review, builtin.youtube_audio, builtin.scenes,
  builtin.visual_understand, builtin.video_understand, builtin.transcribe.
- MISSING: builtin.clip_extract — do not treat as existing.
- ADJACENT: builtin.audio_understand, builtin.understand (exist, not in 10 requested).

Schema policy (M0):
- New configs: schema_version: 1 and media_type: video required.
- Missing schema_version: parse as v1 with deprecation warning (compat only).
- Future schema_version > 1: fail with parseable validation error.
- Unknown keys: fail unless under extensions object.
- Parser policy: contracts/schema-version-parser-policy.md + fixture vectors.

Current intent:
- Turn the Seinfeld-specific training/data prototype into generic built-ins.
- End state: builtin.dataset_build, builtin.training_run, builtin.script_pipeline,
  examples/presets for Seinfeld and Always Sunny, and no astrid/packs/seinfeld directory.
- Preserve useful behavior by moving it to generic homes; do not leave generic
  infrastructure under Seinfeld.

Every wake-up:
1. Read CONTRACTS.md, PLACEMENT.md, FIXTURES.md for locked decisions.
2. Inspect repo state and the builtin-training chain/briefs.
3. Push the work forward safely. Prefer concrete implementation, plan validation,
   tests, or Megaplan chain execution over more discussion.
4. Do not revert unrelated user work. There is a dirty worktree; treat unknown
   changes as user work.
5. Do not start another wake-up loop.
6. If work is complete or truly blocked on human-only input, stop this loop with:
   pkill -f "wakeup_loop.sh.*builtin_training"

Useful checks:
- python3 - <<'PY'
  import yaml
  from pathlib import Path
  data = yaml.safe_load(Path('docs/megaplan/epics/builtin-training/chain.yaml').read_text())
  print('milestones', len(data['milestones']))
  for m in data['milestones']:
      assert Path(m['idea']).exists(), m['idea']
      print(m['label'])
  PY
- rg -n "seinfeld|builtin.dataset_build|builtin.training_run|script_pipeline" docs/megaplan/epics/builtin-training astrid/packs tests
- rg -n "builtin.clip_extract" docs/megaplan/epics/builtin-training  # must show MISSING status

Report tersely at the end of each wake-up: what changed, what was verified, and what remains.
