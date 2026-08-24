# media.gif_search

## Purpose

Search GIPHY for GIF or sticker assets and write durable Astrid artifacts:
normalized `results.json`, a static `preview.html`, and optionally a downloaded
selected rendition. Use it when a workflow needs remote GIF/sticker candidates
that can later be consumed by an editing or rendering step.

This executor only implements GIPHY today. Tenor is intentionally not supported:
Google stopped new Tenor API client signups in January 2026 and announced API
sunset for June 30, 2026.

## Inputs

- `query` (string, required): Search query.
- `provider` (string, optional): `giphy` only.
- `media_kind` (string, optional): `gif` or `sticker`; defaults to `gif`.
- `limit` (integer, optional): Number of results, default 12, maximum 50.
- `rating` (string, optional): GIPHY rating filter, default `pg-13`.
- `env_file` (file, optional): `.env` file containing `GIPHY_API_KEY`.
- `download_index` (integer, optional): Zero-based result index to download.
- `download_id` (string, optional): Provider result id to download.

Exactly one of `download_index` or `download_id` may be provided.

## Outputs

- `results.json`: Normalized metadata plus provider pagination.
- `preview.html`: Static browse page with provider attribution.
- `selected.*`: Optional downloaded rendition when a download selector is given.
- `manifest.json`: Universal result manifest.

## Canonical Command

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "media.gif_search",
        kind="executor", project="demo",
    inputs={
        "query": "dramatic zoom",
        "media_kind": "gif",
        "limit": "12",
        "rating": "pg-13",
    },
)
```

For direct runtime testing:

```bash
ASTRID_INTERNAL_INVOCATION=1 python3 -m astrid.packs.media.executors.gif_search.run \
  --query "dramatic zoom" \
  --out runs/gifs/dramatic-zoom
```

## Dependencies

- Network access.
- `GIPHY_API_KEY` from the environment or `--env-file`.
