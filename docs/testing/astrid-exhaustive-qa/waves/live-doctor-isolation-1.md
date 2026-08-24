# Live doctor/isolation wave 1

Date: 2026-08-23 (Europe/Berlin)

Verdict: **PASS with one P1/P2 diagnostic gap**. The public CLI kept project
boundaries intact and all intentionally damaged managed state was diagnosed and
recovered. `doctor` is read-only and accurately diagnoses missing managed bytes
and abandoned staging. It does not inspect `external_local` bytes or locators,
so external mutation and stale external locators are false negatives for
`doctor`; `media verify` provides the actionable integrity diagnosis and
`media relocate` provides recovery.

## Scope and fixture

No source, test, database, or user files were edited. The disposable fixture was
`/tmp/astrid-live-doctor-isolation-GeEoym` (project root
`$ROOT/projects`), with `ASTRID_PROJECTS_ROOT` set to that root for every
command. It contained two projects:

| project | media | references | shots | timelines |
| --- | --- | --- | --- | --- |
| `alpha` | 2 (managed + external) | `AlphaChar` | `AlphaShot` | `alpha-timeline` |
| `beta` | 2 (managed + external) | `BetaChar` | `BetaShot` | `beta-timeline` |

Managed content hashes were `9f5dda5758c1855c2e0f49b21aa23f7fe2142d152d6491185e09f448cf4d1aa3`
(A) and `8383afa6c0cf0a585e0ec12e7d342548d34ea4243cd5db9c52fb33d1dee22af2`
(B). External content hashes were
`c1821525b8561c0a277c3dc7d0e5a9417cf2f7a0653186ebcdc62cd65539e745` (A) and
`a7d69ee1389023be2667bb6ccf62cfb153114b91df1d4e338dbf30e33e7ca9e6` (B).

The initial empty-root `doctor --json` correctly returned exit 1 with missing
`.astrid`, database, and schema diagnostics. After project creation and media
import, the baseline doctor returned exit 0:

```
python3 -m astrid doctor --json
# ok=true; data_paths, media_paths, sqlite_quick_check, fk_integrity,
# schema_versions all ok
```

## Cross-project isolation

The following IDs were intentionally mixed:

```
A media managed: 9545b636-e78a-5298-8ea1-6d7b70445415
A media external: dfdab220-42b2-5116-8279-08bd9e467efc
B media managed: 806bdb2f-a2f7-53a3-86e6-b7ad9da92079
B media external: 47e37a51-feee-59ac-8062-0d65cd8e9883
A shot: ecbed12e-b017-5eae-8fa8-4a7325b85fc2
B shot: b70f7c38-2710-5d54-b7d7-cf954dbeeeed
A reference: 31e87431-6465-5900-a3e8-9acc53a3c2f7
B reference: d947b6af-7c91-5989-8af1-b3091655b5c4
```

Commands run against `--project beta` with A IDs (and the reverse relation)
were:

```
media verify A-managed --realm managed_local
media verify A-external --realm external_local
media relate --from A-managed --to B-managed --kind derived_from
media relate --from B-managed --to A-managed --kind derived_from
timelines shots add B-shot --media A-managed
timelines save alpha-timeline --config '{"fps":99}' --registry '{"scene":"WRONG"}' --expected-version 1
media references associate B-reference --media A-managed --role depicts
media references associate A-reference --media B-managed --role depicts
media references link --from A-reference --to B-reference --kind related_to
media references set-primary B-reference --media-reference A-association
```

Every command exited 1 with a typed JSON error and no receipt. The two media
verify calls and both relation attempts returned `not_found`; timeline save
returned `not_found` with `entity`, `project_id`, `ref`, and recovery guidance
to list the project timelines; shot add and reference association/link/set-
primary returned `validation_error` (the exact stable error is less actionable
than the timeline error, but still failed closed).

Before/after JSON read-model hashes were identical for both projects:

| read model | before/after SHA-256 | result |
| --- | --- | --- |
| alpha media list | `667ab12ad9a27f74cc5920994e3ff557181d037dc78735eed6131d27e7716b8c` | unchanged |
| beta media list | `7a38409ad09a22889c202321a274f7d6dfd44e7dd9d0a4ba5ee92743d4689bfd` | unchanged |
| alpha references | `19bd930b1067b293e6b39e5fe27436957b82148ed90ecc92cbe9d5bb6d7fe15e` | unchanged |
| beta references | `87639110fc00f85630471217a8fba5984dbc8fc42ff2a1f95e51d95740849cb0` | unchanged |
| alpha shot | `7247ddb5aa3be4c595a6d2aa7e41298187e7536d120ee362a7e2aa665f776c28` | unchanged |
| beta shot | `fa3ddde3c6edfbfd080369d6f4bc6ebf877d1f40af70f6f1a4bd99e61cac50c2` | unchanged |
| alpha timeline | `14bdc53908099a0400bdf27b3ab4b23376e23849ace06d2fe35974e54538e986` | unchanged |
| beta timeline | `418a8079ad09a22889c202321a274f7d6dfd44e7dd9d0a4ba5ee92743d4689bfd` | unchanged |

Final counts remained two media, one reference, one shot, and one timeline per
project; both shots still had zero items. This is a strong zero-mutation result
for both sides of the boundary.

## Doctor and diagnosis drills

### Missing managed bytes — P0/P1 pass

The A managed canonical file was removed from the disposable managed SHA-256
tree. Its pre-removal and source hash were both
`9f5dda5758c1855c2e0f49b21aa23f7fe2142d152d6491185e09f448cf4d1aa3`.

```
python3 -m astrid doctor --json
```

Exited 1, with `media_paths` required/fail and the exact locator ID, path, and
public remedy “restore or relocate the media”; SQLite quick check, foreign keys,
and schema checks stayed green. Recovery used only the public command:

```
python3 -m astrid media relocate 9545b636-e78a-5298-8ea1-6d7b70445415 \
  --project alpha --realm managed_local \
  --source "$ROOT/external-A/a-managed.txt" --json
```

The command preserved the media ID and hash, recreated the canonical bytes, and
the following doctor returned exit 0. The recreated file hash matched the source
exactly.

### Mutated external bytes — P1 false negative in doctor; verify pass

`$ROOT/external-A/a-external.txt` was appended with `MUTATED`, changing its hash
from `c1821525...39e745` to
`4101314f98c654d202bbc8b770dc61c49c04453ba185c6ca34c852cfc247b0a0`.
`doctor --json` still exited 0 and reported healthy managed paths. This is a
false negative: the doctor contract currently checks managed locators only.

```
python3 -m astrid media verify dfdab220-42b2-5116-8279-08bd9e467efc \
  --project alpha --realm external_local --json
```

Exited 1 with typed `integrity_error` and no receipt. Recovery copied the known
good bytes to a disposable restored path and used the public external relocate:

```
python3 -m astrid media relocate dfdab220-42b2-5116-8279-08bd9e467efc \
  --project alpha --realm external_local \
  --locator "$ROOT/external-A/a-external-recovered.txt" --json
python3 -m astrid media verify dfdab220-42b2-5116-8279-08bd9e467efc \
  --project alpha --realm external_local --json
```

Verify then exited 0, restored the `verified_at`, and preserved the original ID
and hash. Doctor returned exit 0 afterward.

### Abandoned staging — P2 pass, optional warning semantics

An abandoned disposable directory was created at
`$ROOT/projects/.astrid/media/.staging/abandoned-live-probe/partial.bin` with
SHA-256 `96e1d5a246bb7c3463385dc91b6dec1b4c9d325e7f29ad01af3158cbae56dd8e`.
Normal doctor exited 0 but emitted an optional warning:

```
1 orphaned staging director(ies) under .../.astrid/media/.staging
```

`doctor --json --strict-optional` exited 1 with the same warning and all required
checks green. No public reaper command was exposed; the disposable staging
directory was removed as fixture cleanup. This is appropriate non-mutating
diagnosis, but the warning could include the offending directory name and an
explicit safe cleanup command.

### Stale external locator / backup flow — P1 false negative in doctor

Using the public command only, B external media was relocated to the future
locator `$ROOT/stale-root/relocated-b.bin` (which did not exist). The relocate
receipt preserved the media ID/hash and set `verified_at` null. Doctor still
returned 0 because this was an external locator. Public verify exited 1 with
`integrity_error`, `media_id`, `realm`, and recovery text directing the operator
to restore the file or run external `media relocate --locator <source-file>`.

The original B external locator was restored via public external relocate, then
verify and doctor both returned 0. A public backup create/restore was also
exercised:

```
python3 -m astrid backup create --out "$ROOT/backup" --projects-root "$ROOT/projects"
python3 -m astrid backup restore "$ROOT/backup" --projects-root "$ROOT/restored/projects"
```

Backup reported two managed media files and 97 SQLite pages; restore reported
two media files. Doctor on the restored disposable root returned 0, with managed
locators rewritten to the restored root while external locators remained the
original absolute paths. This confirms backup/restore is usable, while also
illustrating why external locator verification must remain an explicit operator
step.

## Non-mutation and final health

Doctor emitted no receipts and made no visible read-model changes. Staging
strict-mode was tested with the fixture present and the fixture was then
cleaned. Final public state was two projects; two media, one reference, one shot,
and one timeline in each; zero shot items; and original media IDs/hashes intact.
Final managed hashes were unchanged. Final external hashes were
`c1821525b8561c0a277c3dc7d0e5a9417cf2f7a0653186ebcdc62cd65539e745` and
`a7d69ee1389023be2667bb6ccf62cfb153114b91df1d4e338dbf30e33e7ca9e6`.
Final doctor returned exit 0.

## Findings, false positives/negatives, and wrong turns

- **P1 — doctor misses external-local mutation and stale/missing external
  locators.** `media verify` catches both and gives recovery guidance, but a
  scheduled doctor-only health check can report `ok=true` while an external
  asset is unusable. Either extend `doctor` to inspect external locations or
  clearly label it as managed-only and make the verify sweep an explicit public
  health operation.
- **P2 — abandoned staging is correctly detected without mutation.** Normal
  doctor remains `ok=true` because it is optional; strict optional correctly
  exits 1. Include the concrete orphan path and cleanup guidance in the warning.
- **P2 — some cross-project failures are generic `validation_error`.** They all
  fail closed and leave both projects byte-for-byte/read-model unchanged, but
  project-aware details would make a mistaken ID/slug easier to fix than the
  generic message.
- No false positive was observed: healthy managed state, healthy external state
  after recovery, clean staging, backup-restored managed state, and valid
  project-local operations all passed.
- Wrong turn: the initial help loop passed each multiword command as one shell
  argument and produced usage errors; it was corrected before fixture creation
  and caused no state mutation.

No implementation changes were made. Only disposable fixture roots were
created, damaged, recovered, and cleaned.
