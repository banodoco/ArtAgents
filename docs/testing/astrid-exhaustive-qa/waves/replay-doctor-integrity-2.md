# Replay: doctor external integrity 2

Date: 2026-08-23 (Europe/Berlin)

Verdict: **PASS with one bounded diagnostic limitation**. The public CLI detects external-local byte mutation and missing locations, includes actionable identity/location/recovery data, does not mutate state during doctor, recovers both locations through public `media relocate`/`media verify`, and makes orphan staging warning severity explicit. In the combined mutation+missing run, doctor reports the first failing external location only; the missing location is reported when isolated.

## Scope and black-box boundary

- Fresh disposable root: `/tmp/astrid-doctor-integrity-KOUP16`.
- No source, test, or git changes were made for the replay.
- Only public help/CLI commands were used (`python3 -m astrid ...`); no direct SDK/database access was used to drive behavior.
- Projects: `integrity-a` (`fd2d817f-5d37-583e-93e3-c52a1ff6eb01`) and `integrity-b` (`eeaab762-9198-5801-a8d3-ec19725412c3`).

## Baseline coverage

Imported into `integrity-a`:

| Realm | Media id | Locator | SHA-256 |
| --- | --- | --- | --- |
| `managed_local` | `8b7f799b-a2b1-59b6-af61-12c4ba5b860e` | `/private/tmp/astrid-doctor-integrity-KOUP16/projects/.astrid/media/sha256/b1/ff/b1ff9c8ea3a780bad09b346c423d2d0e46815926879b18e841d928376a946640` | `b1ff9c8ea3a780bad09b346c423d2d0e46815926879b18e841d928376a946640` |
| `external_local` | `87d139f0-2321-5973-93ef-1acc0a052a01` | `/tmp/astrid-doctor-integrity-KOUP16/fixtures/external-a.png` | `dece5c4e3b7c24a38cdc687010d56cdc0b58c9b96c728d8c604fa6f941ab1a0a` |
| `external_local` | `d736aa20-6f79-537e-8a9f-240c0dd8d2ca` | `/tmp/astrid-doctor-integrity-KOUP16/fixtures/external-b.png` | `e470eefbbd8572ee1b7814ea20038a74f2df1fc5d03749095a9519b65d348930` |

`python3 -m astrid doctor --json --projects-root ...` returned `ok: true`, all required checks `status: ok`, and the required media detail explicitly said:

> `managed-media sha256 tree accessible; managed locators resolve; external_local integrity verified (2 locator(s))`

Normal and `--strict-optional` baseline both returned healthy.

## Mutation and deletion

Appended `ASTRID-QA-MUTATION` to `external-a.png` and removed `external-b.png`.

The combined normal and strict doctor runs both returned `ok: false` with a required `media_paths` failure. The bounded entry named:

- locator id `01m0qzjsj4av9g9twfgz22dvx0`;
- media `87d139f0-2321-5973-93ef-1acc0a052a01`;
- project slug/id `integrity-a` / `fd2d817f-5d37-583e-93e3-c52a1ff6eb01`;
- exact locator `/tmp/astrid-doctor-integrity-KOUP16/fixtures/external-a.png`;
- expected hash `dece5c4e3b7c24a38cdc687010d56cdc0b58c9b96c728d8c604fa6f941ab1a0a`;
- found hash `93a65b92f7955a5e2e0b2d007401e6f93a44172b6c9bca7a83d6853b5b14fd56`;
- exact public recovery guidance: `astrid media relocate 87d139f0-2321-5973-93ef-1acc0a052a01 --project integrity-a --realm external_local --locator <source-file>`;
- exact public verification guidance: `astrid media verify 87d139f0-2321-5973-93ef-1acc0a052a01 --project integrity-a --realm external_local`.

The combined report stops after this first failure. To cover the deleted location independently, `media verify d736aa20-6f79-537e-8a9f-240c0dd8d2ca --project integrity-a --realm external_local --json` returned `integrity_error`, with `media_id`, `realm`, recovery text (`restore the external file, or run media relocate with --realm external_local --locator <source-file>`), and message `no write occurred`.

After restoring only `external-b.png`, an isolated doctor run returned `ok: false` and a required entry naming locator id `01m0qzjtpm8zdya9d2n8mz65ah`, media `d736aa20-6f79-537e-8a9f-240c0dd8d2ca`, project slug/id, exact missing locator, and the exact public relocate and verify commands for that media. No expected/found hash was emitted for the unavailable path, as expected.

## Doctor read-only / no-mutation evidence

Immediately before the combined doctor run, `projects show integrity-a` reported `event_head_seq: 4`; immediately after it, it still reported `event_head_seq: 4`. `media list` and both `media show` read models remained present with the same media ids, hashes, locators, and `verified_at: null`; doctor did not rewrite the failed rows or issue receipts. In a final repeat, SQLite file stat was identical across doctor (`1787511367:380928` before and after), and doctor’s JSON had no receipt envelope.

## Public recovery

Restored the original bytes, then used only public commands:

1. `media relocate 87d139f0-2321-5973-93ef-1acc0a052a01 --project integrity-a --realm external_local --locator /tmp/astrid-doctor-integrity-KOUP16/fixtures/external-a.png`
2. `media verify 87d139f0-2321-5973-93ef-1acc0a052a01 --project integrity-a --realm external_local`
3. `media relocate d736aa20-6f79-537e-8a9f-240c0dd8d2ca --project integrity-a --realm external_local --locator /tmp/astrid-doctor-integrity-KOUP16/fixtures/external-b.png`
4. `media verify d736aa20-6f79-537e-8a9f-240c0dd8d2ca --project integrity-a --realm external_local`

Both relocate and verify succeeded, preserving media identity and restoring the expected SHA-256 values. Normal doctor then returned `ok: true` with `external_local integrity verified (2 locator(s))`.

## Orphan staging semantics

Created `/private/tmp/astrid-doctor-integrity-KOUP16/projects/.astrid/media/.staging/orphan-qa-integrity-20260823`.

- Normal doctor: `ok: true`; `media_paths` was `required: false`, `status: warn`, and named the concrete bounded path. Guidance was non-destructive: after confirming no active media command owns it, remove only the listed staging directories.
- `--strict-optional`: `ok: false` while the same check remained optional/warn, making the policy difference explicit.
- A filesystem check confirmed the orphan directory was still present after both doctor runs; doctor did not delete it.

The final state therefore has healthy normal doctor plus the intentional optional orphan warning; strict-optional is expected to fail until that disposable staging directory is manually cleaned.

## Foreign-project ownership/retry guard

Imported the managed fixture into `integrity-b` as media `411eaf7f-1dee-50aa-a11d-ceb96cd150a2`, created shot `b2448424-2d56-5545-bb95-ae7a6347b026` in `integrity-a`, then attempted to add the foreign media through the public shot command. It returned `validation_error` with:

- `reason: foreign` and entity `shot_media`;
- offending `media_id`, target `project_id`, and `shot_id`;
- retry guidance: run ``astrid media list --project <project>`` to choose a media id owned by the target project, then retry the shot command.

The target project `event_head_seq` stayed `9` before and after, and the shot remained `items: []`; the failed cross-project request emitted `receipt: null`.

## Cleanup

Only the disposable `/tmp/astrid-doctor-integrity-KOUP16` root and its fixture files were removed after evidence capture. No repository source/tests were changed.
