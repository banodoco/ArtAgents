# Replay: timeline visualization and generation preflight (wave 2)

## Scope and method

This was a fresh black-box LIVE UX replay on 2026-08-23 in a disposable
projects root, `/private/tmp/astrid-replay-viz-lHNFEC/projects`. I used the
root/family CLI help, the public `rendering.timeline_visualize` and
`generation.generate_image` SDK discovery/schema, and the two selected public
`STAGE.md` documents. I did not inspect source, tests, git history, or prior QA
reports, and made no product-code changes.

The CLI created project `demo` (project id
`1a848fb4-683d-56c9-be0c-dbce380a427a`) and managed timeline `primary`
(timeline UUID `bbe980b3-1b9f-58f1-bb38-fb82501016fd`, ULID
`n8qy2ktsh0t4csh985azvzxg7c`). A two-second, one-clip event-log fixture was
kept under the disposable project's managed `timelines/` tree so the live
visualizer had a real managed source to read. Timeline CRUD itself recorded
the row and history, but did not materialize the event-log directory.

## Successful evidence

- UUID selector succeeded in run `1cfb781a410db7376c59d4162b`, task
  `ed185615e54c7dac530ebbd76b`, with `formats=["png", "svg"]`. It emitted
  `PG001.png`, `PG001.svg`, `PG002.png`, `PG002.svg`, the manifest, and the
  machine bundle under the managed run.
- A project-owned timeline file succeeded in run
  `521a36a055d9bdfe678c519204`, task `f746f186205f25671cfbe849b4`, with
  `timeline_source` set to the contained `assembly.jsonl` file and
  `formats=["md"]`. It emitted `reading-guide.md` and `structure.md` plus the
  machine bundle.
- A comma-separated format string (`"png,svg"`) succeeded in run
  `dd010f8906fd44ac520aedf545`, task `608dccde7fb3ab0efaae620505`, and
  emitted both PNG and SVG page artifacts. SDK list-valued formats also
  succeeded. The documented direct runner spelling (`--format` repeated or
  comma-separated) is guarded as an internal entrypoint; the public root CLI
  has no `timelines visualize` command.

The evidence is real managed media, not only manifest claims:

- PNG media `01m0r4kdadrydqwztdgbh5y0ra` is a 47,568-byte 1920x1080 PNG at
  `/private/tmp/astrid-replay-viz-lHNFEC/projects/.astrid/media/sha256/c1/32/c132a31364ec2eda6cb54083fe8939388a7af67fcf6bf3a4f3e99249ecc939f9`.
- SVG media `01m0r4qr59yyby4vs3x41gnrxh` is a 2,390-byte SVG at
  `/private/tmp/astrid-replay-viz-lHNFEC/projects/.astrid/media/sha256/c8/4e/c84e8e761163de82085559023dc896be73f0396dd7629f79753d1d44578c5306`.
- Markdown `structure.md` is 1,024 bytes at
  `/private/tmp/astrid-replay-viz-lHNFEC/projects/.astrid/media/sha256/d0/55/d055d832ac73da2d981d77f377ba1a933b63efb5be7a644a27a652305a2d78ff`.
- `runs show --evidence` reported each successful run as
  `succeeded: 1/1`, with the corresponding child task and output labels.

## Pre-admission probes

`astrid.sdk.invoke_result(...)` behaved correctly for these cases:

| Case | Result | Side effects |
| --- | --- | --- |
| `timeline_source` + `timeline_slug` | `ok=false`, `CapabilityValidationError`: choose a managed path, timeline ref, or `all` | no run id, no task id, no outputs |
| invalid visualization format `gif` | `ok=false`, `CapabilityValidationError`: choose `png`, `svg`, `md`, or `all` | no run id, no task id, no outputs |
| generation model `not-a-real-model` | `ok=false`, structured validation error listing available models | generation project runs 0 → 0 |
| generation mode `not-a-mode` for `z-image` | `ok=false`, structured validation error listing `i2i`, `t2i` | generation project runs 0 → 0 |

The ordinary `sdk.invoke(...)` path remains typed: the invalid generation-model
probe raised `CapabilityValidationError` (with its underlying `KeyError` as
`__cause__`), matching the documented SDK exception path. No traceback was
printed by the caught call.

## Finding: foreign source is not pre-admission

This requirement did not hold. With project `other` and a source file owned by
`demo`, `invoke_result` returned a runtime `handler_failed` mapping rather than
a typed validation result. It admitted failed run
`0e426eb5fff778a47612ff8054` / task `53a762ae3ae3dc3ae911b792ca`; the project
run count changed 0 → 1 and no evidence artifacts were produced. Repeating the
same probe with list-valued `timeline_source` admitted two more failed runs:
`c2960293434417657575264a8f` and `3c72ee5bfa62d537fb77ef2793`, each with no
outputs.

The error text was truthful (`timeline_source must be ... under .../other/timelines`),
but ownership/path containment is a precondition and should be checked before
kernel admission. This is a P1/P2 agent-UX defect because callers relying on
`invoke_result` cannot guarantee that invalid foreign inputs are side-effect
free.

## Selector note and verdict

The UUID selector was successful. Slug and ULID probes against the same
disposable fixture terminated with `identity ULID does not match directory
name` and produced failed runs; therefore selector coverage is not a clean
pass in this replay. The successful UUID/file paths prove the evidence pack,
managed media, run ledger, task ledger, and format normalization work when the
source resolves.

Overall verdict: **FAIL / needs follow-up**. Generation preflight and
contradictory/invalid-format visualization validation pass with no admission;
foreign timeline-source ownership does not.

The disposable projects root and all generated media/run data are test-only and
should be removed after handoff.
