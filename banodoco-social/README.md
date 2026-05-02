# banodoco-social

Shared Python tooling for Banodoco social publishing workflows.

This package is intentionally standalone. It does not import from ArtAgents or
brain-of-bndc, and the existing brain-of-bndc publishing provider remains
unchanged.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

The console script is installed as:

```bash
banodoco-social
```

## YouTube via Zapier

YouTube publishing posts a JSON payload to a Zapier webhook. Set
`ZAPIER_YOUTUBE_URL` in the runtime environment before publishing:

```bash
export ZAPIER_YOUTUBE_URL="https://hooks.zapier.com/hooks/catch/..."
```

Publish with a reachable `http(s)` video URL:

```bash
banodoco-social youtube \
  --video-url "https://cdn.example.com/renders/talk.mp4" \
  --title "Rendered talk" \
  --description "A rendered talk video." \
  --tag talk \
  --tags "banodoco,event" \
  --privacy-status unlisted \
  --playlist-id "PLAYLIST_ID"
```

The Zapier payload uses these keys: `platform`, `action`, `title`,
`description`, `media_url`, `media_urls`, `privacy_status`, `tags`,
`playlist_id`, and `made_for_kids`.

Local files are deliberately rejected in this iteration. If you have
`runs/event/rendered/talk.mp4`, upload or stage it first to a reachable
`http(s)` URL, then pass that URL with `--video-url`. This package does not
implement multipart upload, binary upload, staging, or local-file upload to
Zapier.

This package is additive. It does not replace or route through brain-of-bndc's
existing `YouTubeZapierProvider`, which remains unchanged for now.
