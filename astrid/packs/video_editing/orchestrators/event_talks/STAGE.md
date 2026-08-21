# video_editing.event_talks

Build and render individual event-talk videos from long recordings. Provides four
subcommands that compose into a pipeline: template generation, transcript search,
holding-screen detection, and render.

## Subcommands

| Subcommand | Purpose |
|---|---|
| `ados-sunday-template` | Write the ADOS Paris Sunday speaker template JSON. |
| `search-transcript` | Search a Whisper JSON transcript for speaker/title phrases. |
| `find-holding-screens` | Sample video frames and OCR for wait/holding/title-card screens. |
| `render` | Render each manifest talk with intro, lower-third, and outro. |

## Invocation

```python
# Full orchestrator run (plan v2 emission + task gate):
import astrid.sdk as sdk
result = sdk.invoke(
    "video_editing.event_talks",
    inputs={"source": "long_recording.mp4"},
    out="runs/event_talks",
)
```

```bash
# Individual subcommand (step executor mode):
python3 -m astrid.packs.video_editing.orchestrators.event_talks.run \
  ados-sunday-template --out runs/talks/template.json
```

Key flags: `--source`, `--out`, `--transcript` (optional, for pre-computed
transcripts), `--dry-run`, `--project`.

## Outputs

```
{out}/
  plan.json                # plan v2
  run.json                 # run provenance
  template.json            # speaker template (ados-sunday-template step)
  search-results.txt       # transcript search hits (search-transcript step)
  holding-screens.json     # OCR'd holding screens (find-holding-screens step)
  render-manifest.json     # per-talk render manifest (render step)
```
