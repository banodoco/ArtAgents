# Final read-back UX fix — live proof

Date: 2026-08-23 (Europe/Berlin)

## Outcome

The two final-maker read-back gaps are closed. `media references show` now
uses the same project-local addressing rule as documented recovery: exact id
first, then an exact unambiguous name. Ambiguous names fail closed with
candidate ids and a list/retry command; missing or foreign references return a
typed `not_found` with bounded recovery guidance. The resolver remains scoped
to the requested project, so an id from another project cannot be read or
mutated through a project-local name/id collision.

`runs show --evidence` now includes bounded `child_outputs` derived from the
authoritative `task_outputs` completion projection. Each direct child carries
its task id, run ordinal, terminal status, and up to 32 ordered outputs with
media id, role, primary flag, label, content hash, byte size, and safe
staging-relative path. Existing run-level evidence and failed-child evidence
remain unchanged. Absolute or traversal paths are omitted from the read-back.

## Live reproduction before the fix

On a fresh disposable root, a reference created as `Field note` could be
shown by exact id, but:

```text
astrid media references show "Field note" --project rb --json
=> not_found: the requested record does not exist
```

This contradicted the public `media references unarchive <name>` recovery
contract and forced an agent to remember the opaque id. The reproduction was
project-local and did not mutate state.

## Live proof after the fix

Fresh root: `/private/tmp/astrid-readback-live-27nZ2e`.

- An unambiguous human name returned the complete reference read model.
- Two `Field note` references returned `validation_error` with
  `reason: ambiguous_display_name` and both candidate ids:
  `105d519d-e343-543a-9789-fa4f6ecd1ade` and
  `b9417e44-1e74-5b7b-a61c-4054614a5ed1`.
- A nonexistent name returned `not_found`, entity `reference`, the requested
  ref, project id, and inclusive-list recovery guidance.
- An alpha reference id requested under beta returned typed `not_found`; no
  cross-project read or mutation occurred.

Fresh render root: `/private/tmp/astrid-run-evidence-live-6wKjGB`, project
`render-readback`. A real text-only Remotion render completed through the
public project-scoped SDK invocation:

- run `3491af7439718545801429ebf8`
- child task `61372af33ff4dcab829d352e3b`
- status `succeeded`, one succeeded child
- MP4 media id `01m0r25qsqntb7xef9d6apxxd3`, SHA-256
  `668a6da6b814f09dd4a0a9c49c6bc6fa14a1c759c0f2538ae3592fa7cf0c6306`
- provenance media id `01m0r26a2r9bjggcr5nykadfmb`, SHA-256
  `592ddea148c679f463907047030e445b63d0b69ae434a511e07a44b8277a0e5f`

The unchanged command:

```text
astrid runs show 3491af7439718545801429ebf8 --project render-readback --evidence --json
```

returned both authoritative child outputs directly. The paths were bounded
relative paths (`out/readback-second.mp4` and its provenance sidecar), with
roles, labels, hashes, sizes, and media ids. `ffprobe` independently confirmed
the MP4 is H.264/AAC at 1920×1080.

## Narrow regression checks

```text
pytest -q tests/sdk/test_references.py tests/sdk/test_runs.py
41 passed
```

The focused coverage includes unique-name resolution, ambiguity candidates,
typed missing recovery, and authoritative child output projection.

## Residual discrepancy replay and correction

The independent replay in `waves/replay-final-readback-2.md` found that a
unique-name read returned the correct reference row but `media: []`, while an
exact-id read returned its canonical association. The resolver had found the
row correctly, but the enrichment query still used the original display name
as its foreign key.

The read path now records the resolved aggregate id immediately after either
exact-id or name resolution and uses that id for every association lookup.
This keeps archived/direct-show semantics and project ownership unchanged.

Fresh live CLI proof: `/tmp/astrid-final-readback-live-UEr4hH`. A
`Unique Hero` reference with one canonical and one `depicts` association was
shown once by exact id and once by name. The complete JSON `data` objects were
identical, including both media associations:

- reference `385dd7da-79e2-5005-b3d0-bfdfa24ef9b0`
- canonical media `8146e4f4-7d0a-5a3d-a7cf-9a76bb34ed9e`
- secondary media `4ee7c2f9-e008-517a-a3b8-b205a14fb3a2`

The narrow reference show suite passes 6 tests, including the canonical-plus-
secondary name/id equivalence regression. Ambiguous, missing, and foreign
lookups remain typed and mutation-free.
