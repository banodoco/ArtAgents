# Smoke Test Scenario

You are running the Astrid Sisypy adapter smoke test. This is a structural-only
scenario that primes a real Astrid project and starts `video_editing.hype` to
generate evidence artifacts.

## What happens

1. A project is created with slug `${SLUG}`.
2. `video_editing.hype` is started on that project.
3. The run is left mid-flight — no steps are acked.
4. The capture phase freezes `events.jsonl` and `tree.txt` into the evidence pack.

## Rules

- This scenario runs with `--actor fake --mode structural` only.
- Never run this in live mode — it is a smoke test, not an agent task.
- The brief exists so Sisypy discovery can find and render it, but no real agent
  reads this file.
