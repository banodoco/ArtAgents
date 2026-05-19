# Agentic Cross-Pack Composition — Discovery Report (v10, canonical CLI only)

## 1. What you did

I attached to project `agentic-cross-pack-composition-ds-1`, discovered the
tool surface via canonical CLI surfaces, confirmed that `builtin.hype` already
contains `builtin.transcribe` as its first child stage, and invoked a single
`builtin.hype` orchestrator run — not two separate invocations.

**Discovery commands (chronological):**

1. `python3 -m astrid orchestrators list` — surfaced `builtin.hype` with
   short description "transcribe → cut → render → validate", hinting at the
   composition immediately.
2. `python3 -m astrid executors list` — confirmed `builtin.transcribe` exists
   as a standalone executor ("Transcribe source audio to transcript.json via
   Whisper").
3. `python3 -m astrid orchestrators search hype` — returned `builtin.hype`
   with the same description, score 36.75.
4. `python3 -m astrid orchestrators search transcribe` — returned
   `builtin.hype` (score 15.00), confirming the search engine knows transcribe
   is associated with hype.
5. `python3 -m astrid orchestrators inspect builtin.hype` — revealed the full
   `child_executors` list: `builtin.transcribe` first of 15. This is the
   definitive evidence of composition.
6. Read `astrid/packs/builtin/hype/STAGE.md` — 3 lines, no composition info.
7. Read `astrid/packs/builtin/transcribe/STAGE.md` — 3 lines, no composition
   info.
8. Read `astrid/packs/builtin/hype/run.py` (lines 42-58) — revealed
   `STEP_ORDER` tuple with "transcribe" as step 0 of 15.
9. `python3 -m astrid author explain builtin.hype` — showed a **misleading**
   DSL smoke-test fixture (noop + 10 attest verdicts), NOT the production
   pipeline. The tool itself prints a warning about this.
10. Synthesized a placeholder brief at `/tmp/hype-composition-test/brief.txt`.

**Invocation (dry run):**

```
python3 -m astrid orchestrators run builtin.hype \
  --out /tmp/hype-composition-test/out --dry-run -- \
  --video /tmp/placeholder.mp4 \
  --brief /tmp/hype-composition-test/brief.txt \
  --out /tmp/hype-composition-test/out
```

Output: `/usr/local/bin/python3 -m astrid.packs.builtin.hype.run --video ... --brief ... --out ...`
— a single invocation. No separate transcribe command.

**Invocation (real run):**

```
python3 -m astrid orchestrators run builtin.hype \
  --out /tmp/hype-composition-test/out -- \
  --video /tmp/placeholder.mp4 \
  --brief /tmp/hype-composition-test/brief.txt \
  --out /tmp/hype-composition-test/out
```

Result: Pipeline ran through `transcribe` → `scenes` → `quality_zones` → `shots`
→ `triage` → `scene_describe` → `quote_scout` (failed there due to empty
transcript from 2-second silent placeholder). `transcript.json` was produced
(empty segments, as expected for silent video). `transcribe.log` confirms:
"chunks=2 skipped_silent=2 segments_kept=0".

**Composition decision: one command, not two.**

## 2. What tools you discovered

**Executors surfaced (via `executors list`):**
- `builtin.transcribe` — standalone transcription via Whisper. Score 36.75 in
  search. I read its STAGE.md and recognized it as a stage within hype. **Not
  invoked separately.**

**Orchestrators surfaced (via `orchestrators list`):**
- `builtin.hype` — the canonical hype editing pipeline. Short description
  "transcribe → cut → render → validate" already signals the composition.
  Score 36.75 for "hype" search, score 15.00 for "transcribe" search.

**Other orchestrators discarded:**
- `builtin.event_talks`, `builtin.iteration_video`, `builtin.thumbnail_maker`,
  `builtin.vary_grid`, `builtin.logo_ideas`, `builtin.animate_image`,
  `builtin.foley_map`, `seinfeld.dataset_build`, `seinfeld.lora_train` — all
  irrelevant to the ask.

**Which I invoked:** Only `builtin.hype`, once, via `astrid orchestrators run`.
I did NOT invoke `builtin.transcribe` separately, because `orchestrators
inspect` confirmed it is a child executor of `builtin.hype`, and the dry run
and real run both confirmed the pipeline handles transcription internally.

## 3. Discoverability notes

**Short description is a strong hint but not proof.** `orchestrators list`
describes hype as "transcribe → cut → render → validate". An attentive agent
would suspect composition from this alone. However, the description uses
verbs (transcribe, cut, render, validate) not executor IDs, so a less-careful
agent might not make the connection that these map to named executors.

**`orchestrators inspect` is the definitive source.** The `child_executors`
field lists all 15 stages by their executor IDs, with `builtin.transcribe`
first. Any agent that runs `inspect` before invoking will see the composition
unambiguously. The question is whether agents routinely `inspect` before
running.

**STAGE.md is a gap.** Both `hype/STAGE.md` and `transcribe/STAGE.md` are
exactly 3 lines with zero composition information. They say what the
tool *is* ("Built-in Astrid orchestrator for the canonical hype editing
workflow") but not what it *contains*. An agent whose workflow is "read
STAGE.md, then invoke" would have no way to know transcribe is already inside
hype and would almost certainly run both.

**`author explain` is actively misleading.** It shows a DSL smoke-test
fixture (noop + 10 attest verdicts like `final_verdict`, `closing_verdict`,
`terminal_verdict`, `ultimate_verdict`, `concluding_verdict`, etc.) instead
of the 15-stage production pipeline. The tool prints a note: "the DSL plan
below is a smoke-test fixture and does NOT reflect the folder-orchestrator's
stage graph." But an agent that doesn't read the note carefully, or that
scrapes the output programmatically, would conclude `builtin.hype` has no
transcribe stage and would double-run `builtin.transcribe` separately.

**`run.py` source is unambiguous but requires code-reading.** The `STEP_ORDER`
tuple on line 42 puts "transcribe" first. But requiring agents to read
`run.py` source to discover composition is a UX failure — composition should
be declarative and surfaced through the tool surface.

**Would a less-careful agent have run both?** Yes, with high probability. If
an agent's workflow is: (1) search for "transcribe" → find `builtin.transcribe`,
(2) search for "hype" → find `builtin.hype`, (3) read STAGE.md (no composition
info), (4) run both — it would double-run. Only `inspect` (or reading `run.py`)
prevents this.

## 4. Biggest UX gap

**STAGE.md must declare child stages.** The single change that would most
reduce the risk of double-running is requiring every orchestrator's STAGE.md
to list its child executor IDs (at minimum) or its full stage graph (ideally).
If `hype/STAGE.md` contained even one line like:

```
Stages: transcribe → scenes → quality_zones → shots → triage → scene_describe
→ quote_scout → pool_build → pool_merge → arrange → cut → refine → render →
editor_review → validate
```

...any agent reading the doc would immediately know that invoking `builtin.hype`
covers `builtin.transcribe`. This is a one-line change with outsized impact on
agent composition correctness.

A secondary gap: `author explain` showing the smoke-test DSL fixture instead of
the production pipeline is a trap. Either the production pipeline should have a
DSL plan that mirrors the folder orchestrator, or `author explain` should refuse
to show the DSL plan when a folder orchestrator exists and instead redirect to
`orchestrators inspect`.
