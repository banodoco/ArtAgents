# Owner-contention UX fix

Date: 2026-08-23  
Surface: live `python3 -m astrid` CLI plus the public `serve` HTTP bridge  
Project root: `/tmp/astrid-owner-ux-WqO5Ty`

## Conclusion

Fixed the P1 agent-UX failure from `waves/live-owner-contention-1.md`.
When `astrid serve` owns the canonical database, product CLI commands now
return the stable five-key envelope even though client composition fails before
the family handler runs. The error is typed as `unavailable` with bounded
details:

```json
{"reason":"store_owned","retryable":true}
```

The human message explains the safe handoff: use `GET /routes` and the HTTP
routes while the bridge runs, or wait for clean shutdown; reads may retry;
writes must preserve the exact payload and idempotency key, retry after
release, and verify state. No second writer or lock weakening was introduced.

## Live verification

I created `handoff-demo` and timeline `primary`, then started a real headless
bridge on `127.0.0.1:18987`.

While the bridge owned the store:

- `projects list --json` exited 1 and returned exactly
  `ok/data/error/receipt/idempotency_key`, with `error.code=unavailable` and
  `error.details.reason=store_owned`.
- `timelines show ... --json` returned the same typed envelope.
- A real `timelines save ... --expected-version 1 --idempotency-key owner-ux-001
  --json` returned the same typed error. The HTTP bridge remained healthy;
  `GET /routes` advertised ownership and `GET
  /projects/handoff-demo/timelines/primary` returned version 1.
- A second live run confirmed `timelines --help` exited 0 while ownership was
  held, and human-mode `projects list`/`timelines save` printed concise
  `error unavailable: ...` guidance rather than the degraded bug prefix.
- No timeline event, receipt, version, or config mutation was created by the
  contended write.

After Ctrl-C and clean bridge shutdown:

- The exact intended save with `owner-ux-001` succeeded once at
  `config_version=2`.
- Replaying the exact payload, expected version, and key returned the original
  receipt/event and version 2; no version 3 or duplicate track appeared.
- A different payload with fresh key `owner-ux-stale` and old expected version
  returned typed `stale_version` with `current_version=2` and performed no
  write. The final `timelines show` contained only the intended `owner-test`
  track.
- `astrid timelines --help` remained usable during ownership, and product
  help now documents the handoff and `store_owned` distinction.

## Guards and implementation

Focused guards pass:

```text
13 passed, 36 deselected in 0.46s
```

The guards cover JSON envelope shape, human recovery text, and help text.

Implementation changes:

- `astrid/application.py` and `astrid/packs/__init__.py` attach the bounded
  `store_owned` retry context when translating the exclusive lock failure.
- `astrid/core/gateway/dispatch.py` renders that composition failure through
  `print_result` instead of the degraded bug renderer.
- `astrid/core/gateway/help.py`, `docs/guides/debugging.md`, and
  `docs/guides/cli-journeys.md` document the handoff rule.
- `tests/v10/test_domain_cli_surface.py` adds narrow JSON/human/help guards.
