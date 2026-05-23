---
name: human_review
description: Generic human-gate primitive. Serves a project HTML page, collects schema-validated JSON decisions, blocks until submit.
---

# Human Review

Reusable HTTP server for human-in-loop steps. Any orchestrator that needs a
human to look at something and produce a structured decision passes its own
HTML page + JSON data, and gets back validated JSON.

## CLI

```
python3 -m astrid.packs.builtin.human_review.run \
  --html <path>            # file or dir; served at /
  --data <path>            # JSON file, served at /data.json (read-only)
  --serve /prefix=<dir>    # repeatable; static mount
  --state <path>           # POST /save applies diff payloads here
  --out <path>             # POST /submit writes here, server exits 0
  --response-schema <path> # optional; strict JSON-schema validation of /submit
  --port 0                 # auto-pick free port (default)
  --no-open                # skip browser auto-launch
  --timeout 0              # exit nonzero after N seconds if no submit (0=unlimited)
```

On startup the executor prints **one line** containing the URL with the
session token query param. Open it in any browser if `--no-open` is set.

## Routes

| Method | Path                   | Behavior |
|--------|------------------------|----------|
| GET    | `/?token=<t>`          | Serves `--html` (file content or dir's `index.html`). |
| GET    | `/data.json`           | Read-only mount of `--data`. |
| GET    | `/state.json?token=<t>`| Returns `--state` contents (200), or 404 if absent. |
| GET    | `/<prefix>/...`        | Static mount per `--serve PREFIX=DIR`. Supports HTTP Range for mp4 seeking. |
| POST   | `/save`                | Applies a diff payload to `--state`: `{base_state_version, revisions}`. Returns 200 with the new state version, 409 on stale base state, or 400 for malformed/non-diff payloads. Token required. |
| POST   | `/submit-batch`        | Applies one decision to either visible `item_ids` or `scope: "filtered"` items selected from `--data`. Requires `base_state_version`; returns 200 with new state version, 409 on stale base state, or 400 on malformed payloads. Token required. |
| POST   | `/submit`              | Schema-validate body, atomic write to `--out`, signal shutdown. Returns 204 on success / 400 on schema fail (state/out unchanged). Token required. |

## Static mounts are unauthenticated by design

`<video>` and `<img>` tags can't easily send custom auth headers, so static
GETs under `--serve` mounts are **not** token-checked. Don't mount sensitive
content; mount only the media the page needs. POSTs and `/state.json` ARE
token-checked.

## Reuse pattern

The HTML decides the response shape; the executor only validates against
the supplied schema. Same primitive serves dataset-review, eval-grid pick,
arrangement approval — write the HTML next to the orchestrator that uses it.

For dataset review state, `/save` is diff-only. Clients must first read
`/state.json`, then submit only changed item revisions with the observed
`base_state_version`. The server never accepts a full replacement state on
`/save`; full-state writes would bypass stale-save detection and are rejected.
Batch decisions use `/submit-batch` with the same `base_state_version` guard.
Send either `item_ids` for the visible page or `scope: "filtered"` with an
optional `status` or `filter.status` to select matching items from `data.json`.
