# Replay: final read-back 2

Date: 2026-08-23 (Europe/Berlin)  
Scope: fresh black-box CLI + public SDK replay; no source, tests, git, or
prior-QA inspection. No pack `run.py` invocation.  
Disposable root: `/tmp/astrid-replay-final-readback-n98Mh5` (cleaned after
capture).

## Verdict

**PASS for the requested final read-back acceptance, with one residual
read-model discrepancy noted below.** Reference name/ID resolution is typed,
project-local, and mutation-free on failures. A real project-scoped
`rendering.render` invocation succeeded, and `runs show --evidence` directly
returned bounded child output records for both the primary MP4 and its
provenance sidecar. A deliberate invalid render remained available as a
typed failed run.

## Fresh setup and reference addressing

The public census/help and rendering `STAGE.md` were read first. A new
`ASTRID_PROJECTS_ROOT` was created, then projects `alpha` and `beta` were
created through the CLI. Four tiny local files were imported through
`media import`: three into `alpha`, one into `beta`.

References created through `media references create`:

| Project | Name | Reference ID | Primary media ID |
| --- | --- | --- | --- |
| alpha | Shared Hero | `ac89bc22-e700-547b-8662-d11b7b0bc5ac` | `0274c1db-f52f-5eec-8b02-b37cc5101c5d` |
| alpha | Shared Hero | `512899f8-ee90-5c60-a8e0-cda43091524b` | `dc05e7a9-6172-5836-ba75-e81c599fe50f` |
| alpha | Unique Hero | `5e711493-d95a-5e40-85c7-84182e5dc971` | `34fd5b5a-d9e4-590e-b5b5-d5b000b250fc` |
| beta | Foreign Hero | `7daed860-89dc-5725-8c8c-2dcfb3445e37` | `9771d3cf-f919-5b73-a36c-a95f50826b18` |

Observed public behavior:

- `media references show --project alpha 'Unique Hero'` succeeded (`exit=0`)
  and returned the unique reference ID.
- `media references show --project alpha <unique-id>` succeeded and took the
  exact ID path, returning the canonical media association.
- `media references show --project alpha 'Shared Hero'` failed with exit 1,
  `validation_error`, `reason=ambiguous_display_name`, exactly two bounded
  `candidate_ids`, and recovery to `media references list --include-archived`
  followed by retry with one exact ID.
- `No Such Hero` failed with typed `not_found`, project context, and a list/id
  recovery message. The foreign reference ID and `Foreign Hero` name both
  failed with the same project-local, actionable `not_found` shape.
- The post-error reference list was unchanged: the failed lookups emitted no
  receipt/event and did not mutate references.

Residual observation: the unique-name show response had `media: []`, while the
same reference shown by exact ID included its canonical media association.
Name resolution itself is successful and safe, but the two read models are
not yet identical.

## Real successful render and direct evidence

A minimal one-second text timeline was placed inside `alpha` and rendered via
the public SDK entrypoint:

```python
sdk.invoke(
    "rendering.render", kind="executor", include_installed=False,
    project="alpha",
    inputs={
        "timeline": "/tmp/astrid-replay-final-readback-n98Mh5/projects/alpha/render-timeline.json",
        "output_name": "replay.mp4",
    },
)
```

The successful run was `1f6a7d91bcc2bb9f59de8c703e`, with child task
`2a19606ce6d974a7781b896ad4`. `runs show --project alpha --json --evidence`
returned one succeeded child directly, with these bounded authoritative
outputs (no child-task hop required):

| Ordinal | Media ID | Label | Role | Bytes | SHA-256 | Safe durable path |
| ---: | --- | --- | --- | ---: | --- | --- |
| 0 | `01m0r481dc5my9g94n2cgkxc52` | `replay.mp4` | `result` / primary | 51,299 | `db9109e5acfc63cffcd4955588e734195bb40bc8e248f3f5c955a9a0d35f0ae7` | `out/replay.mp4` |
| 1 | `01m0r481ddeswa861kvsp7e46d` | `replay.mp4.provenance.json` | `output` | 19,025 | `802ec611cf4b39ddfaa4f88753ee8522f1c1108482036375f185f5e16ad4ce27` | `out/replay.mp4.provenance.json` |

The same IDs and hashes appeared in the terminal `core.task.completed` event.
`media show` independently matched each byte size, hash, media kind, MIME
type, and managed content-addressed locator. The run was `succeeded` with
one child and no failed/cancelled children. The response's generic
`evidence` array remains empty, but the direct `child_outputs` records contain
the required bounded output evidence.

## Deliberate safe failure

An in-project timeline containing the unregistered clip type
`not-a-real-clip` was invoked through the same SDK surface. It produced failed
run `962ba690b1fcd79df553a6019d`, child
`0d25f317d68ce3e4cde1b022bb`, with typed runtime failure:

```text
rendering.remotion does not support this render request:
timeline uses unregistered Remotion clip types: not-a-real-clip
```

`runs show --evidence` retained the failed child and its error, while
`tasks events` retained the complete queued → claimed → started → failed
lifecycle. No output artifacts were published for the failed invocation.

## Cleanup

The disposable root and its temporary media/timeline fixtures were removed
after all public read-back checks. Only this report was left in the workspace;
no source or test files were changed.
