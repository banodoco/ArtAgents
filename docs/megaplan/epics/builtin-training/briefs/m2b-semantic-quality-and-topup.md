# Milestone 2b: Semantic Quality, Invalidation, and Top-Up Loop

## Outcome

Add the content-aware quality loop around `builtin.dataset_build`: semantic filtering, transcript filtering, cache invalidation, human-reject top-up rounds, and actionable reporting.

## Scope

In scope:

- Add optional transcript keyword filtering via `builtin.transcribe`.
- Add semantic filter stages:
  - `visual_understand` frame/contact-sheet judging.
  - `video_understand` for configured video/audio-sensitive checks.
- Add prompt/schema/media hash metadata so judge/caption artifacts invalidate only when relevant inputs change.
- Respect the M0 API budget and rate-limit settings for every transcript, visual, or video understanding call.
- Add caption template/schema validation before manifest export.
- Add perceptual or near-duplicate detection beyond exact file hash where feasible within scope.
- Add capped top-up rounds after human review rejects leave buckets under target.
- Add deterministic reject-reason feedback into later semantic judge prompts.
- Add dataset quality report with:
  - source concentration
  - rights/provenance warnings
  - estimated and observed API call counts/costs where available
  - accepted/rejected/pending counts
  - filter rejection reasons
  - semantic scores
  - caption/schema validation failures
  - target shortfalls after max top-up rounds
- Fail clearly if configured bucket targets remain unmet after max top-up rounds.

Out of scope:

- New trainer adapters beyond ai-toolkit LTX.
- Full image/audio/pair dataset workflows.
- GPU training orchestration.

## Locked Decisions

- Top-up rounds are capped, default 2.
- Reject reason feedback is deterministic/static, not another LLM call.
- VLM calls must be cached by prompt/schema/media hash.
- `video_understand` is configurable and should be available as a first-class semantic filter for video LoRA configs, not hidden as an ad hoc fallback.
- Caption sidecars must be schema/template validated before final manifest export.

## Open Questions

- Thresholds for perceptual duplicate detection.
- Whether transcript filtering transcribes whole sources or candidate clips by default.
- Which semantic filter defaults are appropriate for generic video LoRA versus pack-specific configs.

## Constraints

- Preserve M1/M2a public config compatibility.
- Make expensive/network stages skippable or mockable in tests.
- Refuse non-dry-run semantic stages when required provider secrets or configured API budgets are missing.
- Never silently accept a shortfall after top-up rounds; fail or mark incomplete with a clear reason.

## Done Criteria

- A config can request transcript, visual, and video semantic filters.
- Prompt/schema changes invalidate judge/caption artifacts without manual deletion.
- API calls obey configured concurrency/rate limits and budget caps.
- Top-up collects new candidates and reopens review for new/pending items when buckets fall short.
- The quality report is written and linked from the run output.
- Caption sidecars are validated before final manifest export.
- Tests cover semantic filter stubbing, invalidation, top-up shortfall behavior, and report generation.

## Touchpoints

- `builtin.dataset_build`
- `builtin.transcribe`
- `builtin.visual_understand`
- `builtin.video_understand`
- Generic review UI and `builtin.human_review`
- `tests/`

## Anti-Scope

- Do not broaden into training execution.
- Do not implement non-video media workflows beyond preserving extension points.
