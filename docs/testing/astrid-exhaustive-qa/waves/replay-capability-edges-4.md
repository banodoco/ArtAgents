# Replay: capability edges 4

Date: 2026-08-23  
Mode: fresh black-box LIVE SDK replay  
Scope: public `astrid.sdk` / `AstridClient` only; no source, tests, git, prior QA, credentials, or network.

## Fixture and isolation

Created a fresh `mktemp -d` projects root and one SDK-created project (`edge-demo`).
Generated a tiny local mono WAV, a brief, and a placeholder video inside the temporary
root. `OPENAI_API_KEY` was explicitly unset. The temporary root was removed in a
`finally` cleanup (`shutil.rmtree`); no fixture was retained.

## Capability lookup edges

- `sdk.get_capability("generation.generate_imag", kind="executor", include_installed=False)`
  raised `CapabilityNotFoundError` with bounded nearest matches: `generation.generate_image`,
  `generation.generate_image_openai`, and `generation.generate_audio` (with aliases where
  applicable). This is useful typo recovery and contains no unbounded catalog dump.
- `sdk.get_capability("video_editing.hype", kind="executor", include_installed=False)`
  raised `CapabilityNotFoundError` stating it is registered as an orchestrator, explicitly
  saying to retry with `kind='orchestrator'`, and naming `orchestrator:video_editing.hype`.
- `sdk.get_capability("far.unknown.capability.edge.zzzz", kind="executor", include_installed=False)`
  raised `CapabilityNotFoundError` with `no close catalog match` and recovery to call
  `discover(include_installed=False)` and filter by id/name/aliases, plus supported kinds
  `executor, orchestrator, element`. It emitted zero irrelevant capability suggestions.

## Hype inputs

`sdk.invoke("video_editing.hype", kind="orchestrator", project="edge-demo", dry_run=True,
inputs={"video": <video-path>, "brief": <brief-path>})` returned `InvocationResult.ok == True`.
The planned command retained both literal declared values as `--video <video-path>` and
`--brief <brief-path>`.

Adding `rogue: "do-not-accept"` to the same input mapping raised
`CapabilityValidationError`: the orchestrator does not declare `rogue`, declared inputs
are `brief, video`, and recovery says to pass runtime flags through
`orchestrator_args=("--flag", "value")`.

## Credential-free audio invocations

The tiny local WAV was passed directly to each executor; no `runs.show` call was made.
Both returned `InvocationResult.ok == False`, retained top-level `run_id`,
`kernel_run_id`, `kernel_task_id`, and `kernel_attempt_id`, and had empty `outputs`:

| capability | run id | task id | top-level error behavior |
| --- | --- | --- | --- |
| `understanding.audio_understand` | `6afbd6dc39ad571dfd608c2952` | `c680f2225174658f2c40b7760b` | Bounded `handler_failed` / `CapabilityRuntimeError`; explains `OPENAI_API_KEY not found` and recovers by setting `OPENAI_API_KEY` or passing an explicit env file. |
| `editorial.transcribe` | `406cfbd2f70119e41daaad29e6` | `cad3051f0f5d5c89a18e8b7193b` | Bounded `handler_failed` / `CapabilityRuntimeError`; log tail identifies only `OPENAI_API_KEY not found`, and recovery points to checking the transcribe log and retrying. |

The returned errors contained no API-key value, audio output, transcript, or other
secret. `understanding.audio_understand` also preserved attempt id
`01m0r2t8pgn10sa3t6pqy8fgt2`; `editorial.transcribe` preserved attempt id
`01m0r2ta5ah2cxdspevtge5av7`.

## Verdict

PASS. All requested discovery, wrong-kind recovery, far-unknown guidance, Hype
declared/rogue input, and credential-free invocation edge behaviors were observed.
