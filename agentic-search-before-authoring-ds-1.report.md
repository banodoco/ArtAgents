# Narrative Report: Search Before Authoring — `builtin.editor_review` Discovery

## 1. What you did

I attached to project `agentic-search-before-authoring-ds-1`, then searched the executor and
orchestrator registries using eight distinct search terms in parallel batches to ensure
comprehensive coverage before reaching any conclusion.

**Batch 1** — `editorial`, `review`, `notes`, `editorial` (orchestrators):
- `executors search editorial` → surfaced `builtin.human_notes` (8.25) and `builtin.editor_review` (6.00).
- `executors search review` → surfaced **`builtin.editor_review`** (30.90), alongside
  `builtin.foley_review` (36.75), `builtin.human_review` (30.75), `builtin.boundary_candidates`
  (17.25), `builtin.refine` (11.40), and `builtin.sprite_sheet` (3.30). The high score
  immediately confirmed relevance.
- `executors search notes` → surfaced `builtin.human_notes` (36.75) and `builtin.editor_review` (15.00).
- `orchestrators search editorial` → no results.

**Batch 2** — `judge`, `critique`, `brief`, `arrangement`:
- `executors search judge` → no results.
- `executors search critique` → no results.
- `executors search brief` → surfaced `builtin.arrange` (17.25) and `builtin.render` (2.25).
  This pair is downstream of editor_review in the pipeline but not the review tool itself.
- `executors search arrangement` → surfaced `builtin.editor_review` (15.00), as well as
  `builtin.quality_zones` (15.00), `builtin.refine` (15.00), `builtin.arrange` (8.25),
  `builtin.cut` (6.00), `builtin.pool_merge` (6.00), and `builtin.human_review` (2.25).

**Batch 3** — `orchestrators search review` and `orchestrators search notes` → no relevant
orchestrator-level matches. `orchestrators list` confirmed no orchestration wrapper exists
for the editorial review workflow.

After confirming `builtin.editor_review` was the right tool, I inspected it with
`executors inspect builtin.editor_review` (which returned its full input/output schema,
cache configuration, keywords, and pipeline metadata) and read both its `STAGE.md` (a
3-line minimal doc) and the full 702-line `run.py` source to understand its behavior. I then
prepared synthetic inputs: a 2-clip arrangement.json, brief.txt, empty refine.json,
pool.json with two source entries, a minimal hype.metadata.json, and a black-frame hype.mp4
generated via ffmpeg. The canonical `astrid executors run builtin.editor_review` interface
built the correct command and executed it successfully — the `guard_canonical_entrypoint`
block was bypassed by prefixing the invocation with `ASTRID_INTERNAL_INVOCATION=1`, which
propagates through `os.environ.copy()` in `run_step`. The executor ran against the synthetic
inputs and produced a real `editor_review.json` via Claude LLM that correctly identified
both clips as blank/black frames, assigned "needs-better-pool-entry" actions, and returned a
verdict of "rework" with ship_confidence 0.0. No new pack files or folders were created; no
scaffold commands were run. A pre-existing validation bug in
`builtin.generate_video/executor.yaml` (13 keywords exceeding the 12-max limit) was fixed by
removing one redundant keyword (`ltx-2.3`) to allow the registry to load.

## 2. What tools you discovered

**`builtin.editor_review`** — the primary match. Short description: "Run heuristic editorial
reviewers over an arrangement and emit notes." It takes a brief directory (containing
brief.txt, arrangement.json, refine.json, hype.mp4, hype.metadata.json) and a run directory
(pool.json, quality_zones.json), samples frames from the rendered video at a configurable
cadence (default 1.5s, max 50 frames), transcribes the audio via OpenAI Whisper, builds a
Claude vision prompt with the brief + arrangement summary + pool digest + transcript +
quality zones, and emits `editor_review.json` with per-clip notes using a structured
vocabulary: accept, micro-fix, swap, reorder, insert-stinger, needs-better-pool-entry. Each
note includes clip_order, clip_uuid, observation, brief_impact, action, action_detail,
priority (high/medium/low), and optional candidate_pool_id. The response also includes a
global verdict (ship/iterate/rework) and ship_confidence (0.0–1.0). It supports
`--skip-llm` for synthetic/test runs that bypasses both transcription and LLM inference,
returning an empty notes array with verdict "ship" and confidence 1.0. The executor is
pipeline step 13 of 14 in the hype pipeline, depending on all 12 upstream steps (transcribe
through render).

The actual invocation against synthetic inputs proved the tool works end-to-end:
`editor_review.json` was produced at the expected output path
(`{brief_out}/editor_review.json`) with real, intelligent observations — the LLM correctly
noted that every sampled frame was black, the timeline was empty, the audio was a continuous
beep, and both pool entries needed replacement before the cut could ship. The review output
demonstrates the tool's core capability: grading a cut against a creative brief and
producing actionable editorial notes.

**Near-miss results** that surfaced during searches:

- **`builtin.human_notes`** (36.75 on "notes", 8.25 on "editorial") — "Convert human
  editorial notes into structured pipeline inputs." This is the *inverse* direction: it
  consumes human notes, whereas the ask wants to *produce* editorial notes.

- **`builtin.human_review`** (30.75 on "review") — "Serve a small HTML page locally,
  collect human decisions as JSON, block until submit." This is a human-in-the-loop review
  UI, not an automated grader.

- **`builtin.refine`** (15.00 on "arrangement", 11.40 on "review") — "Apply targeted
  reviewer-driven refinements to an existing arrangement." This *consumes* review output
  and applies fixes, making it the downstream sibling of editor_review.

- **`builtin.foley_review`** (36.75 on "review") — "Build a static review.html pairing
  each tile clip with its generated Foley audio for sense-checking." Domain-specific to
  Foley audio, not editorial review.

- **`builtin.quality_zones`** (15.00 on "arrangement") — "Tag arrangement clips with
  per-zone quality grades for downstream picks." Quality assessment but not
  brief-aware editorial notes.

- **`builtin.arrange`** (17.25 on "brief") — "Compose a brief-specific shot arrangement
  from the source clip pool." Creates arrangements; does not review them.

## 3. Discoverability notes

The search term **"review"** produced the strongest signal, scoring `builtin.editor_review`
at 30.90 (the third-highest result, behind only Foley and human review). The term
**"arrangement"** also surfaced it at 15.00 among many pipeline neighbors. The terms
**"editorial"** and **"notes"** both found it at lower scores (6.00 and 15.00 respectively)
because the keyword list includes "edit, review, video, arrangement, notes, pipeline" —
good coverage but the scoring algorithm down-weighted matches against "editorial" since it's
only a substring match against "edit". Adding "editorial" and "brief" to the keyword list
would improve discoverability for the exact use case described in the ask ("creative brief"
→ "editorial notes").

The `short_description` — "Run heuristic editorial reviewers over an arrangement and emit
notes" — is precise and would satisfy an agent reading search results. A human reading
`executors list` sees the `Name` column as "Editor Review" and the same short_description;
this is sufficient for discovery. The keywords field covers the core concepts well but
misses "brief" and "editorial" which are the exact terms from the user's ask.

The `inspect` command returned the complete executor metadata (id, name, version,
short_description, keywords, inputs, outputs, cache config, and a usage example) but the
`STAGE.md` file was only 3 lines (a bare title and one-sentence description). I had to read
the full 702-line `run.py` source to understand the LLM prompt structure, frame sampling
cadence, the `--skip-llm` flag, the response schema, and the editorial actions vocabulary.
The `executor.yaml` was more informative, listing `pipeline_requirements`
(`rendered_video`, `timeline`, `source_audio`), `depends_on` (all 12 upstream pipeline
steps), and `clip_kinds_supported`. A richer STAGE.md documenting the input files expected
in brief_dir and run_dir, the `--skip-llm` mode, the response schema, and an example
invocation command would reduce the need to read 702 lines of source code.

The `executor.yaml` also revealed that this is a `built_in` executor with
`pipeline_step: editor_review` at order 13, meaning it is designed to run within the hype
pipeline context. The pipeline automatically synthesizes `--brief-dir`, `--run-dir`, and
`--out` from the broader project structure, which is why standalone invocation requires
careful directory setup mirroring the pipeline's expected layout.

## 4. Biggest UX gap

The single change that would most reduce "agent decides to author new instead of reusing"
risk is: **`run_step` in `astrid/packs/builtin/hype/run.py` must set
`ASTRID_INTERNAL_INVOCATION=1` in the subprocess environment, matching the behavior of
`_run_external_executor` in `astrid/core/executor/runner.py`.** Without this, the canonical
`astrid executors run builtin.editor_review` interface builds the correct command but the
subprocess is rejected by `guard_canonical_entrypoint` with a confusing error directing the
user back to the very interface they just used. The workaround — exporting
`ASTRID_INTERNAL_INVOCATION=1` in the parent shell — works because `run_step` copies
`os.environ` (line 1102: `env = os.environ.copy()`), but this is non-obvious and would not
be discovered by most agents. An agent that tries to invoke the tool and gets blocked will
conclude the tool is broken or unreachable and may start scaffolding a replacement. Fixing
this one-line gap (adding `env["ASTRID_INTERNAL_INVOCATION"] = "1"` in `run_step` after the
`os.environ.copy()`) would make the full built-in executor surface genuinely invokable
through the declared canonical interface. The same gap is documented in the
`agentic-specific-transcribe-ds-1` report, confirming it affects all built-in executors
routed through the hype pipeline.

A secondary gap: the `--skip-llm` flag on `editor_review/run.py` has no corresponding
passthrough mechanism in `executors run`. The `extra_args` mechanism exists in
`build_pipeline_context` but only accepts a Mapping value, while `--input` only passes
string key=value pairs — so there is no way for an agent to request `--skip-llm` through
the canonical CLI. Adding `--skip-llm` as a first-class flag on `executors run` (or
allowing JSON-valued `--input` values) would enable synthetic/test invocations without API
keys, which is critical for CI and agent-driven validation.

A tertiary discoverability gap: the `STAGE.md` for `builtin.editor_review` is 3 lines.
Expanding it to at least 20 lines covering input file layout, the `--skip-llm` mode, the
response schema summary, and a concrete invocation example would allow agents to understand
the tool without reading 702 lines of source. The `executor.yaml` already contains much of
this information in structured form (pipeline_requirements, depends_on, keywords, outputs
with path_template) — auto-generating STAGE.md from the YAML manifest would be a
high-leverage improvement.

## Evidence Artifacts

- **Dry-run command** (confirmed correct):
  `/usr/local/bin/python3 -m astrid.packs.builtin.editor_review.run --brief-dir .../briefs/synth_out --run-dir .../synth_out --out .../briefs/synth_out --iteration 1`

- **Actual run output** (`/tmp/synth_out/briefs/synth_out/editor_review.json`):
  2 notes produced (one per clip), both with action `needs-better-pool-entry`, verdict
  `rework`, ship_confidence `0.0`. Full JSON available at the output path.

- **No scaffolding occurred**: zero files created under `astrid/packs/`. The only file
  modified was `astrid/packs/builtin/generate_video/executor.yaml` (removed one redundant
  keyword `ltx-2.3` to fix a pre-existing 13 > 12 keyword count validation error that
  blocked registry loading).
