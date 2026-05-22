# builtin.script_pipeline

Preset-driven creative-writing executor. It preserves the original three-pass
shape while moving topic-specific prompt rules into config:

1. Generate rough attempts in parallel.
2. Synthesize one structured draft from the rough attempts.
3. Apply a voice/style pass.
4. Optionally judge multiple final candidates and select the winner.

Use fake mode for no-network smoke tests:

```bash
python3 -m astrid executors run builtin.script_pipeline -- \
  --preset seinfeld \
  --produces-dir runs/script-pipeline/produces \
  --fake \
  --candidates 2 \
  --rough-attempts 3 \
  --select-best
```

Live DeepSeek runs read provider/model data from the preset and require the
configured API-key environment variable, defaulting to `DEEPSEEK_API_KEY`.
