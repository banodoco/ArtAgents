# video_editing.hype

End-to-end hype editing pipeline: transcribe → scenes → quality_zones → shots →
triage → scene_describe → quote_scout → pool_build → pool_merge → arrange → cut →
refine → render → editor_review → validate.

## When to Use

Use when you have a source video and a creative brief and want a finished
Remotion-rendered hype video with cache-aware step resume.

## Invocation

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "video_editing.hype",
    kind="orchestrator",
    project="demo",
    inputs={"video": "source.mp4", "brief": "brief.txt"},
)
```

Key flags: `--video`, `--brief`, `--out` (all required). Optional: `--theme`,
`--target-duration`, `--asset KEY=PATH`, `--skip <step>`, `--from <step>`,
`--dry-run`, `--env-file`, `--verbose`.

## Outputs

```
{out}/
  briefs/{brief_slug}/
    brief.txt               # copy of the brief
    arrangement.json        # editorial arrangement
    hype.timeline.json      # Remotion timeline
    hype.assets.json        # asset manifest
    hype.metadata.json      # run metadata
    hype.mp4                # rendered output
    editor_review.json      # review pass results
    validation.json         # final validation
  run.json                  # run provenance
```
