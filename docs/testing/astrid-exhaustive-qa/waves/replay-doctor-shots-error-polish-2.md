# Replay 2: doctor, shots, and reference error polish

Date: 2026-08-24 (Europe/Berlin)  
Method: black-box live agent UX through public `python3 -m astrid` commands
only; no source inspection, test invocation, database editing, or product
changes  
Disposable projects root:
`/private/tmp/astrid-doctor-shots-polish.XquoUY`  
Verdict: **PASS — the requested error and response polish is present, typed,
recoverable, and side-effect-free.**

## Acceptance summary

| Contract | Result |
| --- | --- |
| Fresh doctor JSON identifies healthy uninitialized state | Pass |
| Fresh doctor human output supplies one create-project action | Pass |
| Bootstrap changes doctor to ready with JSON `next_action:null` | Pass |
| Ready human output omits next-action line | Pass |
| Shot remove exposes `removed_item` and remaining count | Pass |
| Shot remove retains legacy `item`, `item_ids`, IDs, and head | Pass |
| Invalid reorder has typed reason, offending IDs, and show/retry recovery | Pass |
| Invalid reorder changes no shot state | Pass |
| Archived-reference association identifies reference and recovery | Pass |
| Archived-reference rejection changes no reference state | Pass |
| Following supplied recovery succeeds | Pass |

## 1. Doctor lifecycle

### Fresh root, JSON

Exact command:

```bash
polish_root=$(mktemp -d /private/tmp/astrid-doctor-shots-polish.XXXXXX)
python3 -m astrid doctor --projects-root "$polish_root" --json
```

Key exact output:

```json
{
  "next_action": "Initialize a project with `python3 -m astrid projects create <slug> --name <Name>`",
  "ok": true,
  "state": "uninitialized"
}
```

All absent-database checks were explicitly `uninitialized`, not failures.
`python_version` and the absence of a managed-media tree were `ok`. Exit code
was 0.

### Fresh root, human

Exact command:

```bash
python3 -m astrid doctor --projects-root "$polish_root"
```

Exact header/action:

```text
Astrid doctor
state: uninitialized
next action: Initialize a project with `python3 -m astrid projects create <slug> --name <Name>`
```

The path and database lines then explained that uninitialized state was
expected on a brand-new root. Exit code was 0.

### Bootstrap and ready state

Exact bootstrap:

```bash
ASTRID_PROJECTS_ROOT="$polish_root" \
python3 -m astrid projects create polish-lab \
  --name 'Polish Lab' --json
```

Project ID:
`243c342d-5b5d-593e-a9f4-b51288c7e849`.

The subsequent JSON doctor returned:

```json
{
  "next_action": null,
  "ok": true,
  "state": "ready"
}
```

All checks were `ok`, including `quick_check`, foreign keys, and schema
versions `core=1, references=1, shots=1, timeline=1`. Human output began:

```text
Astrid doctor
state: ready
[ok] python_version: 3.11.11
```

and correctly contained no `next action:` line. Both ready commands exited 0.

Agent UX assessment: the lifecycle is unambiguous. A new root is not falsely
presented as broken, there is exactly one useful action, and that action
disappears once completed.

## 2. Shot fixture

Three 64×64 PNG inputs were created in the disposable fixture directory and
imported through `astrid media import`:

| Color | Media ID | Content hash |
| --- | --- | --- |
| red | `d50ef1c4-8a9c-5719-87af-8576de8cd93a` | `e673e1a7...877ba4` |
| green | `e486257c-a54b-5e27-b789-988103d03c6a` | `5ace4b15...165b09` |
| blue | `17356523-04f7-5f8c-87a9-391dd4fc7291` | `bff1b410...4802ae` |

The public shot command:

```bash
python3 -m astrid timelines shots create \
  --project polish-lab --name 'Color Sequence' \
  --metadata '{"purpose":"error-polish"}' --json
```

created shot `a95fdc6d-5ca2-5830-b1cb-333859e25dc5`. Three public `shots add`
calls produced these ordered item IDs:

```text
red   8e032930-855c-5588-9306-131bb647fb7b
green d5eeec1b-5918-54b9-bcf0-fd72a39ad09b
blue  862fdc7f-3527-55ad-99fc-a42f3078f1ce
```

The baseline `shots show` had `event_head_seq:4`, positions `0,1,2`, and the
same item order.

## 3. Invalid reorder diagnostics and zero mutation

### Duplicate IDs

Exact command:

```bash
python3 -m astrid timelines shots reorder \
  a95fdc6d-5ca2-5830-b1cb-333859e25dc5 --project polish-lab \
  --items 8e032930-855c-5588-9306-131bb647fb7b,8e032930-855c-5588-9306-131bb647fb7b,00000000-0000-0000-0000-000000000001 \
  --json
```

Exact error:

```json
{
  "code": "validation_error",
  "message": "shot reorder rejected; supply the complete current item permutation",
  "details": {
    "entity": "shot_items",
    "item_ids": [
      "8e032930-855c-5588-9306-131bb647fb7b",
      "8e032930-855c-5588-9306-131bb647fb7b",
      "00000000-0000-0000-0000-000000000001"
    ],
    "reason": "duplicate",
    "recovery": "run `astrid timelines shots show <shot> --project <project>` and retry with its complete current item ids exactly once",
    "shot_id": "a95fdc6d-5ca2-5830-b1cb-333859e25dc5"
  }
}
```

Exit code was 1. Immediate `shots show` still returned event head 4 and the
original red/green/blue order.

### Omitted current ID

A distinct request supplied red, green, and a foreign UUID while omitting the
blue item. It returned:

```json
{
  "code": "validation_error",
  "message": "shot reorder rejected; supply the complete current item permutation",
  "details": {
    "entity": "shot_items",
    "item_ids": ["862fdc7f-3527-55ad-99fc-a42f3078f1ce"],
    "reason": "omission",
    "recovery": "run `astrid timelines shots show <shot> --project <project>` and retry with its complete current item ids exactly once",
    "shot_id": "a95fdc6d-5ca2-5830-b1cb-333859e25dc5"
  }
}
```

Again exit code was 1, event head remained 4, and all IDs, positions, media,
and metadata were unchanged. The diagnostic identifies the missing live item,
not merely a generic permutation mismatch.

Following the recovery, the complete blue/red/green permutation succeeded and
advanced the event head exactly once to 5.

Agent UX assessment: the typed `reason`, concrete IDs, shot ID, and exact
`show` command make both diagnosis and correction deterministic. When a
request contains both an omission and a foreign replacement, Astrid reports
the omission first rather than enumerating every mismatch; this is adequate
because the recommended `show` supplies the full authoritative set, though a
future multi-issue detail could save one comparison.

## 4. Shot removal response

After the successful reorder, the green item was removed:

```bash
python3 -m astrid timelines shots remove \
  a95fdc6d-5ca2-5830-b1cb-333859e25dc5 \
  d5eeec1b-5918-54b9-bcf0-fd72a39ad09b \
  --project polish-lab --json
```

The response contained:

```json
{
  "event_head_seq": 6,
  "item": {
    "id": "d5eeec1b-5918-54b9-bcf0-fd72a39ad09b",
    "media_id": "e486257c-a54b-5e27-b789-988103d03c6a",
    "metadata": {"color": "green"},
    "position": 2
  },
  "item_ids": [
    "862fdc7f-3527-55ad-99fc-a42f3078f1ce",
    "8e032930-855c-5588-9306-131bb647fb7b"
  ],
  "project_id": "243c342d-5b5d-593e-a9f4-b51288c7e849",
  "remaining_item_count": 2,
  "removed_item": {
    "id": "d5eeec1b-5918-54b9-bcf0-fd72a39ad09b",
    "media_id": "e486257c-a54b-5e27-b789-988103d03c6a",
    "metadata": {"color": "green"},
    "position": 2
  },
  "shot_id": "a95fdc6d-5ca2-5830-b1cb-333859e25dc5"
}
```

The full legacy `item`, `item_ids`, project/shot IDs, and event head remain.
The new `removed_item` makes the subject explicit, and
`remaining_item_count:2` prevents the caller from having to infer length.
`shots show` confirmed only blue/red remained and positions were compacted to
0/1. `media show e486...` confirmed the removed item's media identity, CAS
locator, digest, and bytes remained intact.

Agent UX assessment: pass. The duplicated `item` and `removed_item` objects
are intentionally redundant for compatibility; `removed_item` is materially
clearer to a new caller.

## 5. Archived reference association recovery

The public create command made character reference
`ee39ed0e-f680-5486-8ba2-beaa358490e5` (`Archived Hero`) with red as its
primary canonical media. `references archive` returned
`preserved.media_references:1`. Baseline `references show` then contained:

```text
archived_at = 2026-08-24T11:21:01.932560Z
event_head_seq = 2
media count = 1
primary media = d50ef1c4-8a9c-5719-87af-8576de8cd93a
```

The rejected command was:

```bash
python3 -m astrid media references associate \
  ee39ed0e-f680-5486-8ba2-beaa358490e5 \
  --project polish-lab \
  --media e486257c-a54b-5e27-b789-988103d03c6a \
  --role depicts --metadata '{"attempt":"archived"}' --json
```

Exact error:

```json
{
  "code": "terminal_state",
  "message": "reference is archived; unarchive it before adding an association",
  "details": {
    "entity": "reference",
    "recovery": "run `astrid media references unarchive <ref> --project <project>` then retry the association",
    "reference_id": "ee39ed0e-f680-5486-8ba2-beaa358490e5"
  }
}
```

Exit code was 1 and receipt was null. Immediate `references show` was
identical: same archive timestamp, event head 2, one primary association, and
unchanged metadata. No green association was created.

The prescribed recovery, with the returned ID substituted:

```bash
python3 -m astrid media references unarchive \
  ee39ed0e-f680-5486-8ba2-beaa358490e5 --project polish-lab --json
```

returned `changed:true`, `status:"active"`, and preserved the original media
association. Retrying `associate` then succeeded, adding green as `depicts`
and advancing the reference head to 4. Final `show` contained both the
original canonical association and the new secondary association.

Agent UX assessment: pass. The error category distinguishes lifecycle state
from bad input, names the exact reference ID, explains the operation ordering,
and provides the correct recovery command. The command uses placeholders
rather than interpolating the returned ID/project, which requires trivial
substitution but avoids an unsafe copy/paste command targeting the wrong
scope.

## Final verdict

All requested polish behaves correctly in live public usage. Error responses
are not merely clearer prose: they carry machine-readable categories,
structured offending identity, a deterministic recovery path, and zero
mutation. Successful follow-up commands prove the guidance is operational.

No product, source, tests, SQLite rows, or managed JSON were edited directly
during this replay. Only this evidence report was added to the repository.
