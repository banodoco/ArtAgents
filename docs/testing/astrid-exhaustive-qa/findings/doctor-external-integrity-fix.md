# Doctor external-integrity fix

Date: 2026-08-23

## Semantics

`astrid doctor` remains strictly read-only and keeps its six-check JSON shape.
The existing required `media_paths` check now verifies every
`external_local` location against the immutable `media.content_hash`, in
addition to the managed SHA-256 locator checks. A healthy result explicitly
reports either `external_local integrity verified (N locator(s))` or that no
external locations exist. A missing, unreadable, or hash-mismatched external
file is a required failure, so ordinary `doctor` cannot report global health
while an imported external asset is unusable.

Failure details include the location ID, media ID, project slug/ID, locator,
expected/found hashes where applicable, and public recovery commands:

```
astrid media verify <media-id> --project <project> --realm external_local
astrid media relocate <media-id> --project <project> --realm external_local --locator <source-file>
```

Doctor never updates `verified_at`, moves files, or creates receipts. Hashing is
deliberately the default because a green ordinary health result must be
truthful; operators with very large external collections should account for
the read-only full-file scan cost.

The sweep does not stop at the first bad external locator. Rows are checked in
deterministic locator-ID order, with separate `hash_mismatch`, `unavailable`,
and `unreadable` counts. Failure entries are capped at eight (`cap=8`) and the
detail reports `showing=<shown>/<total>` plus `truncated=<count>` metadata, so
many damaged paths remain bounded while the aggregate counts stay truthful.
One unreadable path is recorded and the remaining locators are still checked.

Orphan staging warnings now include a deterministic bounded list (up to eight)
of concrete directories and state that cleanup is safe only after confirming
no active media command owns them. Doctor never deletes staging.

The centralized SDK mapper now preserves localized ownership details for shot
media and reference media/association/primary/link failures, including the
offending IDs, target project, stable reason, and a public list/show recovery
command. These remain typed `validation_error` responses and still reject
before mutation.

## Reproduction before the fix

On disposable root `/tmp/astrid-doctor-fix-repro-S32HPt`, one project held one
managed and one external media row. After appending bytes to, then removing,
the external source path, the old doctor returned exit 0 with
`media_paths.status=ok` in both cases. `media verify` already detected the
damage, but doctor-only monitoring could greenwash it.

## Regression tests

Added `tests/v10/test_doctor.py`:

- mutates and removes an external file, asserting required doctor failure,
  media/location identity and public recovery text, and byte-for-byte
  unchanged SQLite before/after doctor;
- restores the bytes and asserts the explicit external-integrity success detail;
- creates two orphan staging directories and asserts concrete paths, bounded
  cleanup guidance, and no deletion.
- damages two external locators in different ways (mutation plus removal) and
  asserts one read-only doctor result contains both failures, category counts,
  bounded-output metadata, both media IDs, and both recovery command families.

Existing SDK regressions were extended for foreign shot media and foreign
reference media details. Targeted evidence:

```
pytest -q tests/v10/test_doctor.py tests/sdk/test_shots.py tests/sdk/test_references.py
45 passed
```

## Live proof after the fix

Fresh disposable root `/tmp/astrid-doctor-fix-final-BeNWEM`:

1. Baseline external-only media path: doctor exited 0 and reported
   `external_local integrity verified (1 locator(s))`.
2. Appended bytes: doctor exited 1 with `hash mismatch`, media/location/project
   identifiers, expected/found SHA-256, and verify/relocate recovery commands.
3. Restored the original bytes using public `media relocate` and `media verify`;
   recovery succeeded.
4. Removed the external bytes: doctor exited 1 with `unavailable` and the same
   actionable recovery guidance.
5. Recreated bytes and recovered again using public relocate + verify.
6. Created `.astrid/media/.staging/live-abandoned`; doctor returned an optional
   warning naming the exact path and safe cleanup guidance. Strict optional
   mode remains the explicit exit-1 policy (covered by the regression).
7. Removed only the disposable fixture staging/root; final doctor returned 0.

No user files or production roots were touched. No implementation path creates
receipts or mutates data during doctor.

## Replay extension: aggregate external failures

Fresh disposable root `/tmp/astrid-doctor-aggregate-live-4SoDyh` held two
`external_local` files in one project. After mutating the first and removing
the second, public `astrid doctor --json` returned exit 1 and one `media_paths`
failure containing:

```
checked 2 locator(s), failed 2 (hash_mismatch=1, unavailable=1)
showing 2/2; cap=8; ... truncated=0
```

Both media IDs, locator IDs, project identity, expected/found hash (for the
mutation), and `media relocate`/`media verify` commands were present. Recreating
the disposable bytes and running public relocate plus verify for each media ID
returned doctor exit 0 with `external_local integrity verified (2 locator(s))`.
The fixture root was removed after the replay.
