# Triage

**Executor**: `editorial.triage`  
**Status**: implemented  
**Pipeline step**: 4 (quality gate before pool building)

Triages source-video scenes by quality before the pool-building phase.
The executor evaluates each scene against quality criteria — visual clarity,
motion stability, and audio intelligibility — and emits a `scene_triage.json`
that marks scenes as keep, reject, or conditional. This gate determines
which scenes are eligible for pool building in downstream training steps.

Triage is the last quality checkpoint before the pool-building phase
(training.pool_build at step 7). Rejected scenes are excluded from the
clip pool; conditionally-accepted scenes carry notes for downstream
arrangement and refinement.

## SDK quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.triage",
        kind="executor", project="demo",
    inputs={"scenes": "./out/scenes.json", "shots": "./out/shots.json"},
)
```

With an explicit env file for API credentials:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "editorial.triage",
        kind="executor", project="demo",
    inputs={
        "scenes": "./out/scenes.json",
        "shots": "./out/shots.json",
        "env_file": ".env.local",
    },
)
```

## Inputs

| Name     | Type | Required | Description                              |
|----------|------|----------|------------------------------------------|
| scenes   | file | no       | Scene boundaries JSON from editorial.scenes |
| shots    | file | no       | Shot windows JSON from editorial.shots |
| env_file | file | no       | Optional environment file for API credentials |

## Outputs

| Name         | Type | Path                         | Description                     |
|--------------|------|------------------------------|---------------------------------|
| scene_triage | file | `{out}/scene_triage.json`    | Per-scene quality triage decisions |

## Pipeline position

Step 4 of the editorial pipeline. Depends on the early-pipeline executors
(transcribe, scenes, quality_zones, shots). Feeds into pool_build by
excluding low-quality scenes from the candidate pool.

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
- `editorial.shots`
