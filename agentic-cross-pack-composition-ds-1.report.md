# Agentic Cross-Pack Composition — Discovery Report (v13)

## 1. What you did

I attached to project `agentic-cross-pack-composition-ds-1`, discovered the
tool surface through the canonical CLI (`executors list`, `orchestrators list`,
`orchestrators inspect`), confirmed that `builtin.hype` already contains
`builtin.transcribe` as its first child executor, and invoked a **single**
`builtin.hype` orchestrator run — not two separate invocations.

**Chronological commands:**

1. `python3 -m astrid attach agentic-cross-pack-composition-ds-1` — bound
   session (idempotent re-attach to existing session).
2. `python3 -m astrid executors list` — surfaced `builtin.transcribe` (and 45+
   other executors). **Not invoked separately.**
3. `python3 -m astrid orchestrators list` — surfaced `builtin.hype` with short
   description "transcribe → cut → render → validate", heavily hinting at the
   composition.
4. `python3 -m astrid orchestrators inspect builtin.hype` — **definitive**:
   `builtin.transcribe` listed first of 15 `child_executors`. This is the
   canonical composition proof. No code-reading required.
5. Read `astrid/packs/builtin/hype/STAGE.md` — 3 lines, zero composition info.
6. Read `astrid/packs/builtin/transcribe/STAGE.md` — 3 lines, zero composition
   info.
7. Verified placeholder video existed at `/tmp/placeholder.mp4` (5866 bytes,
   2-second silent clip from prior run) and brief at
   `/tmp/hype-composition-test/brief.txt`.

**Invocation (single command, canonical CLI):**

```
python3 -m astrid orchestrators run builtin.hype \
  --out /tmp/hype-composition-test/out-v13 -- \
  --video /tmp/placeholder.mp4 \
  --brief /tmp/hype-composition-test/brief.txt \
  --out /tmp/hype-composition-test/out-v13
```

**Result:** Pipeline ran `transcribe` → `scenes` → `quality_zones` → `shots`
→ `triage` → `scene_describe` → `quote_scout` (failed there with
`BadRequestError: messages.0: user messages must have non-empty content` —
expected, since a 2-second silent clip produces an empty transcript that Claude
rejects). `transcript.json` was produced: `{"segments": []}`. `transcribe.log`
confirms: `chunks=2 skipped_silent=2 segments_kept=0`.

**Composition decision: one command, not two.** `builtin.hype` internally ran
`builtin.transcribe` as stage 0 of 15. No separate `builtin.transcribe`
invocation was made or needed. The canonical CLI surface (`astrid orchestrators
run`) was used exclusively — no `astrid.packs.*` bypass.

## 2. What tools you discovered

**Executors surfaced (via `astrid executors list`):**
- `builtin.transcribe` — "Transcribe source audio to transcript.json via
  Whisper." Standalone executor. **Not invoked separately** because
  `orchestrators inspect` confirmed it is child executor 0 of 15 inside
  `builtin.hype`.
- 45+ other executors (`builtin.scenes`, `builtin.cut`, `builtin.render`,
  `builtin.validate`, `builtin.quote_scout`, etc.) — all irrelevant to the
  separate-invocation question, all discarded.

**Orchestrators surfaced (via `astrid orchestrators list`):**
- `builtin.hype` — "Run the canonical hype editing pipeline end-to-end
  (transcribe → cut → render → validate)." **Invoked once**, via
  `astrid orchestrators run`. The short description already signals transcribe
  is included.
- 9 other orchestrators (`builtin.event_talks`, `builtin.iteration_video`,
  `builtin.thumbnail_maker`, `builtin.vary_grid`, `builtin.logo_ideas`,
  `builtin.animate_image`, `builtin.foley_map`, `seinfeld.dataset_build`,
  `seinfeld.lora_train`) — all irrelevant, all discarded.

**Composition discovery tools, ranked by usefulness:**
1. `orchestrators inspect builtin.hype` — **definitive.** `child_executors`
   field lists all 15 stages with `builtin.transcribe` at index 0.
2. `orchestrators list` short description — **strong hint.** "transcribe → cut
   → render → validate" makes the inclusion obvious to an attentive agent.
3. `run.py` STEP_ORDER — unambiguous but requires source-code reading. Should
   not be necessary.
4. `author explain builtin.hype` — **actively misleading.** Shows a DSL
   smoke-test fixture (noop + attest verdicts) instead of the 15-stage
   production pipeline. A programmatic scraper or skimming agent would conclude
   transcribe is NOT included and would double-run.
5. STAGE.md files — **complete gap.** Both are 3 lines with zero composition
   information.

## 3. Discoverability notes

**STAGE.md is the biggest discoverability failure.** Both `hype/STAGE.md` and
`transcribe/STAGE.md` are exactly 3 lines each, describing what the tool *is*
(e.g., "Built-in Astrid orchestrator for the canonical hype editing workflow")
but containing zero information about what it *contains*. An agent whose
workflow is "read STAGE.md, then invoke" would have no way to know transcribe
is already inside hype and would almost certainly run both. This is the
single most dangerous gap because STAGE.md is the natural first read for
discoverability — the doc literally has "STAGE" in the filename, implying it
describes pipeline stages, yet it describes none.

**`orchestrators inspect` is the definitive source but requires an extra step.**
The `child_executors` list in the inspect output is unambiguous —
`builtin.transcribe` is item 0 of 15. Any agent workflow that includes
`inspect` before `run` will see this and avoid double-running. The open
question is whether agent workflows routinely include `inspect` or skip
straight to `run`. The v13 workflow included `inspect` explicitly; many agents
would not.

**The `orchestrators list` short description is a strong hint but is human
prose, not structured data.** "transcribe → cut → render → validate" makes the
inclusion obvious to an attentive human reader. But it uses verb forms
("transcribe"), not executor IDs (`builtin.transcribe`). An agent parsing this
would need to fuzzy-match arrow-separated words to executor IDs — fragile and
error-prone.

**`author explain` is a trap for folder-orchestrator packs.** When a pack has
both a DSL plan and a folder orchestrator (like `builtin.hype`), `author
explain` shows the DSL plan — a smoke-test fixture bearing no resemblance to
the production pipeline. An agent that runs `author explain builtin.hype`
before deciding what to invoke would see a noop + attest verdicts and conclude
transcribe is not included. This is a critical discoverability anti-pattern.

**Would a less-careful agent have run both?** Yes, with high probability.
Three plausible failure modes:
1. **STAGE-only agent**: reads STAGE.md for both tools (no composition info),
   invokes both. Double-run.
2. **Explain-then-run agent**: runs `author explain` (sees smoke-test fixture
   with no transcribe), invokes both. Double-run.
3. **Search-and-run agent**: searches for "transcribe" (finds
   `builtin.transcribe`), searches for "hype" (finds `builtin.hype`), invokes
   both without inspecting. Double-run.

Only the `inspect`-first workflow prevents this reliably — and that workflow
is not documented or enforced anywhere.

## 4. Biggest UX gap

**STAGE.md must declare child stages.** The single change that would most
reduce the risk of double-running is requiring every orchestrator's STAGE.md
to list its child executor IDs or full stage graph. If `hype/STAGE.md`
contained even one line like:

```
Stages: builtin.transcribe → builtin.scenes → builtin.quality_zones →
builtin.shots → builtin.triage → builtin.scene_describe →
builtin.quote_scout → builtin.pool_build → builtin.pool_merge →
builtin.arrange → builtin.cut → builtin.refine → builtin.render →
builtin.editor_review → builtin.validate
```

...any agent reading the doc would immediately know that invoking `builtin.hype`
covers `builtin.transcribe`. This is a one-line addition with outsized impact —
no new CLI surface, no schema changes, just a documentation convention enforced
by pack authoring. It's also the most natural place for an agent to look: a
file called STAGE.md that currently describes zero stages.

**Secondary gap: `author explain` is a trap for dual-representation packs.**
When a pack has both a DSL plan and a folder orchestrator, `author explain`
shows the DSL plan (smoke-test fixture) instead of the production pipeline.
Either the production pipeline should have a DSL plan that mirrors the folder
orchestrator's stage graph, or `author explain` should refuse to show the DSL
plan when a folder orchestrator exists and redirect to `orchestrators inspect`.

**Tertiary gap: `orchestrators list` needs structured stage data.** The short
description uses prose ("transcribe → cut → render → validate") rather than
structured executor IDs. Adding a `stages: [builtin.transcribe, builtin.cut,
builtin.render, builtin.validate]` field to the list output would make
composition machine-discoverable without requiring a separate `inspect` call
per orchestrator.
