# Replay: doctor aggregate external integrity 3

Date: 2026-08-23  
Surface: public CLI only (`python3 -m astrid`), no source/tests inspection  
Verdict: **PASS**

## Setup

Disposable project root: `/tmp/astrid-doctor-aggregate-final-Gm7ABu/projects`.
Created project `demo`, then imported three files with
`media import ... --realm external_local`:

| media | id | expected SHA-256 |
|---|---|---|
| alpha.bin | `56ffea45-8f44-564e-ba27-e276b0f78584` | `d4466971ade76d49acea05d3146eea90a65c5ae9408f21a31ac313a642659636` |
| bravo.bin | `7c23a178-c06c-572f-b533-3409c81ce2c7` | `c167e29d73c3f3806e9df4687f4858f9d401d61bb81913337118a61316010b0c` |
| charlie.bin | `7a0bae08-104b-50cb-87fd-023758875d17` | `f43598dbf053eca435b7a73c081f310be6327fb717e8df1e06eee3ef2f4a02ad` |

Before the aggregate doctor call, alpha was overwritten with different bytes,
bravo was removed, and charlie was changed to mode `000` (permission denied).

## Aggregate doctor evidence

One `doctor --projects-root ... --json` scan returned exit code 1 and a single
`media_paths` failure detail containing all three failures:

* `hash_mismatch`: alpha's project/media/location identity, locator, expected
  hash `d446...9636`, and found hash `5872bf17cf492cbe1095f8bdc4b5fbac8a9bb37b8850c57098b8c6f050b9790a`.
* `unavailable`: bravo's project/media/location identity and missing locator.
* `unreadable`: charlie's project/media/location identity, locator, and
  `[Errno 13] Permission denied`.

The detail reported `checked 3 locator(s), failed 3
(hash_mismatch=1, unavailable=1, unreadable=1); showing 3/3; cap=8` and
`truncated=0`. Each entry included both recovery forms, `media relocate
<media-id> --project demo --realm external_local --locator <source-file>` and
`media verify <media-id> --project demo --realm external_local`. The unreadable
read error did not abort scanning: all three entries appeared in the one
bounded aggregate.

## Read-only/state proof

The aggregate doctor envelope had `receipt: null`; it emitted no project
receipt/event. A managed-project file/hash snapshot in the independent
aggregate replay root `/tmp/astrid-doctor-aggregate-r7K8KK/projects` was
byte-identical before and after doctor (`PROJECT_TREE_UNCHANGED=true`). In the
final replay root, the only observed first-call difference when hashing every
file was SQLite's `astrid.sqlite3-shm` shared-memory sidecar; a subsequent
doctor call was byte-stable. This is runtime SQLite bookkeeping, not a
receipt/project/media mutation; the doctor envelope remained `receipt: null`.

## Recovery

Using only the prescribed public operations, each identity was relocated to a
preserved valid external locator and then verified:

```text
media relocate 56ff... --realm external_local --locator .../recovery/alpha.bin
media relocate 7c23... --realm external_local --locator .../recovery/bravo.bin
media relocate 7a0b... --realm external_local --locator .../recovery/charlie.bin
media verify 56ff... --realm external_local
media verify 7c23... --realm external_local
media verify 7a0b... --realm external_local
```

All three verifies returned the original expected hash. A final public
`doctor --json` returned exit code 0, `ok: true`, and
`external_local integrity verified (3 locator(s))`.

Both disposable roots were removed after evidence capture. No repository
source, tests, or git state was changed.
