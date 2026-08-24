# Replay: canonical render preflight and runtime failure 4

Date: 2026-08-24
Mode: independent black-box live agent usage. I used the public Astrid CLI
and CLI help only for the product journey. `ffmpeg` was not needed. I did not
inspect or edit source/tests/product code.

Fresh disposable root:

`ASTRID_PROJECTS_ROOT=/tmp/astrid-render-replay-3KwVd0`

## Verdict

**PASS.** Canonical rendering now provides a useful pre-admission boundary for
incomplete output configuration, preserves drafts, and returns a typed,
actionable error without creating a run, task, attempt, or render snapshot.
A complete CAS correction rendered successfully. A deliberately unsupported
clip type then demonstrated a genuine deterministic post-admission runtime
failure whose exact run/task/attempt and top-level message were stable across
replay.

## Journey 1 — permissive draft and pre-admission rejection

Created project `render-preflight` and default timeline `draft` (timeline id
`2f9ae287-ef64-55e8-b6d3-466b2aad36f2`, ULID
`14xypyyvy7y592pxkq1gzk4a75`) with version 1 config:

```json
{
  "clips": [{
    "id": "missing-clip", "at": 0, "track": "source",
    "clipType": "video", "asset": "missing-asset", "from": 0, "to": 1
  }],
  "output": {"file": "draft.mp4"}
}
```

The public `timelines show draft --json` confirmed the incomplete document was
durably retained as a draft. `timelines render draft --json` returned one
five-key envelope:

```json
{
  "ok": false,
  "error": {
    "code": "validation_error",
    "message": "canonical timeline 'draft' is not renderable: config.output is incomplete; missing required field(s): resolution, fps. Either omit config.output or provide resolution, fps, and file, then retry",
    "details": {
      "sdk_category": "validation",
      "sdk_error": "CapabilityValidationError",
      "run_id": null,
      "kernel_run_id": null,
      "kernel_task_id": null,
      "kernel_attempt_id": null
    }
  },
  "data": null,
  "receipt": null
}
```

Immediately after this failed command, public `runs list --project
render-preflight --json` returned `[]`. The project event head remained at 3
(project creation, timeline creation, and no render admission), and the
project tree contained only its plan/project files; no
`.astrid/render-snapshots` materialization existed for the rejected request.
This is the desired no-side-effect preflight behavior.

## Journey 2 — CAS correction and successful render

I first CAS-saved a complete `output` object at version 2, which exposed the
next required canonical fields (`clips` and `tracks`) without admitting a
run. I then CAS-saved the actually valid correction at expected version 2:

```json
{
  "clips": [],
  "tracks": [],
  "output": {"resolution": "320x180", "fps": 30, "file": "corrected.mp4"}
}
```

This advanced the timeline to version 3. The public render then succeeded:

- kernel run: `a1fc2887081915b930ecb0d679`
- task: `dd48325a39e18d3ee3f9d74e4b`
- attempt: `01m0skzzjm599zw17g6gebdjga`
- primary artifact: `hype.mp4`, hash
  `c096f16bc6a571ba980a9613fef5e667ebbac5cec8035ec67f6da693a54d68e5`
- provenance artifact: `hype.mp4.provenance.json`, hash
  `53741f40cdcfb8fca4fefab94305c9d83bb0f9f71ba6f04627d6b94440a141ae`

Both artifact paths were durable managed `.astrid/media/sha256/...` CAS
locations. The render snapshot and run were created only after the valid CAS
save and admission.

## Journey 3 — deterministic post-admission failure and replay

An initial attempt to use an unknown effect object (`effects:
{"effect-that-does-not-exist": 1}`) did not fail: the renderer accepted it and
produced artifacts. That is a useful friction observation, but not a valid
runtime-failure fixture.

I then CAS-saved a schema-valid timeline at version 6 with a deliberately
unregistered `clipType: "bogus"`, complete output and track fields. It passed
canonical preflight and was admitted. Both identical public render commands
returned the same runtime error envelope:

```json
{
  "ok": false,
  "error": {
    "code": "invocation_error",
    "message": "rendering.remotion does not support this render request: timeline uses unregistered Remotion clip types: bogus",
    "details": {
      "sdk_category": "runtime",
      "sdk_error": "CapabilityRuntimeError",
      "run_id": "648963b1eeab860eaa41583298",
      "kernel_run_id": "648963b1eeab860eaa41583298",
      "kernel_task_id": "dee8b5f9b80b417101a4b5be78",
      "kernel_attempt_id": "01m0sm1zmvqge49cwmafytrk6f"
    }
  },
  "data": null,
  "receipt": null
}
```

The second replay preserved the exact same run, task, attempt, error code, and
message. `runs list` showed the admitted failed run, proving the contrast with
the earlier pre-admission rejection.

## Friction and UX score

- **Preflight: 10/10.** Missing output fields are listed in one message with a
  direct recovery instruction; IDs are null and no run is created.
- **Draft recovery: 9/10.** CAS save is clear and stale-safe. The first
  output-only correction revealed a second required layer (`clips`/`tracks`),
  so the public journey may still require one retry for a hand-authored draft.
- **Runtime failure/replay: 10/10.** A post-admission unsupported type is
  typed, actionable, and replay-stable with durable run evidence.
- **Effect discoverability: 7/10.** An unknown effect object was silently
  tolerated and rendered rather than rejected or surfaced; this is outside the
  canonical preflight correction but is a remaining agent-UX ambiguity.

Overall: **9/10 — PASS.**
