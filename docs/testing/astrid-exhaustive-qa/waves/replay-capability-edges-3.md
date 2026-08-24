# Replay: capability edges 3

Date: 2026-08-23  
Surface: public `astrid.sdk` / CLI and public VibeComfy CLI only  
Isolation: disposable `/tmp/astrid-cap-edge-3.YQdlil` project root; no API key was
provided and no source/tests/git/prior-QA inspection was used.

## Wave 1 — `video_editing.hype` STAGE input boundary

Used the literal SDK shape `inputs={video,brief}` with
`kind="orchestrator"`, `project="replay-edge-3"`, and `dry_run=True`.

Observed `InvocationResult.ok=true`, `dry_run=true`, and the normalized command
contained both declared inputs:

```text
... hype.run --video /tmp/astrid-cap-edge-3.YQdlil/video.mp4
    --brief /tmp/astrid-cap-edge-3.YQdlil/brief.txt --out ...
```

Adding undeclared `rogue` to `inputs` was rejected before execution with typed
`astrid.sdk.exceptions.CapabilityValidationError`:

```text
orchestrator 'video_editing.hype' does not declare SDK input(s): rogue;
declared inputs: brief, video. recovery: pass the runtime flags through
orchestrator_args=("--flag", "value") and retry
```

Verdict: **PASS** — both STAGE ports are normalized, and extra input is a typed
pre-admission rejection with `orchestrator_args` guidance.

## Wave 2 — live-safe no-key audio failures

Generated a tiny local WAV (800 silent mono frames) and invoked both executors
with `OPENAI_API_KEY` unset and no `env_file`.

* `understanding.audio_understand`: invocation returned `ok=false`, no outputs;
  SDK run details reported `OPENAI_API_KEY not found` and recovery to set the key
  in the environment or pass an explicit env file.
* `editorial.transcribe`: invocation returned `ok=false`, no outputs; run details
  reported the same bounded missing-key cause and recovery, with only a log path
  and no secret value.

The public `runs.show(..., include_evidence=True)` SDK result carried the failure
messages. The top-level `InvocationResult` itself carried `ok=false` but
`error=null` and only run/task IDs; callers must inspect run details for the
cause/recovery text. No API key value, transcript, analysis, or output artifact
was emitted.

Verdict: **PASS with API-shape caveat** — safe bounded cause/recovery is present
in public run-detail errors; direct invocation does not duplicate it in its
top-level `error` field.

## Wave 3 — discovery safety and output metadata

`sdk.discover(include_installed=False)` exposed the following public metadata:

| Capability | Network | Environment / secret declaration | Real outputs |
| --- | --- | --- | --- |
| `understanding.audio_understand` | `true` | permissions include `environment`; `secrets_required=["OPENAI_API_KEY"]` | `analysis` (`understanding/audio`) and `manifest` (`metadata/result-manifest`) |
| `editorial.transcribe` | `true` | permissions include `environment`; `secrets_required=["OPENAI_API_KEY"]`; optional `env_file` input | `transcript`, `subtitle`, `transcript_text`, `chunk_plan`, `manifest` |
| `video_editing.hype` | `false` | no secrets; no environment permission | orchestrator has no declared outputs |

Verdict: **PASS** — network, environment/key requirement, and concrete executor
output descriptors are discoverable (with the expected empty output list for the
hype orchestrator).

## Wave 4 — unknown ID and wrong kind

Far unknown exact ID `far.unknown.capability.edge.zzzz` with
`kind="executor"` raised typed `CapabilityNotFoundError`, but the message gave
an irrelevant nearest match:

```text
unknown executor 'far.unknown.capability.edge.zzzz'; nearest matches:
executor:reigh.reigh_data (alias: builtin.reigh_data)
```

Wrong kind (`video_editing.hype`, `kind="executor"`) was correctly bounded and
actionable:

```text
unknown executor 'video_editing.hype'; registered as orchestrator; retry with
kind='orchestrator'; nearest matches: orchestrator:video_editing.hype ...
```

Verdict: **FAIL** — wrong-kind guidance passes, but a far unknown exact ID still
invented/offered an irrelevant nearest match instead of bounded catalog guidance.

## Wave 5 — local VibeComfy dry-run preflight

Ran public preflight commands against ready template `smoke/empty_image_red`:

```text
vibecomfy inspect smoke/empty_image_red --json
vibecomfy validate smoke/empty_image_red --json
vibecomfy doctor smoke/empty_image_red --json
```

All exited `0`. Inspect/doctor reported `readiness_level=ready`, `status=runnable`
or `status=ok`, two runtime nodes (`EmptyImage`, `SaveImage`), one image output,
zero model assets, and zero error/warning/info diagnostics. Doctor’s actionable
message was: `No local issues found. Runtime/model/node failures require
vibecomfy run logs.` The expected no-ComfyUI startup notice was emitted; no run
was queued.

Verdict: **PASS** — local dry-run/preflight remains intentional and actionable.

## Overall verdict

**CONDITIONAL / FAIL on the strict edge suite.** Waves 1, 3, and 5 pass. Wave 2
is operationally safe and exposes the required key recovery in run details, with
the noted top-level SDK error-field caveat. Wave 4 fails the no-irrelevant-match
requirement for far unknown IDs. The disposable project root and its temporary
audio/video/brief fixtures were removed after capture; no code changes were made.
