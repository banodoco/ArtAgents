# Live UX wave: stale collaborative timeline save

Date: 2026-08-23  
Surface: `python3 -m astrid` public CLI only  
Mode: live agent usage (no programmatic tests, no source/test inspection)  
Project root: `/tmp/astrid-live-conflict-jd4gkY` (fresh, unique `mktemp` root)

## Goal and verdict

I acted as two editors with the same initial read of timeline document version 1:

1. Create project `collaborative-cut` and default timeline `primary`.
2. Editor A adds a title track and saves from version 1.
3. Editor B, still holding its independent version-1 document, adds a captions
   track and attempts to save.
4. Preserve both edits without overwriting either one.
5. Use the public history/diff surfaces to explain the conflict and recovery.

Outcome: PASS. Astrid prevented the stale whole-document save, retained editor
A's title track, and allowed a reread/merge that produced both tracks at version
3. Replaying the successful merge with the same idempotency key returned the
same receipt and did not create a duplicate version or duplicate track.

The core safety behavior is strong. The original live run found a P1 UX gap:
the CLI emitted a typed `stale_version` error but did not include the current
version or a ready-to-merge recovery hint. That gap was remediated and rechecked
in a fresh live run below. `save` remains whole-document, so the agent must
still retain and re-enter all current JSON while resolving the conflict; a
field-level patch/merge API remains intentionally out of scope here.

## Setup and initial orientation

I created the isolated root with:

```text
mktemp -d /tmp/astrid-live-conflict-XXXXXX
=> /tmp/astrid-live-conflict-jd4gkY
```

The first read-only health check against the brand-new root reported expected
missing-data failures (`data_paths`, database, foreign keys, schema), and
explicitly suggested creating a project. This was useful orientation, although
`doctor --json` returned a checks object rather than the five-key product-command
envelope.

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid doctor --json
```

Relevant result:

```json
{
  "checks": [
    {"name":"data_paths","status":"fail","detail":"managed data directory is missing: .../.astrid"},
    {"name":"sqlite_quick_check","status":"fail","detail":"database missing: ... (expected on a brand-new projects root; run `astrid projects create <slug> --name <Name>` to initialize it)"}
  ],
  "ok": false
}
```

I then created the project and read its generated `plan.md`, as a real agent
should when attaching to a project:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid projects create collaborative-cut --name 'Collaborative Cut' --json
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid projects show collaborative-cut --json
sed -n '1,120p' /tmp/astrid-live-conflict-jd4gkY/collaborative-cut/plan.md
```

Project creation succeeded with project sequence 1. The plan was an empty
skeleton with sections for current focus, open threads, key decisions, and
notes; there was no conflict/collaboration guidance there.

Timeline creation:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid timelines create primary --project collaborative-cut --name Primary --default --json
```

The initial timeline document was:

```json
{
  "config": {},
  "config_version": 1,
  "is_default": true,
  "name": "Primary",
  "registry": {"assets": {}},
  "slug": "primary",
  "timeline_id": "5083ee01-a23c-5160-bf29-c585c01f623d",
  "timeline_ulid": "92gqkn0e6f8nz0x4812yz1q1ab"
}
```

I also checked the public save contract:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid timelines save --help
```

The key contract is that `--config`, `--registry`, and
`--expected-version` are all required, and `save` is a whole-document CAS save.
That fact is discoverable, but only if the agent knows to ask for command help.

## Conflict reproduction

Both simulated editors started from the exact version-1 document above.

### Editor A: title track, version 1 → 2

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid timelines save primary --project collaborative-cut --config '{"tracks":[{"id":"title","type":"title","text":"Collaborative Cut"}]}' --registry '{"assets":{}}' --expected-version 1 --idempotency-key editor-a-title-v1 --json
```

Result: `ok: true`, `config_version: 2`, one `timeline.saved` event, and
`idempotency_key: editor-a-title-v1`. The title track was present exactly once.

### Editor B: stale captions write, still expecting version 1

Editor B intentionally did not reread after A's save. Its independent document
contained only its own captions track:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid timelines save primary --project collaborative-cut --config '{"tracks":[{"id":"captions","type":"captions","language":"en","text":"Captions"}]}' --registry '{"assets":{}}' --expected-version 1 --idempotency-key editor-b-captions-v1 --json
```

Astrid rejected it:

```json
{
  "data": null,
  "error": {
    "code": "stale_version",
    "details": {},
    "message": "the write supplied a stale expected version"
  },
  "idempotency_key": "editor-b-captions-v1",
  "ok": false,
  "receipt": null
}
```

The process exited with code 1. This is a good machine-detectable failure: the
error is typed, the write has no receipt, and the current document was not
silently replaced. A retry with the same stale request/key produced the same
`stale_version` response and did not change state.

### Immediate state check

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid timelines show primary --project collaborative-cut --json
```

The current document still contained only A's edit and was version 2:

```json
{
  "config": {
    "tracks": [
      {"id":"title","text":"Collaborative Cut","type":"title"}
    ]
  },
  "config_version": 2,
  "registry": {"assets": {}}
}
```

This proves the stale B write did not overwrite A and did not partially apply.

## Recovery and merge

The safe recovery was:

1. Read the current timeline (version 2).
2. Preserve A's title track from that current document.
3. Add B's captions track to the current document, rather than retrying B's
   stale whole-document payload.
4. Save the merged whole document with `--expected-version 2` and a fresh
   idempotency key for the new logical operation.

Command:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid timelines save primary --project collaborative-cut --config '{"tracks":[{"id":"title","type":"title","text":"Collaborative Cut"},{"id":"captions","type":"captions","language":"en","text":"Captions"}]}' --registry '{"assets":{}}' --expected-version 2 --idempotency-key editor-b-merge-v2 --json
```

Result: `ok: true`, `config_version: 3`, one new `timeline.saved` event, and a
receipt tied to `editor-b-merge-v2`.

The final state contained both tracks exactly once, in the merged document:

```json
{
  "config": {
    "tracks": [
      {"id":"title","text":"Collaborative Cut","type":"title"},
      {"id":"captions","language":"en","text":"Captions","type":"captions"}
    ]
  },
  "config_version": 3,
  "registry": {"assets": {}}
}
```

### Idempotency/retry check

I deliberately replayed the successful merge command with the *same*
`editor-b-merge-v2` key and the original `--expected-version 2`, even though the
timeline was already at version 3:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid timelines save primary --project collaborative-cut --config '{"tracks":[{"id":"title","type":"title","text":"Collaborative Cut"},{"id":"captions","type":"captions","language":"en","text":"Captions"}]}' --registry '{"assets":{}}' --expected-version 2 --idempotency-key editor-b-merge-v2 --json
```

Astrid returned the original successful result, the original event id and
receipt, `config_version: 3`, and exit code 0. It did not create version 4 or a
duplicate track. This is exactly the retry behavior an agent needs after an
ambiguous transport failure.

The practical idempotency rule inferred from live use:

- Reuse the same key when retrying the same logical request; Astrid replays it
  safely, even when the expected version is now stale.
- Use a fresh key only after rereading and intentionally constructing a new
  merged document. The merge correctly used `editor-b-merge-v2`, not the stale
  `editor-b-captions-v1` key.

## History and diff evidence

History command:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid timelines history primary --project collaborative-cut --json
```

History showed exactly three document versions:

```json
[
  {"kind":"timeline.created","version":1,"config":{},"registry":{"assets":{}}},
  {"kind":"timeline.saved","version":2,"config":{"tracks":[{"id":"title","text":"Collaborative Cut","type":"title"}],"registry":{"assets":{}}},
  {"kind":"timeline.saved","version":3,"config":{"tracks":[{"id":"title","text":"Collaborative Cut","type":"title"},{"id":"captions","language":"en","text":"Captions","type":"captions"}],"registry":{"assets":{}}}
]
```

Diff command:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid timelines diff primary --project collaborative-cut --json
```

Diff returned adjacent transitions:

```json
[
  {
    "from_kind":"timeline.created",
    "from_version":1,
    "to_kind":"timeline.saved",
    "to_version":2,
    "document":{"added":["tracks"],"changed":[],"removed":[]},
    "registry":{"added":[],"changed":[],"removed":[]}
  },
  {
    "from_kind":"timeline.saved",
    "from_version":2,
    "to_kind":"timeline.saved",
    "to_version":3,
    "document":{"added":[],"changed":["tracks"],"removed":[]},
    "registry":{"added":[],"changed":[],"removed":[]}
  }
]
```

This is enough to explain that A's save made version 2 and the recovery merge
made version 3. However, the diff is document-key level (`tracks` changed), not
track/field level; it does not say “title came from A, captions came from B,”
because Astrid has no provenance or rejected-write record in the public output.

Final health check:

```text
ASTRID_PROJECTS_ROOT=/tmp/astrid-live-conflict-jd4gkY python3 -m astrid doctor --json
```

All required checks passed: data paths accessible, SQLite quick check OK, no
foreign-key violations, and schema versions `core=1, references=1, shots=1,
timeline=1`.

## UX critique, severity ranked

### P0 — none observed

No data loss, silent overwrite, partial write, duplicate version, or duplicate
track occurred. The CAS fence and idempotency replay are reliable.

### P1 — stale error is safe but not recoverable enough

Observed error:

```json
{"code":"stale_version","details":{},"message":"the write supplied a stale expected version"}
```

For an agent, this establishes *that* the write failed but not what to do next.
It omits the current version (`2`), current timeline identity/document, the
version that won, or a link/command pattern for `show`, `history`, `diff`, and
merge. An agent must infer the recovery protocol from prior help and then make
an extra read. A human user would reasonably wonder whether retrying the same
command is safe or whether their edit disappeared.

What Astrid should have told me:

> Save rejected: timeline `primary` is now version 2, but this request expected
> version 1. Your edit was not applied. Read the current document, merge your
> changes into it, then save with `--expected-version 2`. Reuse the same
> idempotency key only to retry the same logical request; use a new key for the
> merged save. Use `timelines history` or `timelines diff` to inspect the two
> committed versions.

Ideally the error would carry structured fields such as
`expected_version`, `current_version`, `current_document`, and
`recovery_commands` (or a server-side merge/dry-run operation).

### P1 — whole-document save creates a high manual merge burden

The save help makes `--config` and `--registry` mandatory and describes a
whole-document CAS save. To add one track, the agent must resend the entire
config and registry, preserve unrelated fields, and hand-quote nested JSON in a
shell command. The conflict reproduction required keeping two divergent full
documents in working memory. That is fragile for a large timeline and makes
accidental deletion of a collaborator's unrelated change easy.

What Astrid should have told me (or exposed as a safer primitive):

> This is a whole-document replacement. Before saving after a stale-version
> error, reread and preserve every current config/registry field. For additive
> track edits, prefer a patch/merge command that names the track and performs a
> field-level CAS.

A `timelines merge`/`timelines patch` surface with explicit additive operations
would materially lower agent error rates while retaining the CAS guard.

### P2 — diff is too coarse for conflict explanation

`timelines diff` was valuable and easy to invoke, but it reported only that the
top-level `tracks` key changed between versions 2 and 3. It did not identify the
added `captions` item, preserve rejected B payload as an audit artifact, or
show field-level differences. For agent UX, a JSON Patch-like diff (including
array item identity) would make the merge auditable and reduce guesswork.

What Astrid should have told me:

> Version 2 added `tracks[title]`; version 3 added `tracks[captions]`. The stale
> request from editor B was rejected and is available as a proposed change for
> review.

### P2 — history is clear but lacks actor/request provenance

History showed exact versions, kinds, timestamps, and full snapshots, which is
good. It did not expose the idempotency keys, editor labels, request receipt
ids, or the rejected stale attempt. That makes “who changed what” and “why did
the merge happen” harder to explain in a collaborative setting.

What Astrid should have told me:

> Version 2 was committed by `editor-a-title-v1`; editor B's version-1 request
> was rejected as stale; version 3 was committed by `editor-b-merge-v2` after a
> reread/merge.

### P3 — command discovery is good, but not context-sensitive

The top-level census and `timelines save --help` were concise and sufficient to
discover the CAS contract. The error itself did not point back to those commands
or suggest the next read. A short recovery hint in the error would make the
existing surface feel much more self-guiding.

### P3 — fresh-root doctor output is slightly surprising

`doctor --json` on a new root returned `ok: false` and a checks array rather
than the documented five-key product envelope. It did explain that a missing
database is expected before the first project and named the exact bootstrap
command, so this is low severity. It did not block the timeline workflow.

## Agent ergonomics summary

The successful live path was:

```text
create project → create default timeline → show v1
→ editor A save expected 1 (v2)
→ editor B stale save expected 1 (typed failure, no mutation)
→ show v2 → manually merge full JSON
→ save expected 2 (v3) → replay same key (no-op/idempotent)
→ show + history + diff + doctor
```

The safety model is trustworthy and the final evidence is strong. The original
run's conflict-recovery inference burden is now fixed: the stale error names
the expected/current versions, states that no write occurred, and explains the
public show → merge → save and idempotency-key rules. The remaining friction is
that the rejected proposal is not preserved for review and `save` is still a
whole-document replacement without field-level merge. For simple documents
this is manageable; for realistic timelines with many tracks and registry
entries it remains a meaningful source of avoidable agent mistakes.

## Follow-up remediation: actionable stale-version recovery

The confirmed P1 error-UX gap was fixed in the public SDK mapper used by both
the SDK and CLI. The frozen five-key envelope and three-key error object remain
unchanged. A mapped timeline CAS conflict now carries stable machine-readable
details:

```json
{"expected_version": 1, "current_version": 2}
```

Its concise human message states that no write occurred and gives the public
recovery rule: run `timelines show`, merge the proposed edit into the current
whole document, then run `timelines save` with that document's
`config_version` as `--expected-version`. It also says to reuse the same
idempotency key only when retrying the same logical request, and to use a fresh
key for the intentionally new merged save. No patch/merge API was added.

### Fresh live verification after the fix

On a new isolated root, I repeated the two-editor sequence. Editor A committed
the title track at version 2. Editor B then submitted its version-1 captions
document with `editor-b-captions-v1` and received exit code 1:

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

The same guidance appeared in concise human mode. Without source-diving, the
agent could follow it: public `timelines show` still showed only A's title
track at version 2, and public `timelines history` still showed only versions 1
and 2. Thus the rejected B write created no new version, event, or receipt.

The agent then merged the title and captions tracks and saved with
`--expected-version 2` and fresh key `editor-b-merge-v2`; the save committed
version 3 containing both tracks. Replaying that exact merged request with the
same key returned the original receipt and version 3, with no version 4 or
duplicate track. This verifies both the recovery rule and idempotency guidance
through the live public CLI.
