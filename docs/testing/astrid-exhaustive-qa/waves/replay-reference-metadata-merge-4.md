# Replay: reference metadata merge and composite safety 4

Date: 2026-08-24

Mode: independent black-box live agent usage. Product interaction used only
public Astrid CLI/help. A disposable generic media fixture and shell hashes
were used for evidence. No source, tests, or product edits were made during
the replay.

Fresh root: `/tmp/astrid-reference-merge-replay-z8Uo26`
Project: `ref-merge`
Media id: `ba7ba476-48ae-5faa-bf16-3a38e50e3bcc`
Media hash: `a993dd0bb1fc40ad7de95ef3639546a33af7f6949b7c0c27be6ee6913068dac9`

## Verdict

**PASS.** Reference metadata updates are shallow merges, explicit `{}` is a
clear operation, duplicate-name recovery fails closed with candidate IDs,
archive/unarchive preserves relationships and is safely repeatable, and shot
item removal is composite-safe: it removes only the shot item while preserving
the kernel media row, managed CAS locator, content hash, and bytes.

## Metadata update journey

Created a managed generic media file and two references with the same project
name `Character`. Reference one started with:

```json
{"color":"red","traits":{"age":7},"tags":["a","b"]}
```

The public update command changed only one key:

```bash
python3 -m astrid media references update 1bd1b983-547e-507d-ac34-bfe007fe9aa2 \
  --project ref-merge --metadata '{"color":"blue"}' --json
```

The returned and subsequent `show` metadata was:

```json
{"color":"blue","traits":{"age":7},"tags":["a","b"]}
```

This confirms a shallow key merge that preserves untouched keys and nested
values. Sending explicit empty metadata:

```bash
python3 -m astrid media references update 1bd1b983-547e-507d-ac34-bfe007fe9aa2 \
  --project ref-merge --metadata '{}' --json
```

returned and persisted `metadata: {}`. The clear behavior is explicit and
does not accidentally retain the previous object.

## Duplicate-name recovery and archive lifecycle

The two reference IDs were:

- `1bd1b983-547e-507d-ac34-bfe007fe9aa2`
- `4ea04a0e-68ae-5aff-880e-8caf9b77ffb1`

Archived both by exact ID. Inclusive public list showed both archived rows.
Attempting `media references unarchive Character --project ref-merge --json`
failed closed with:

```json
{
  "code": "validation_error",
  "message": "reference recovery name is ambiguous; use an exact id",
  "details": {
    "candidate_ids": [
      "1bd1b983-547e-507d-ac34-bfe007fe9aa2",
      "4ea04a0e-68ae-5aff-880e-8caf9b77ffb1"
    ],
    "recovery": "run 'media references list --include-archived' and retry unarchive with one exact id",
    "ref": "Character"
  }
}
```

Unarchiving the first exact ID returned `changed: true`, preserved
`media_references: 1`, and restored the reference to `active`. Repeating the
same unarchive returned `changed: false` with the same preserved counts. The
second duplicate remained archived, demonstrating deterministic name
ambiguity and safe exact-ID recovery.

## Shot removal and media preservation

Created shot `88de44ab-6d2a-5d1f-a3a8-7add51ff738e` and added the imported media
as item `f0e8a99a-3b1e-5c68-8dfc-89987cdc79f7`. Before removal, public media
readback reported:

- content hash `a993dd0bb1fc40ad7de95ef3639546a33af7f6949b7c0c27be6ee6913068dac9`;
- managed locator
  `/private/tmp/astrid-reference-merge-replay-z8Uo26/.astrid/media/sha256/a9/93/a993dd0bb1fc40ad7de95ef3639546a33af7f6949b7c0c27be6ee6913068dac9`;
- 24-byte content whose shell SHA-256 matched the kernel hash.

The first intuitive attempt passed the media ID to `shots remove`; public CLI
returned typed `not_found` and changed nothing. Help clarified that removal
takes the shot item ID. Retrying with the exact item ID succeeded, returned an
empty `item_ids` list, and left the shot with zero items.

After removal, public `media show` returned the same media ID, content hash,
managed locator, 24-byte size, and managed-local location. The shell hash was
identical before and after removal. Thus shot removal does not delete or alter
shared media bytes.

## UX assessment

- **Metadata merge/clear: 10/10.** The update delta is intuitive and explicit
  `{}` clearing is durable.
- **Duplicate recovery: 10/10.** Ambiguity fails closed with candidate IDs and
  a precise inclusive-list/exact-ID recovery command.
- **Archive lifecycle: 10/10.** Relationships are preserved and repeat
  unarchive is a clear `changed:false` no-op.
- **Composite safety: 9/10.** Media survives shot removal byte-for-byte. The
  only minor friction was that the remove command requires the shot item ID,
  not the media ID; the public help documents this distinction and the failed
  attempt was side-effect-free.

Overall: **9.75/10 — PASS.**
