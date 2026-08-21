# Open In Reigh

**Executor**: `reigh.open_in_reigh`  
**Status**: implemented  
**Kind**: local staging (copies/prepares files for manual Reigh import)

Copies or stages generated timeline + assets files for handoff into a Reigh
project. Unlike `reigh.publish` (which pushes data via API), this executor
prepares local outputs so they can be manually imported into Reigh through
the Reigh web interface or CLI.

This is a **local-only operation** — it does not require Reigh credentials
or network access. The executor copies the timeline JSON (and optionally
the assets JSON) to a staging location suitable for import.

## Quick-start

```python
import astrid.sdk as sdk
result = sdk.invoke("reigh.open_in_reigh", inputs={"timeline": "./out/hype.timeline.json"})
```

With explicit assets file:

```python
result = sdk.invoke("reigh.open_in_reigh", inputs={
    "timeline": "./out/hype.timeline.json",
    "assets": "./out/hype.assets.json",
})
```

## Inputs

| Name     | Type | Required | Description            |
|----------|------|----------|------------------------|
| timeline | file | yes      | Timeline JSON file     |
| assets   | file | no       | Assets JSON file       |

## Outputs

No sentinel outputs — this executor uses `cache.mode: none` and always runs
when invoked. Side effects are local file copies/staging operations.

## Pipeline position

Terminal executor — runs optionally after `video_editing.cut` to prepare
outputs for manual Reigh import. Not part of the numbered editorial pipeline.

## Depends on

None declared in the dependency graph.

## Comparison with publish

| Feature          | `reigh.open_in_reigh`      | `reigh.publish`                     |
|------------------|----------------------------|-------------------------------------|
| Mechanism        | Local file copy/stage      | Reigh API push                      |
| Credentials      | None required              | `REIGH_USER_TOKEN` + `REIGH_SUPABASE_URL` |
| Network          | Not required               | Required (`isolation.network: true`) |
| Mutating         | Local only                 | Mutates live Reigh project          |
| Use case         | Manual import workflow     | Automated CI/CD pipeline            |
