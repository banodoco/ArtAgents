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
Modality-specific flags (`--video`, `--image`, `--at`, `--query`,
…) are not declared as registry inputs, so for any non-trivial call invoke
the dispatcher module directly:

```python
# SDK form — useful for dry runs, scripting, and CI shape checks.
import astrid.sdk as sdk
result = sdk.invoke("understanding.understand", inputs={"mode": "video"}, dry_run=True)
```

```bash
# Canonical form — full modality-specific flag passthrough.
python3 -m astrid.packs.understanding.executors.understand.run --mode image --image frame.jpg
python3 -m astrid.packs.understanding.executors.understand.run --mode audio --audio clip.wav
python3 -m astrid.packs.understanding.executors.understand.run --mode video --video source.mp4 --at 01:20
```
