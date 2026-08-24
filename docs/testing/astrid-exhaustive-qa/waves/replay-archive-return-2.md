# Replay archive return 2 — live agent UX replay

Date: 2026-08-23  
Surface: public `python3 -m astrid` CLI only  
Disposable root: `/tmp/astrid-replay-archive-return-2.78VMVF` (cleaned after this report)

## Scope and constraints

This was a fresh black-box replay. I used the root/family `--help` surfaces, the
Astrid skill, CLI calls, and CLI read-backs only. I did not inspect source,
tests, git diff, prior QA reports, or implementation notes. No product code was
modified. Phase B was a fresh shell and treated the Phase A handoff as only the
project slug `replay-archive-return-2`; timeline/reference/media IDs were
rediscovered from inclusive list calls.

## Phase A — create, save, archive

Commands (all with `ASTRID_PROJECTS_ROOT` set to the disposable root):

```text
python3 -m astrid --help
python3 -m astrid doctor --json
python3 -m astrid projects create replay-archive-return-2 --name "Replay Archive Return Two" --settings '{"replay":"archive-return-2"}' --json
python3 -m astrid projects show replay-archive-return-2 --json
python3 -m astrid projects list --json
python3 -m astrid timelines create primary --project replay-archive-return-2 --name "Paused Primary" --config '{"paused_note":"initial-note","playhead_seconds":3,"editor_mode":"editing"}' --registry '{"assets":{"fixture":{"kind":"tiny-local"}}}' --default --json
python3 -m astrid timelines show primary --project replay-archive-return-2 --json
python3 -m astrid media import /tmp/astrid-replay-archive-return-2.78VMVF/tiny-local-media.bin --project replay-archive-return-2 --realm external_local --json
python3 -m astrid media list --project replay-archive-return-2 --json
python3 -m astrid media references create --project replay-archive-return-2 --kind character --name "Archive Return Character" --media <imported-media-id> --description "Replay archive return reference" --metadata '{"marker":"REF_MARKER_REPLAY_2"}' --json
python3 -m astrid media references show <reference-id> --project replay-archive-return-2 --json
python3 -m astrid timelines save primary --project replay-archive-return-2 --config '{"paused_note":"REPLAY_ARCHIVE_RETURN_2_PAUSED","playhead_seconds":42.5,"editor_mode":"paused","recognizable_marker":"TIMELINE_MARKER_REPLAY_2"}' --registry '{"assets":{"fixture":{"kind":"tiny-local","media_id":"MEDIA_ASSOCIATION_EXPECTED"}},"reference_name":"Archive Return Character"}' --expected-version 1 --json
python3 -m astrid timelines history --project replay-archive-return-2 primary --json
python3 -m astrid media references archive <reference-id> --project replay-archive-return-2 --json
python3 -m astrid timelines archive primary --project replay-archive-return-2 --json
python3 -m astrid timelines list --project replay-archive-return-2 --include-archived --json
python3 -m astrid media references list --project replay-archive-return-2 --include-archived --json
```

Evidence:

- The tiny local fixture imported as one 32-byte media row with a stable
  content hash and one `external_local` location.
- Timeline create returned `is_default: true`, `config_version: 1`; save
  returned `config_version: 2` and the recognizable paused marker/config.
- Reference creation returned one canonical media association. The archived
  reference reported `preserved: {events: 1, media_references: 1,
  reference_links: 0}`.
- Timeline archive returned `config_version: 3`; inclusive lists showed one
  archived timeline (`primary`) and one archived named reference.
- After project creation, `doctor --json` passed (`quick_check ok`, no foreign
  key violations, `core=1, references=1, shots=1, timeline=1`).

## Phase B — rediscover, restore, repeat, resume

The first operations in the fresh shell were:

```text
python3 -m astrid --help
python3 -m astrid timelines list --project replay-archive-return-2 --include-archived --json
python3 -m astrid media references list --project replay-archive-return-2 --include-archived --json
```

Recovery used the rediscovered timeline slug and reference name, without an
ID shortcut:

```text
python3 -m astrid timelines unarchive primary --project replay-archive-return-2 --json
python3 -m astrid timelines unarchive primary --project replay-archive-return-2 --json
python3 -m astrid media references unarchive "Archive Return Character" --project replay-archive-return-2 --json
python3 -m astrid media references unarchive "Archive Return Character" --project replay-archive-return-2 --json
```

The first timeline/reference calls returned `changed: true`; the repeats
returned `changed: false`. The repeat responses retained the same timeline
`config_version: 4` and reference preserved count (`events: 3,
media_references: 1, reference_links: 0`), demonstrating no duplicate
mutation/event on idempotent retries.

Read-back then showed exactly one active timeline, one active reference, and
one media row in the primary project. The restored reference's canonical
`media_id` exactly matched the sole media row's ID. The timeline identity
(slug/ULID/kernel ID), default flag, saved paused note, playhead, editor mode,
recognizable marker, and registry were unchanged from the archived read-back.

Resume editing:

```text
python3 -m astrid timelines save primary --project replay-archive-return-2 --config '{"paused_note":"REPLAY_ARCHIVE_RETURN_2_PAUSED","playhead_seconds":42.5,"editor_mode":"paused","recognizable_marker":"TIMELINE_MARKER_REPLAY_2","resume_marker":"RESUMED_REPLAY_ARCHIVE_RETURN_2"}' --registry '{"assets":{"fixture":{"kind":"tiny-local","media_id":"MEDIA_ASSOCIATION_EXPECTED"}},"reference_name":"Archive Return Character"}' --expected-version 4 --json
python3 -m astrid timelines show primary --project replay-archive-return-2 --json
python3 -m astrid timelines history --project replay-archive-return-2 primary --json
python3 -m astrid media references show <rediscovered-reference-id> --project replay-archive-return-2 --json
```

The save returned `config_version: 5`; the read-back preserved all paused
fields and added `resume_marker`. Timeline history contained the ordered
`timeline.created` v1, `timeline.saved` v2, `timeline.archived` v3,
`timeline.unarchived` v4, and `timeline.saved` v5 rows. The reference retained
the original name, kind, metadata, description, identity, and canonical media
association.

## Ambiguity / fail-closed recovery

In a separate disposable project (`replay-archive-return-2-ambiguity`), I
imported one fixture, created two archived references with the same name
`Ambiguous Archive Return` (different kinds), and ran:

```text
python3 -m astrid media references list --project replay-archive-return-2-ambiguity --include-archived --json
python3 -m astrid media references unarchive "Ambiguous Archive Return" --project replay-archive-return-2-ambiguity --json
python3 -m astrid media references list --project replay-archive-return-2-ambiguity --include-archived --json
```

The name-based call exited 1 with `validation_error`, message
`reference recovery name is ambiguous; use an exact id`, both candidate IDs,
and actionable guidance to rerun the inclusive list and retry with one exact
ID. The before/after inclusive lists contained the same two IDs and both
remained archived, proving no mutation on the failed recovery.

## Wrong turns and friction

1. Running `doctor --json` before the first product command on an empty root
   exited 1 because `.astrid/astrid.sqlite3` did not exist. The diagnostic
   explicitly directed project creation to initialize the store. After
   creation, doctor passed.
2. The timeline-create DTO uses `timeline_id` and `config_version`, not the
   generic `id`/`version` keys my first extraction attempted. Public
   `timelines show` corrected the extraction; no incorrect product mutation
   resulted.
3. Recovery requires an inclusive list to discover archived records, but then
   supports the human-friendly timeline slug and unambiguous reference name;
   no default-timeline preference was needed.

## Verdict

PASS. The live archive-return journey restored the exact timeline and named
reference from inclusive discovery, preserved configuration, history, event
counts, identity, and canonical media association, made repeated unarchive
requests no-ops (`changed:false`), resumed editing, and kept the primary
project at exactly one timeline, one reference, and one media row. Ambiguous
name recovery failed closed with candidate IDs and retry guidance without
mutation. Root help exposed the expected eight families (five product,
three operational) plus the two nested mounts.
