# Vague Video Request — Discovery Run Report

**Agent:** `agentic-vague_video_request-ds-1`
**Project:** `agentic-vague-video-request-ds-1`
**Run tag:** `v10`
**Outcome:** Successfully discovered and exercised `builtin.hype` — the canonical Astrid orchestrator for hype-cut/sizzle-reel/trailer editing. Pipeline ran 6 of 15 stages before failing on `quote_scout` (expected with a silent 1-second placeholder).

---

## 1. What you did

Started by attaching to the project with `python3 -m astrid attach agentic-vague-video-request-ds-1`, which bound the session and exported `ASTRID_SESSION_ID`. Immediately followed with `python3 -m astrid orchestrators list` to survey the available multi-step pipelines. Scanned the output and spotted `builtin.hype` with the description "Run the canonical hype editing pipeline end-to-end (transcribe → cut → render → validate)" — an exact semantic match for the user's ask ("trailer, sizzle reel, hype cut").

Ran `python3 -m astrid orchestrators inspect builtin.hype` to confirm the pipeline structure. The inspect output revealed 15 child executors (`transcribe`, `scenes`, `quality_zones`, `shots`, `triage`, `scene_describe`, `quote_scout`, `pool_build`, `pool_merge`, `arrange`, `cut`, `refine`, `render`, `editor_review`, `validate`) and the invocation pattern. Cross-referenced with `python3 -m astrid executors list` to verify all child executors exist and are registered.

Checked `docs/ideas.md` which explicitly recommends `builtin.hype` for "A hype cut from a long video." Read the orchestrator's `STAGE.md` (3-line placeholder), `orchestrator.yaml` (runtime config with full child executor list), and `run.py` (1,686-line orchestrator with argparse showing `--video`, `--brief`, `--out`, and many other options). Also read `docs/architecture.md` which documents that agents should load the top-level Astrid skill first, then open the folder-level `STAGE.md` for the selected registry item.

Created a minimal 1-second black-frame silent MP4 placeholder (`/tmp/hype_test/placeholder.mp4`) via ffmpeg, plus a brief text file (`/tmp/hype_test/brief.txt`). Ran a dry-run first: `python3 -m astrid orchestrators run builtin.hype --project agentic-vague-video-request-ds-1 --dry-run -- --video /tmp/hype_test/placeholder.mp4 --brief /tmp/hype_test/brief.txt --dry-run` — the gateway emitted the planned command. Then ran for real: `python3 -m astrid orchestrators run builtin.hype --project agentic-vague-video-request-ds-1 -- --video /tmp/hype_test/placeholder.mp4 --brief /tmp/hype_test/brief.txt`.

The orchestrator executed successfully through 6 stages: `transcribe` (produced an empty transcript.json — expected for silent video), `scenes` (detected scene boundaries), `quality_zones` (tagged quality zones), `shots` (sliced into shots), `triage` (triaged by quality), and `scene_describe` (captioned scenes with a vision model via 2 LLM debug requests). It failed at `quote_scout` because the empty transcript caused a `BadRequestError` from Anthropic Claude ("user messages must have non-empty content"). The output directory contained 9 JSON artifacts (`transcript.json`, `scenes.json`, `quality_zones.json`, `shots.json`, `scene_triage.json`, `scene_descriptions.json`, `run.json`, `cache/chunks.json`, and 4 LLM debug files). Total shell calls: 8.

---

## 2. What tools you discovered

**Orchestrator: `builtin.hype`** — The canonical hype editing pipeline. Discovered via `python3 -m astrid orchestrators list`, where it appeared with the description "Run the canonical hype editing pipeline end-to-end (transcribe → cut → render → validate)." The name "hype" was directly guessable from the user's request language ("hype cut"). Confirmed suitability via `docs/ideas.md` line 7: "A hype cut from a long video — `builtin.hype`." Inspected in detail with `python3 -m astrid orchestrators inspect builtin.hype --json`, which revealed the full 15-stage pipeline and all child executors.

**Executors discovered (15, all child executors of builtin.hype):** `builtin.transcribe` (Whisper transcription), `builtin.scenes` (ffmpeg scene-boundary detection), `builtin.quality_zones` (per-zone quality grading), `builtin.shots` (shot window slicing), `builtin.triage` (quality triage), `builtin.scene_describe` (vision-model captioning), `builtin.quote_scout` (Claude-driven quote extraction), `builtin.pool_build` (candidate clip pool construction), `builtin.pool_merge` (pool merging), `builtin.arrange` (brief-specific shot arrangement), `builtin.cut` (timeline+assets+metadata JSON triple generation), `builtin.refine` (reviewer-driven refinement), `builtin.render` (Remotion compositor render), `builtin.editor_review` (heuristic editorial review), and `builtin.validate` (output validation against timeline). All surfaced via `python3 -m astrid orchestrators inspect builtin.hype` which lists `child_executors` in the pipeline's `STEP_ORDER`.

**Other orchestrators seen (not used):** `builtin.event_talks` (conference talk pipeline), `builtin.thumbnail_maker` (thumbnail generation), `builtin.foley_map` (spatial Foley pipeline), `builtin.iterate_video`, `builtin.logo_ideas`, `builtin.vary_grid`, `builtin.animate_image`, plus Seinfeld-specific pack orchestrators. None matched the "hype cut / sizzle reel / trailer" ask as precisely as `builtin.hype`.

**Key docs discovered:** `docs/ideas.md` (idea-to-orchestrator mapping), `docs/architecture.md` (system overview, onboarding commands, and the guidance that agents should read folder-level `STAGE.md`), `astrid/packs/builtin/hype/STAGE.md` (3-line placeholder), `astrid/packs/builtin/hype/orchestrator.yaml` (runtime metadata with full child executor list and command template), `astrid/packs/builtin/hype/run.py` (orchestrator implementation with argparse, cache-aware resume logic, and per-source/per-brief sentinel file tracking).

---

## 3. Discoverability notes

**What felt obvious:** The `orchestrators list` output was the clearest discovery path. The description "Run the canonical hype editing pipeline end-to-end" uses the exact same word ("hype") that the user's request uses ("hype cut"), making the match immediately obvious. The keyword tags (`hype, pipeline, video, edit, render, transcribe, cut`) reinforce the match. The `docs/ideas.md` file served as an excellent second-confirmation signal — a single-line mapping from user intent to orchestrator ID. The `orchestrators inspect` output was comprehensive, listing all child executors, the runtime command template, and the invocation pattern.

**What didn't feel obvious:** The `STAGE.md` for `builtin.hype` is a 3-line placeholder that says nothing beyond the orchestrator's name. Per `docs/architecture.md` lines 40-42, agents are told to "load the top-level Astrid skill first, then open only the specific folder-level `STAGE.md` needed for the selected registry item." If an agent follows this instruction literally, they land on a near-empty file with zero usage guidance, no example invocation, and no explanation of required inputs. The passthrough argument syntax (`astrid orchestrators run <id> -- <pack-args>`) requires reading `orchestrators run --help` carefully — it's not surfaced in the `orchestrators inspect` output despite being the canonical invocation path. The `--project` vs `--out` mutual exclusion is runtime-enforced rather than documented upfront.

**Was the right tool's name guessable?** Yes. The user said "hype cut" and the orchestrator is literally called "hype." In a blind `orchestrators list` scan, `builtin.hype` appears in the first half (alphabetically by pack, then by name within pack). If someone searched for "trailer" or "sizzle" they would not find it — those terms don't appear in any keyword or description — but the user's prompt included "hype cut" which made the match trivial.

**Did the skill doc trigger at the right moment?** No. The `STAGE.md` triggered (I read it at the right point in discovery) but contained almost no information. The real skill documentation is distributed across `orchestrators inspect` output, `docs/ideas.md`, and `run.py`'s argparse help — none of which an agent following the architecture doc's "open the folder-level STAGE.md" guidance would see without further exploration.

---

## 4. Biggest UX gap

**The `STAGE.md` for `builtin.hype` is a 3-line placeholder with no actionable content.** This is the single biggest UX gap because the architecture doc explicitly trains agents to read folder-level `STAGE.md` as their primary source of truth for a selected orchestrator. The current file says only:

```
# Hype Pipeline
Built-in Astrid orchestrator for the canonical hype editing workflow.
```

It is missing: (a) the full invocation command with passthrough syntax, (b) the list of required inputs (`--video`, `--brief`, `--out`), (c) a minimal worked example, (d) the 15-stage pipeline order with a one-line description of what each stage does, (e) prerequisites and API key expectations (Whisper, Anthropic Claude, vision models, Remotion), and (f) common failure modes like the empty-transcript → quote_scout crash I hit. A well-populated `STAGE.md` would have let me invoke the orchestrator correctly on the first attempt without needing to read `run.py`'s argparse or experiment with `--out`/`--project` mutual exclusion. Compare with `docs/templates/orchestrator/STAGE.md` which itself is only a 22-line example template — the template and the actual stage doc are both too sparse. The fix: backfill every shipped orchestrator's `STAGE.md` with the template expanded to include invocation examples, input requirements, pipeline stage overview, and common pitfalls, then gate CI on `STAGE.md` minimum-content checks so this doesn't regress.
