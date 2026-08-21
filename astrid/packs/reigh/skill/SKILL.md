---
name: reigh
description: >
  Reigh platform integration: publish timelines via API, stage local
  outputs for handoff, fetch canonical project data, and build spatial
  audio viewer pages.  Requires Reigh credentials for API access.
---

# Reigh

The reigh pack covers four executors for integrating Astrid-generated
timelines and assets with the Reigh platform.

## Executors

| Executor | What it does |
|---|---|
| `reigh.publish` | Push a finished timeline + assets pair into a Reigh project via API. Mutating — requires `REIGH_USER_TOKEN` and `REIGH_SUPABASE_URL`. |
| `reigh.open_in_reigh` | Copy or stage generated timeline+assets for handoff into a Reigh project. Local-only, no API calls — prepares outputs for import. |
| `reigh.reigh_data` | Fetch canonical Reigh project data through the reigh-data Edge Function. Requires `REIGH_PAT`. |
| `reigh.spatial_audio_page` | Build a static page that mixes Foley tracks anchored to spatial rectangles via Web Audio, with the original video and per-tile audio. |

## When to use

- Use `reigh.publish` when you have a finished timeline+assets pair and
  want to push it into a Reigh project via the API. This is the canonical
  path for automated pipeline-to-Reigh handoff.
- Use `reigh.open_in_reigh` when you want to stage outputs locally for
  manual import into Reigh — no credentials or network needed.
- Use `reigh.reigh_data` to fetch project metadata from Reigh before
  starting a pipeline run (e.g., to discover project/timeline UUIDs).
- Use `reigh.spatial_audio_page` as the final step of a spatial Foley
  pipeline to produce an interactive viewer HTML page.

## Credential setup

The reigh pack requires different credentials depending on which executor
you use:

| Env var | Required by | Purpose |
|---|---|---|
| `REIGH_PAT` | `reigh.reigh_data` | Personal access token for the reigh-data Edge Function. |
| `REIGH_USER_TOKEN` | `reigh.publish` | User auth token for Reigh API writes. |
| `SUPABASE_URL` (or `REIGH_SUPABASE_URL`) | `reigh.publish` | Supabase project URL for the Reigh backend. |

Set them in your environment or in a `.env` file:

```bash
export REIGH_PAT="pat_..."
export REIGH_USER_TOKEN="..."
export SUPABASE_URL="https://<project>.supabase.co"
```

## Quick-start

```python
import astrid.sdk as sdk

# Publish a timeline to Reigh
result = sdk.invoke("reigh.publish", inputs={
    "project_id": "<uuid>", "timeline_id": "<uuid>",
    "timeline_file": "./hype.timeline.json",
})

# Stage outputs locally for Reigh import
result = sdk.invoke("reigh.open_in_reigh", inputs={
    "timeline": "./hype.timeline.json", "assets": "./hype.assets.json",
})

# Fetch Reigh project data
result = sdk.invoke("reigh.reigh_data", inputs={"project_id": "<uuid>"}, out="./reigh-data.json")

# Build spatial audio viewer (requires tiles.json from foley pipeline)
result = sdk.invoke("reigh.spatial_audio_page", inputs={"manifest": "./tiles.json"}, out="./viewer")
```
