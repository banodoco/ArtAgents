# Canonical render preflight and error propagation fix

Date: 2026-08-24

## Outcome

Fixed the P1 found in the independent canonical-render replay.

A canonical timeline remains a permissive authoring draft, but
`rendering.render` managed-ref mode now validates the pinned timeline and
registry before materializing execution inputs or admitting a kernel run.
An incomplete `config.output` produces an actionable typed validation error
with null run/task/attempt ids. No doomed run or render snapshot is created.

Post-admission renderer failures also retain their actionable handler error on
an exact failed-run replay. Previously the first execution could record a
useful error, while the terminal replay reconstructed only `ok: false` and
identifiers, causing `timelines render` to fall back to the generic
`timeline render failed` message.

## Original live failure

In the preceding fresh replay, three canonical timelines were created with a
partial output object:

```json
{"output": {"file": "image.mp4"}}
```

Create succeeded. Render then admitted a run and returned only:

```text
timeline render failed
```

`runs show <run> --evidence` was required to discover the actual deterministic
schema error:

```text
'resolution' is a required property
required: ['resolution', 'fps', 'file']
```

This produced durable failed runs for a request that could be rejected from
the pinned document alone.

## Root causes

### Missing managed-ref render preflight

The canonical-ref path resolved the timeline and version before admission, but
immediately materialized the snapshot and handed it to the executor. Timeline
render-schema validation lived inside the Remotion support check reached by
the admitted task.

Timeline create/save deliberately store loose JSON documents so drafts and
non-rendering authoring states remain possible. Tightening those mutations
would conflate authoring validity with render readiness. The missing boundary
was the transition from canonical document to render invocation.

### Failed exact replay dropped persisted error data

The kernel invocation path returned `exec_res.error` for a newly failed
attempt. On an identical request whose run was already terminal, it restored
the run/task ids but did not reload the failed attempt's `error_json`.
`InvocationResult.error` therefore became null, and the product CLI had no
message to propagate.

## Implementation

### Managed render readiness

Added `validate_managed_render_snapshot` in:

- `astrid/packs/rendering/executors/render/managed_timeline.py`

After resolving the active timeline and CAS version, but before snapshot
materialization, it now validates deterministic render requirements:

1. `config.output` remains optional, but when present it must contain all of
   `resolution`, `fps`, and `file`; the error names every missing field and
   explains that the author may either omit the object or complete it.
2. The entire timeline is validated with Astrid's canonical shared timeline
   validator, covering renderer-required shape and semantic constraints.
3. The materialized registry is validated with the canonical registry
   validator.
4. Every clip asset reference must exist in the pinned registry.

`astrid/sdk/invocation.py` runs this validation inside the existing managed
render preparation branch. Any failure becomes `CapabilityValidationError`,
which `invoke_result` maps to the stable validation result without admission.

This preserves the intended split:

- create/save: permissive authoring documents;
- render: strict deterministic readiness before admission;
- backend execution: runtime/toolchain checks that cannot be decided solely
  from the canonical document.

### Failed replay error preservation

For a terminal failed or cancelled run, the invocation path now loads the
latest terminal execution attempt and restores its persisted `error_json` plus
real attempt id. The normal `InvocationResult.error` mapping then exposes its
message and runtime category to the product CLI on both first failure and
exact replay.

## Fresh live proof

Disposable root:

`ASTRID_PROJECTS_ROOT=/tmp/astrid-render-preflight-fix.oc9wJ7/projects`

Created project `preflight` and canonical timeline `incomplete` version 1:

```json
{
  "tracks": [],
  "clips": [],
  "output": {"file": "draft.mp4"}
}
```

This create succeeded, proving drafts remain permissive. Immediately before
render, public `runs list --project preflight --json` returned zero runs.

Command:

```bash
python3 -m astrid timelines render incomplete \
  --project preflight --expected-version 1 --json
```

Exited 1 and returned exactly:

```json
{
  "data": null,
  "error": {
    "code": "validation_error",
    "message": "canonical timeline 'incomplete' is not renderable: config.output is incomplete; missing required field(s): resolution, fps. Either omit config.output or provide resolution, fps, and file, then retry",
    "details": {
      "sdk_error": "CapabilityValidationError",
      "sdk_category": "validation",
      "run_id": null,
      "kernel_run_id": null,
      "kernel_task_id": null,
      "kernel_attempt_id": null
    }
  },
  "ok": false,
  "receipt": null,
  "idempotency_key": ""
}
```

After the rejection:

- public run count remained `0`;
- the project had no `.astrid/render-snapshots` directory.

Thus validation occurs before both ledger admission and snapshot filesystem
materialization.

### Valid recovery still renders

Saved the same timeline with a one-second structured text clip, explicit
320x180@30 theme canvas, and complete output object. The document advanced to
version 2. Rendering version 2 succeeded:

- kernel run: `7277179a9aaa5828b3009d89ac`
- returned artifacts: 2

The stricter transition does not block a valid canonical render.

### Post-admission failure detail survives replay

Created a schema-valid timeline using intentionally unknown effect clip type
`not-a-real-effect`. This passes generic document preflight and correctly
reaches backend-specific support selection.

The first render failed after admission with:

```text
rendering.remotion does not support this render request: timeline uses
unregistered Remotion clip types: not-a-real-effect
```

Identifiers:

- run: `75b5675d3d9db6eed059a94c32`
- task: `b909389aa59825b0b3b90a5c7d`
- attempt: `01m0sksjy7jzn3917w7qs3xkbp`

Repeating the identical command returned the same ids and the same actionable
message. It did not regress to `timeline render failed`. Both envelopes
classified the failure as `CapabilityRuntimeError` / `runtime`.

## Automated guards

`tests/packs/rendering/test_managed_timeline_render.py` now proves:

- incomplete output rejection before snapshot materialization;
- missing registry asset rejection during managed render preflight;
- a newly failed handler and its exact replay return the same actionable
  error and stable kernel ids.

Focused checks:

```text
pytest -q \
  tests/packs/rendering/test_managed_timeline_render.py \
  tests/v10/test_domain_cli_projects_timelines.py

79 passed in 2.69s
```

The changed Python modules compile successfully and focused `git diff --check`
is clean.

## Verdict

PASS. A deterministic canonical timeline schema error now fails before
admission with direct recovery guidance and null kernel ids. Draft authoring
remains permissive, valid renders remain functional, and genuine runtime
failure detail is stable across exact replay.
