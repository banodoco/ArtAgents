# Agentic Vague Video Request — Discovery Report (v11, canonical CLI only)

## 1. What you did

Attached to project `agentic-vague-video-request-ds-1` (initial attempt with
`projects attach` failed — the correct subcommand is `projects default` or the
session auto-resolves from `.astrid-session`). Listed orchestrators via
`astrid orchestrators list` and immediately spotted `builtin.hype` with the
description "Run the canonical hype editing pipeline end-to-end (transcribe →
cut → render → validate)." The name "hype" matched the user's request for a
"hype cut" directly, so no searching through unrelated orchestrators was
needed.

Inspected the orchestrator with `astrid orchestrators inspect builtin.hype`,
which confirmed a 15-step pipeline (transcribe, scenes, quality_zones, shots,
triage, scene_describe, quote_scout, pool_build, pool_merge, arrange, cut,
refine, render, editor_review, validate). The inspect output pointed to
`python3 -m astrid.packs.builtin.hype.run --help` for argument discovery, but
that path is blocked by the canonical entrypoint guard. Instead, read
`run.py` source directly to surface the required args (`--out`, `--brief`,
optional `--video`). The STAGE.md was only 3 lines — effectively a stub.
Discovered that `--project` and `--out` are mutually exclusive (the project
flag auto-derives the output directory), which was only learnable through
trial and error since no doc surfaces this constraint.

No source video was staged, so synthesized a 1-second silent MP4 placeholder
with ffmpeg and wrote a brief.txt describing a 30-second "AI creativity
unleashed" hype reel. Invoked the orchestrator via the canonical CLI surface:
`astrid orchestrators run builtin.hype --project agentic-vague-video-request-ds-1
-- --video /tmp/hype_run/placeholder.mp4 --brief /tmp/hype_run/brief.txt`. The
orchestrator executed 6 of 15 steps successfully (transcribe, scenes,
quality_zones, shots, triage, scene_describe), producing a full artifact tree
with transcript.json, scenes.json, quality_zones.json, shots.json,
scene_triage.json, scene_descriptions.json, scene keyframes, audit ledger,
and LLM debug traces. It failed at step 7 (quote_scout) because the silent
placeholder video produced an empty transcript, which caused an empty user
message to the Claude API — an expected and architecturally correct failure
for placeholder media.

## 2. What tools you discovered

**`builtin.hype` (orchestrator)** — surfaced by `astrid orchestrators list` as
the third entry with the description "Hype Pipeline: Run the canonical hype
editing pipeline end-to-end (transcribe → cut → render → validate)." The name
"hype" is a direct keyword match for the user's request ("trailer, sizzle
reel, hype cut"), making this an unambiguous discovery. The inspect output
revealed 15 child executors and the full step order.

**Child executors** — `astrid orchestrators inspect builtin.hype` listed all
15 child executors explicitly in the `child_executors` field: builtin.transcribe,
builtin.scenes, builtin.quality_zones, builtin.shots, builtin.triage,
builtin.scene_describe, builtin.quote_scout, builtin.pool_build,
builtin.pool_merge, builtin.arrange, builtin.cut, builtin.refine,
builtin.render, builtin.editor_review, builtin.validate. Separately confirmed
each exists via `astrid executors list`, which also surfaced related tools
like `builtin.inspect_cut` (for inspecting rendered cuts) and
`builtin.boundary_candidates` (for visual scene-boundary review).

**`astrid next`** — the universal port-of-call listed `builtin.hype` among
its suggested orchestrators but ranked it 7th, behind six text-digest
orchestrators. While it was discoverable, the ranking didn't reflect the
user's video-focused intent, suggesting the recommender doesn't weight
orchestrator keywords against the task description.

## 3. Discoverability notes

What felt obvious: the `orchestrators list` output made `builtin.hype`
immediately recognizable. The name is a perfect keyword match for "hype cut,"
and the short description ("transcribe → cut → render → validate") instantly
confirmed it was the canonical pipeline for this kind of work. The child
executor list in `inspect` gave a clear mental model of the 15-step workflow
without needing to read any source code.

What didn't feel obvious: argument discovery was the biggest friction point.
The `inspect` output's instruction to run `python3 -m astrid.packs.builtin.hype.run
--help` is a circular dead-end — the entrypoint guard blocks that invocation
by design. The STAGE.md was only 3 lines with no argument documentation. This
forced reading 500+ lines of `run.py` to surface the argument parser, which
is fragile (the parser could change) and time-consuming. The mutual exclusion
between `--project` and `--out` was undocumented anywhere; I only discovered
it through a failed invocation. The skill doc (SKILL.md) never triggered
during this flow — it's a general agent guide, not a per-orchestrator
reference.

The empty STAGE.md is a missed opportunity. A 5-10 line doc showing the
canonical invocation with `--video`, `--brief`, and the project-managed
output pattern would have saved the source-dive. Similarly, `orchestrators
inspect` could surface a `required_args` or `usage` field instead of
delegating to a blocked `--help` path.

## 4. Biggest UX gap

The single biggest UX gap is that `orchestrators inspect` points agents to a
blocked help path (`python3 -m astrid.packs.builtin.hype.run --help`) with no
fallback. Every orchestrator's inspect output includes the line `# discover
pack args: python3 -m astrid.packs.<id>.run --help`, but the canonical
entrypoint guard in every run.py blocks direct module invocation. This
creates a reliable dead-end: the tool tells you to do something that the tool
itself prevents. Fixing this requires either (a) surfacing the full argument
signature directly in the inspect output (a `signature` or `args` field
parsed from the argparse definition), or (b) providing a whitelisted
`--help` passthrough in the guard that allows help-only invocations, or (c)
populating STAGE.md with the canonical invocation examples so agents never
need the help flag. Option (a) is the most robust — it eliminates the
source-dive entirely and works even when STAGE.md is a stub.
