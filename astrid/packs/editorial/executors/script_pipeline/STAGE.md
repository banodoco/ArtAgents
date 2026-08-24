# editorial.script_pipeline

Preset-driven creative-writing executor. It preserves the original three-pass
shape while moving topic-specific prompt rules into config:

1. Generate rough attempts in parallel.
2. Synthesize one structured draft from the rough attempts.
3. Apply a voice/style pass.
4. Optionally judge multiple final candidates and select the winner.

Use fake mode for no-network smoke tests:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.script_pipeline",
        kind="executor", project="demo",
    inputs={
        "preset": "seinfeld",
        "produces_dir": "runs/script-pipeline/produces",
        "fake": True,
        "candidates": "2",
        "rough_attempts": "3",
        "select_best": True,
    },
)
```

Live DeepSeek runs read provider/model data from the preset and require the
configured API-key environment variable, defaulting to `DEEPSEEK_API_KEY`.
