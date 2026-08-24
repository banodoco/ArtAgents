# Phase-B live HTTP/CLI acceptance — 2026-08-24

Verdict: **PASS after one minimal fix**. The acceptance used the configured
`Astrid/.venv/bin/python`, the public `python -m astrid serve` process, curl
over loopback, and a disposable root:
`/private/tmp/astrid-live-root.uK12rO`. No user project or default root was
used.

## Evidence

- Serve bound `127.0.0.1:18765`; `/health` returned `200` and the exact
  disposable `projects_root`. `/routes` returned version 1, exclusive-owner
  metadata, trust metadata, and the advertised timeline/media/task/attempt
  routes. Boot token was delivered at `.astrid/request-token` with mode 0600.
- Trust perimeter passed: ordinary GET with the bound Host returned 200;
  forged `Host: localhost:18765` returned 403; tokenless POST returned 403;
  malformed token-bearing POST returned typed 400; OPTIONS without a token
  returned 204 and CORS preflight headers.
- Before serving, public CLI created `demo` and timeline `primary`, imported
  `/etc/hosts`, and verified project/list/show envelopes. While serve owned
  the database, a CLI list returned typed `unavailable` with `reason=store_owned`
  and retry guidance.
- HTTP project/timeline reads returned 200. Timeline save with the boot token
  advanced `config_version` 1→2 and persisted a registry asset keyed to the
  imported media. A stale `expected_version=1` save returned 409 with
  `no write occurred`; a reread remained at version 2 with the original
  config/registry.
- Gallery/media routes passed GET and HEAD 200, exact `Content-Length`,
  `Accept-Ranges`, ETag and Last-Modified. `Range: bytes=2-9` returned 206 and
  the expected 8 bytes; conditional ETag returned 304 with no body; an
  unsatisfiable range returned 416 and `Content-Range: bytes */213`. The same
  checks passed for `/projects/demo/media/{id}/content`.
- After the fix below, task/generation reads returned 200, queue claim on an
  empty queue returned 204, and a `render_export` task admitted over HTTP
  returned 201. Claim returned attempt 1/fence; heartbeat returned 200 and
  status version 2; fenced failure returned 200 with structured error and
  requeued the task. Restart preserved both failed attempts. A second claim
  after restart created attempt 2, and fenced failure again preserved the
  structured error and requeued the task.
- Stop/start was exercised three times. After the final restart, health,
  timeline state, task state, and queue claim all remained available; the
  final attempt was failed deliberately so no lease was left live.

## Fix and friction

The first live pass found that `GET /routes` advertised task/attempt routes,
but CLI `serve` passed no `task_bridge` to the HTTP server, so task reads
returned 500 `the task bridge is not composed on this server`. The minimal
fix composes `ReighTaskBridge` in the serve composition root, with the
single existing writer/registry and lazy `GenerationRepository` factory,
then injects it into `create_local_bridge_server`. The timeline repository is
reused for completion-time settlement, preserving one writer authority.

The only expected environment friction was capability availability: the
`image_upscale` capability correctly failed closed with a typed 422 because
the pinned VibeComfy checkout was absent. `render_export` was available and
provided the complete task/attempt journey without external services.

## Regression check

`python -m compileall -q astrid/core/gateway/dispatch.py` passed, and
`pytest -q tests/integrations/reigh/test_task_routes.py tests/integrations/reigh/test_local_trust_gate.py`
passed: **50 passed in 30.72s**.
