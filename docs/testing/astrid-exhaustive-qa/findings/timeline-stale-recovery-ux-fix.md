# Finding: actionable stale timeline recovery

Date: 2026-08-23  
Surface: public `python3 -m astrid` CLI and SDK error envelope  
Severity: P1 UX remediation  
Status: fixed and live-verified

## Finding

The live two-editor timeline wave proved that whole-document CAS safety was
correct, but the stale save response was not actionable. A stale editor received
`stale_version` with `details: {}` and the generic message “the write supplied a
stale expected version.” The editor had to infer the show → merge → save rule,
and could not see the expected/current versions from the public error.

## Cause and change

`TimelineVersionConflictError` already carried `expected_version` and
`current_version`. The public path is:

```text
timelines save
  -> TimelinesService.save
  -> map_error
  -> DomainResult.failure
  -> shared CLI envelope/human renderer
```

The centralized mapper was discarding those exception fields. It now maps stale
CAS exceptions additively and compatibly:

```json
{
  "code": "stale_version",
  "details": {"expected_version": 1, "current_version": 2}
}
```

Timeline stale errors additionally say that no write occurred and give the
public recovery rule: run `timelines show`, merge the edit into the current
whole document, then run `timelines save` with its `config_version` as
`--expected-version`. They explain that the same idempotency key is for retrying
the same logical request only; a fresh key is required for the new merged save.
No patch/merge API was introduced. Generic run/event stale errors retain the
normalized version fields and receive record-level recovery wording.

The envelope remains the exact five-key shape. The error object remains the
exact three-key shape. Details contain only bounded typed version integers, and
the rejected operation still has no receipt.

## Before-fix live baseline

Fresh root: `/tmp/astrid-live-stale-WLIHML`

Editor A saved a title track from version 1 to version 2. Editor B submitted a
captions-only document with expected version 1 and got:

```json
{
  "code": "stale_version",
  "details": {},
  "message": "the write supplied a stale expected version",
  "receipt": null
}
```

Public `timelines show` remained at version 2 with only A’s title track, and
public `timelines history` remained at versions 1 and 2. A reread/merge save
then produced version 3 with both tracks; replaying that exact save with its
same idempotency key returned version 3 and the same receipt.

## After-fix live verification

Fresh root: `/tmp/astrid-live-stale-fixed-EfeOFL`

The same stale request returned exit code 1 and this machine-readable error:

```json
{
  "data": null,
  "error": {
    "code": "stale_version",
    "details": {"current_version": 2, "expected_version": 1},
    "message": "timeline save rejected: expected version 1, current version 2; no write occurred. Recovery: show the current timeline, merge your changes into it, then save with its config_version as --expected-version. Reuse the same idempotency key only for the same request; use a fresh key for the merged save."
  },
  "idempotency_key": "editor-b-captions-v1",
  "ok": false,
  "receipt": null
}
```

Human mode emitted the same recovery guidance as one concise error line. The
public show still reported version 2 and only A’s title track; history still
contained exactly versions 1 and 2. This demonstrates that B’s rejected write
created no version, event, or receipt.

Following the message, I merged both tracks and saved at expected version 2
with fresh key `editor-b-merge-v2`. It succeeded at version 3. Replaying the
same merged request/key returned the original receipt and version 3, with no
version 4 and no duplicate track.

## Guards

Focused regression coverage passes:

```text
pytest -q tests/sdk/test_domain_contracts.py tests/sdk/test_timelines.py tests/v10/test_domain_cli_projects_timelines.py
116 passed in 4.43s
```

The narrow SDK guard asserts the stable `expected_version`/
`current_version` details and checks that the message includes no-write,
show/merge/save, `config_version`, and idempotency-key guidance. The original
CAS safety and idempotent replay tests remain green.

## Residual friction

`timelines save` remains a whole-document replacement, so an agent must carry
forward unrelated current config/registry fields while merging. A field-level
patch/merge API could reduce that burden, but it is intentionally outside this
fix and would require a separate contract and safety review.

