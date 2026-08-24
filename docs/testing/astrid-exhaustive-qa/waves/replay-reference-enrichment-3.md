# Replay: reference enrichment 3

## Scope

Fresh black-box LIVE UX replay using only the public `python3 -m astrid` CLI. No
source, tests, git state, or prior QA artifacts were consulted. The run used a
temporary `ASTRID_PROJECTS_ROOT` and was cleaned after capture.

## Positive path

- Created project `replay-reference-enrichment-3` (project ID
  `b6040466-8146-5912-8859-88b5bf8896fe`).
- Imported two distinct media rows:
  - canonical: `9bf081f1-4193-5be6-b0f1-0cc9792143ac`
  - secondary: `ee450a6b-063d-5ff7-8e77-543f95f56cb9`
- Created the unique `character` reference `Replay Hero 3 Unique` (reference
  ID `dc62c270-0223-5ac7-a4b0-4c6d69481033`) with nested reference metadata.
- The create response contained the canonical association in ordinal order:
  `ordinal: 0`, `role: canonical`, `is_primary: true`, empty association
  metadata.
- Associated the secondary media with `role: depicts`, `ordinal: 1`,
  `is_primary: false`, and metadata `{ "confidence": 0.88, "shot":
  "secondary" }`.
- `media references show` by exact ID and by the unique human name returned
  identical `.data` read models: same identity, description, kind, nested
  metadata, ordered media associations, association IDs/media IDs, roles,
  ordinals, primary flags, and association metadata.
- Archived the reference, then repeated both show selectors. The returned
  `.data` models again matched exactly, including the same non-null
  `archived_at` and preserved associations. `list --include-archived` exposed
  the archived row for recovery.

## Negative and recovery checks

| Case | Observed result | Mutation guard |
| --- | --- | --- |
| Duplicate name (`Ambiguous Replay Name`, two refs) | `validation_error`, `details.reason: ambiguous_display_name`, both exact candidate IDs, and recovery instruction to list inclusively then retry by ID | `data: null`, `receipt: null`, exit 1 |
| Missing name (`Missing Replay Name`) | `not_found` with project ID, ref, and list/retry recovery | `data: null`, `receipt: null`, exit 1 |
| Foreign project slug + exact local reference ID | `not_found`; reference is scoped to the foreign project | `data: null`, `receipt: null`, exit 1 |
| Foreign project UUID + exact local reference ID | Same typed `not_found` and recovery | `data: null`, `receipt: null`, exit 1 |
| Foreign project slug + unique local reference name | Same typed `not_found`; no cross-project name leakage | `data: null`, `receipt: null`, exit 1 |
| Foreign project UUID + unique local reference name | Same typed `not_found`; no cross-project name leakage | `data: null`, `receipt: null`, exit 1 |

The inclusive list and exact-ID retry recovered the first duplicate candidate,
returning its complete read model. A post-negative inclusive list remained the
same three-reference set (one archived unique ref and two active duplicates),
with no error-path-created rows or changed associations.

## Verdict

**PASS.** Exact-ID and unique-name reads are equivalent full read models for
active and archived references. Ambiguous names fail closed with typed
candidates and recovery guidance; missing and foreign-project selectors fail
closed without mutation or cross-project leakage.
