# Replay: stale timeline conflict recovery (fresh agent)

## Verdict

**PASS — recovery UX is actionable and preserves both concurrent edits.** The
stale-save response names the expected and current versions, explicitly states
that no write occurred, and gives the correct `show → merge → save` recovery
sequence. It also gives correct idempotency-key guidance: reuse a key only for
the same request and use a fresh key for the merged save. The final timeline
contains both title and captions tracks; history and diff expose the three
document versions without duplicate writes.

## Live setup and scenario

- Used a fresh isolated `ASTRID_PROJECTS_ROOT=/tmp/astrid-replay-conflict-HHHK5D`.
- Created project `collaborative-cut` and default timeline `primary` through the
  public CLI.
- Both editors were treated as having read version 1.
- Editor A saved a title track with `--expected-version 1` and idempotency key
  `editor-a-title-v1`; the save returned `config_version: 2`.
- Editor B then attempted to save a captions-only document from stale version 1
  with `--expected-version 1` and key `editor-b-captions-v1`.

## Observed stale-save response

The CLI returned exit code 1 and this structured error envelope:

```json
{"data":null,"error":{"code":"stale_version","details":{"current_version":2,"expected_version":1},"message":"timeline save rejected: expected version 1, current version 2; no write occurred. Recovery: show the current timeline, merge your changes into it, then save with its config_version as --expected-version. Reuse the same idempotency key only for the same request; use a fresh key for the merged save."},"idempotency_key":"editor-b-captions-v1","ok":false,"receipt":null}
```

This is unusually good agent-facing failure guidance: it is typed, includes both
versions, makes the no-write guarantee explicit, and tells the agent exactly
how to recover.

## Recovery and idempotency

Following the response, `timelines show primary --project collaborative-cut`
confirmed version 2 and A's title track remained intact. `timelines diff` showed
the version 1 → 2 addition. B then merged the captions track into the current
document and saved with `--expected-version 2` and fresh key
`editor-b-merge-v2`; the save returned `config_version: 3`.

Replaying the exact merged save with the same key returned the identical version
3 result and identical receipt/event id, without creating another version.

## Final evidence

Final `show` returned `config_version: 3` with both tracks:

```json
{"tracks":[{"id":"title","kind":"title","text":"Collaborative Cut"},{"id":"captions","kind":"captions","text":"Hello world"}]}
```

`history` contained exactly three entries, versions 1 (`timeline.created`), 2
(`timeline.saved`, title), and 3 (`timeline.saved`, title + captions). `diff`
contained exactly two adjacent transitions (1→2 and 2→3). No duplicate version
or event was introduced by the idempotent replay.

## UX notes

No material friction was encountered. The only agent burden is that merge is a
manual whole-document operation: the CLI does not perform a semantic track
merge, which is appropriate for a CAS primitive and is clearly communicated by
the stale error.
