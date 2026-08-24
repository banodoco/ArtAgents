# Doctor + shots error polish finding

Date: 2026-08-24 (Europe/Berlin)  
Surface: public `python3 -m astrid` CLI first, followed by compatible SDK
mapping changes and live CLI replay.

## Verdict

PASS after a bounded polish patch. No P0/P1 issues. The changes are additive:
existing doctor states/codes and shot response keys remain valid, while fresh
roots now expose a clear next action and typed mutation results include the
missing recovery/membership context.

## Live reproduction before the patch

Fresh root: `/tmp/astrid-doctor-shot-polish-z6R6oR`.

### Pristine doctor

Both `doctor` and `doctor --json` correctly returned `ok: true`, exit 0, and
`state: "uninitialized"`. However, the only next-step hint was repeated in
individual check detail strings. There was no concise top-level JSON or human
guidance field.

### Shot removal

The live remove envelope returned the removed object under the generic
`data.item`, alongside `data.item_ids` for the remaining shot membership. The
removed item's old position was therefore easy to misread as current
membership. Media preservation itself was correct.

### Archived association

After archiving a reference, `media references associate` returned:

```json
{"code":"terminal_state","details":{},"message":"the record is in a terminal state"}
```

The terminal classification was correct, but recovery was guesswork.

### Invalid reorder

Submitting a duplicate permutation returned:

```json
{"code":"validation_error","details":{},"message":"the request failed validation"}
```

The operation was safely rejected before mutation, but did not identify the
shot, duplicate reason, offending IDs, or the required whole-shot recovery.

## Patch

### Doctor guidance

Pristine doctor JSON now includes:

```json
{"next_action":"Initialize a project with `python3 -m astrid projects create <slug> --name <Name>`"}
```

Human output prints the same line as `next action:`. `ok: true`, exit 0, and
`state: "uninitialized"` are unchanged. Ready/unhealthy roots expose
`next_action: null`, avoiding any implication that a healthy root needs setup.

### Shot remove semantics

The legacy fields remain unchanged (`item` and `item_ids`). Removal results now
also include:

- `removed_item`: explicit copy of the removed item facts;
- `remaining_item_count`: count of current shot members after removal.

Older receipts without these additive fields still deserialize safely. Add-item
responses do not emit removal-only fields.

### Typed recovery details

Archived reference association remains `terminal_state` but now includes the
reference ID and an exact unarchive/retry recovery command.

Shot reorder validation remains `validation_error` but now includes:

- `entity: "shot_items"`;
- `shot_id`;
- `reason` (`omission`, `duplicate`, `extra`, or `foreign`);
- offending `item_ids`;
- a recovery instructing the user to show the shot and submit its complete
  current item permutation exactly once.

## Live replay after the patch

On a fresh doctor root `/tmp/astrid-doctor-guidance-OEcIhf`:

- human doctor printed `state: uninitialized` plus the new `next action:`;
- JSON returned the same guidance with `ok: true`, exit 0;
- the already initialized replay root returned `state: ready` and
  `next_action: null`.

On the seeded disposable project:

- archived association returned `terminal_state`, reference ID, and an
  `unarchive ... then retry` recovery;
- shot remove returned `removed_item` and `remaining_item_count: 1` while
  preserving the old fields;
- duplicate reorder returned `reason: duplicate`, the duplicated ID, shot ID,
  and a show/retry recovery;
- all invalid operations remained pre-admission and zero-mutation.

## Guards

Focused and surrounding suites pass:

```text
49 passed in 7.30s
```

This covers doctor pristine/corruption checks, shot add/remove/reorder and
atomicity/replay behavior, reference lifecycle/association behavior, and the
new recovery/detail assertions.

No unrelated product surface was changed. Remaining friction is limited to
the intentional requirement that a reorder caller read the current shot before
submitting a complete permutation.
