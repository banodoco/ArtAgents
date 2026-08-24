# Understand Executor

Use `understanding.understand` when an agent wants one dispatch point for source
understanding across audio, still-image, and video modalities. It is a thin
switch over the three underlying executors:

- `--mode audio` → `understanding.audio_understand`
- `--mode image` or `--mode visual` → `understanding.visual_understand`
- `--mode video` → `understanding.video_understand`

All arguments after `--mode <modality>` are forwarded unchanged to the
selected executor. Inspect the underlying executors' inputs through the SDK.

## Examples

The SDK form passes only the `mode` selector through the executor registry.
Every invocation is attached to a project; project-scoped runs write inside
that project's run tree. Modality-specific flags (`--video`, `--image`, `--at`,
`--query`, …) are not declared as registry inputs, so use the underlying
modality capability for any non-trivial call. The dispatcher SDK form is useful
for dry runs, scripting, and CI shape checks:

```python
# SDK form — useful for dry runs, scripting, and CI shape checks.
import astrid.sdk as sdk
result = sdk.invoke(
    "understanding.understand",
    kind="executor",
    project="demo",
    inputs={"mode": "video", "video": "source.mp4", "at": "01:20"},
    dry_run=True,
)
```

The direct module commands previously shown here are internal runner commands,
not public entrypoints; the canonical-entrypoint guard rejects direct
invocation. Invoke the underlying public capability after inspecting its
schema when modality-specific inputs are needed.
