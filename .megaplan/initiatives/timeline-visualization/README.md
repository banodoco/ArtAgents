# Durable Timeline Visualization

Implement an agent-only Astrid inspection journey from project overview to
segment, clip context, exact original media, and transcript/text evidence. The
surface must support proportional and readable-linear timeline layouts,
snapshot-safe drill-down, executable next actions, and repeated VLM
comprehension testing.

## Prep decision

- Delivery shape: two-milestone megaplan epic.
- Estimated human effort: 15–22 focused engineering days.
- Overall plan difficulty: 4/5.
- Selected profile: `partnered-4` for both milestones.
- Required score record: **Overall plan difficulty: 4/5; selected profile:
  `partnered-4`; because:** local rendering success is insufficient—the public
  CLI, frozen snapshot, stable-id navigation, original-media integrity,
  transcript mapping, cross-format geometry, and VLM-evaluation contracts must
  remain coherent end to end.
- Planning complexity: `full`.
- Depth: `high`.
- Vendor: `codex`.
- Shorthand: `partnered-4/full/high @codex`.
- Prep phase: complete; the architecture survey and agent-UX audit are durable.
- Feedback phase: off; not requested.
- Execution isolation: use one dedicated chain worktree and carry the current
  source state, because the Astrid checkout contains relevant uncommitted
  `timeline_storyboard` baseline work.

## Milestones

1. `m1-navigation-spine` — build the semantic/layout models, evidence pack,
   snapshot-safe action graph, CLI, and journey through verified original
   media. It writes the implemented navigation contract consumed by milestone
   two.
2. `m2-source-text-vlm` — add provenance-correct transcript/text mapping,
   integrity/freshness adversarial fixtures, and iterative VLM proof of the
   complete overview-to-source journey without redesigning milestone one's
   contracts.

## Durable inputs

- [North Star](NORTHSTAR.md)
- [Overall locked brief](briefs/timeline-visualization.md)
- [Milestone 1 brief](briefs/m1-navigation-spine.md)
- [Milestone 2 brief](briefs/m2-source-text-vlm.md)
- [Architecture and UX decisions](decisions/timeline-visualization-plan.md)
- [Chain spec](chain.yaml)

## Prepared launch

Run from the Astrid repository:

```bash
/Users/peteromalley/Documents/Arnold/.venv/bin/python \
  -m arnold_pipelines.megaplan chain start \
  --spec .megaplan/initiatives/timeline-visualization/chain.yaml \
  --in-worktree timeline-visualization \
  --carry-dirty \
  --no-git-refresh \
  --no-push
```

Do not use `--clean-worktree`: the current visualization preparation and
`timeline_storyboard` work are part of the implementation baseline.

Launch this inside a subagent by default so the chain's planning, execution,
and validation chatter stays outside the coordinating conversation. Automatic
milestone progression is deliberate; `--no-push` keeps the resulting source
state local for review after both milestones and their image/VLM evidence are
complete.
