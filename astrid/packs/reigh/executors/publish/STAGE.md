# Publish To Reigh

**Executor**: `reigh.publish`  
**Status**: implemented  
**Kind**: mutating (pushes timeline+assets into a live Reigh project via API)

Publishes a finished timeline + assets pair into a Reigh project through the
Reigh API. The executor sends the timeline JSON to the Reigh backend, which
ingests it into the specified project and timeline.

**This executor is mutating.** It writes data into a live Reigh project.
Always verify the target project and timeline IDs before running.

## Credential requirements

The executor requires two environment variables for Reigh API authentication:

| Variable             | Description                          |
|----------------------|--------------------------------------|
| `REIGH_USER_TOKEN`   | User authentication token for Reigh  |
| `REIGH_SUPABASE_URL` | Supabase project URL for Reigh       |

Both must be resolvable via the candidate-env-file walk
(`astrid/core/util/secrets.py`). The executor makes authenticated HTTP
calls to the Reigh API — it requires network access (`isolation.network: true`).

## Quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke("reigh.publish", inputs={
    "project_id": "abc123-def456",
    "timeline_id": "ghi789-jkl012",
    "timeline_file": "./out/hype.timeline.json",
})
```

## Inputs

| Name          | Type   | Required | Description                  |
|---------------|--------|----------|------------------------------|
| project_id    | string | yes      | Reigh project UUID           |
| timeline_id   | string | yes      | Reigh timeline UUID          |
| timeline_file | file   | yes      | Path to hype.timeline.json   |

## Outputs

No sentinel outputs — this executor uses `cache.mode: none` and always runs
when invoked. Side effects are mutations to the target Reigh project.

## Pipeline position

Terminal executor — runs optionally after `video_editing.cut` (or after
`rendering.render` if publishing a rendered timeline). Not part of the
numbered editorial pipeline.

## Depends on

None declared in the dependency graph.
