Push forward the Astrid pack-first capability system epic.

Repository: /Users/peteromalley/Documents/reigh-workspace/Astrid

Primary artifacts:
- docs/megaplan/epics/pack-system/chain.yaml
- docs/megaplan/epics/pack-system/briefs/

Current intent:
- Make every discoverable capability belong to a pack.
- Some packs are enabled by default and feel built-in.
- Personal, example, deprecated, and adapter capabilities use the same pack mechanism but are filtered from normal agent discovery unless enabled.
- Preserve agent discoverability through manifest-driven list/search/inspect.
- Treat `Capability` / `CapabilityHandle` as the unifying abstraction for executors, orchestrators, and elements; do not force one shared registry implementation unless the codebase naturally wants it.
- Prefer forks/overrides and agent-assisted update reconciliation over in-place user edits to default packs.
- Reuse existing pack scaffolding, validation, discovery, and element fork behavior before inventing new machinery.
- Do not move public ids before alias/deprecation infrastructure exists.
- Treat safety/cost/permission metadata as part of the core pack contract, not a late add-on.
- Keep alias, fork, override, and in-place edit as distinct concepts.
- Coordinate file moves with builtin-training and timeline-event-sourcing work before moving shared pack/workflow files.
- Keep M0 thin. Defer remote registry, dependency isolation, rich capability graph planning, and semantic merge/update intelligence unless a concrete implementation blocker requires them.

Milestone shape:
1. Thin pack contract.
2. Capability identity and aliases.
3. Unified layout and discovery.
4. Pack migration and cleanup.
5. Forks, overrides, and agent updates.
6. Integration, docs, and an agent discovery proof.

Every wake-up:
1. Inspect repo state and the pack-system chain/briefs.
2. Push the current milestone forward safely.
3. Do not revert unrelated user work. This repo may be dirty; treat unknown changes as user work.
4. Do not start another wake-up loop.
5. If complete or blocked on human-only input, stop the loop with:
   pkill -f "wakeup_loop.sh.*pack_system"

Useful checks:
- python3 - <<'PY'
  import yaml
  from pathlib import Path
  data = yaml.safe_load(Path('docs/megaplan/epics/pack-system/chain.yaml').read_text())
  print('milestones', len(data['milestones']))
  for m in data['milestones']:
      assert Path(m['idea']).exists(), m['idea']
      print(m['label'])
  PY
- python3 -m astrid executors list
- python3 -m astrid orchestrators list
- python3 -m astrid elements list

Report tersely: what changed, what was verified, and what remains.
