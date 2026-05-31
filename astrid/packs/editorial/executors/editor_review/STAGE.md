# Editor Review

**Executor**: `editorial.editor_review`  
**Status**: implemented  
**Pipeline step**: 13 (human-in-loop gate using heuristic reviewers)

Runs automated heuristic editorial review over a rendered hype.mp4 against the
creative brief. This is the human-in-loop gate — it samples frames from the
rendered video at a configurable cadence, transcribes the output audio via
OpenAI GPT Audio (Whisper), inspects the cut run directory artifacts, and
feeds all evidence into a Claude vision model. The model returns structured
`editor_review.json` with per-clip notes, actions (accept, micro-fix, swap,
reorder, insert-stinger, needs-better-pool-entry), priorities, and a ship
verdict with confidence.

The executor can call `editorial.inspect_cut` internally to enrich the
evidence presented to the reviewer, and it reads refine.json, quality_zones.json,
and the unified pool to ground its recommendations. Use `--skip-llm` to
bypass the Claude call and emit a default ship verdict (for dry-run or
testing). The reviewer supports up to 2 iterations (`--iteration 1|2`) for
multi-pass review workflows.

For fully interactive human review (web-based clip-by-clip approval),
use `editorial.human_review` — editor_review is the automated heuristic
pass, not the interactive web UI.

## CLI quick-start

```bash
python -m astrid executors run editorial.editor_review -- \
  --brief-dir ./out --run-dir ./runs/my-run --out ./out
```

With custom model and frame sampling:

```bash
python -m astrid executors run editorial.editor_review -- \
  --brief-dir ./out --run-dir ./runs/my-run --out ./out \
  --model claude-sonnet-4-6 --max-frames 30 --cadence-sec 2.0 \
  --env-file .env.local
```

Skip the LLM call for a default ship verdict:

```bash
python -m astrid executors run editorial.editor_review -- \
  --brief-dir ./out --run-dir ./runs/my-run --out ./out \
  --skip-llm
```

Second-iteration review:

```bash
python -m astrid executors run editorial.editor_review -- \
  --brief-dir ./out --run-dir ./runs/my-run --out ./out \
  --iteration 2
```

## Inputs

| Name      | Type      | Required | Description                                     |
|-----------|-----------|----------|-------------------------------------------------|
| brief_dir | directory | no       | Directory with arrangement.json, hype.mp4, etc. |
| run_dir   | directory | no       | Source run directory with pool.json, scenes, etc. |
| env_file  | file      | no       | Env file for Claude and OpenAI API credentials  |

## Outputs

| Name          | Type | Path                          | Description                           |
|---------------|------|-------------------------------|---------------------------------------|
| editor_review | file | `{brief_out}/editor_review.json` | Structured review notes, actions, ship verdict |

## Pipeline position

Step 13 of the editorial pipeline. Runs after rendering.render (step 12)
produces hype.mp4, and before editorial.validate (step 14) confirms the
output quality. The editor_review.json output feeds into refine (step 11
on subsequent iterations) or directly informs the ship/no-ship decision.

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
- `editorial.shots`
- `editorial.triage`
- `understanding.scene_describe`
- `editorial.quote_scout`
- `training.pool_build`
- `training.pool_merge`
- `editorial.arrange`
- `video_editing.cut`
- `editorial.refine`
- `rendering.render`
