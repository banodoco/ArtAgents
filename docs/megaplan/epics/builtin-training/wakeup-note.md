Push forward the Astrid built-in training cleanup chain.

Repository: /Users/peteromalley/Documents/reigh-workspace/Astrid

Primary artifacts:
- docs/megaplan/epics/builtin-training/chain.yaml
- docs/megaplan/epics/builtin-training/briefs/

Current intent:
- Turn the Seinfeld-specific training/data prototype into generic built-ins.
- End state: builtin.dataset_build, builtin.training_run, a generic creative-writing/script built-in, examples/presets for Seinfeld and Always Sunny, and no astrid/packs/seinfeld directory.
- Preserve useful behavior by moving it to generic homes; do not leave generic infrastructure under Seinfeld.

Every wake-up:
1. Inspect repo state and the builtin-training chain/briefs.
2. Push the work forward safely. Prefer concrete implementation, plan validation, tests, or Megaplan chain execution over more discussion.
3. Do not revert unrelated user work. There is a dirty worktree; treat unknown changes as user work.
4. Do not start another wake-up loop.
5. If work is complete or truly blocked on human-only input, stop this loop with:
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

Report tersely at the end of each wake-up: what changed, what was verified, and what remains.
