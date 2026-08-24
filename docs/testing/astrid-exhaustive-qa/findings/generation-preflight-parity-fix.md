# Generation preflight parity fix

Date: 2026-08-23

## Outcome

Generation preflight now has one read-only request validator shared by the
typed generation facades and generic `astrid.sdk.invoke`. It runs before
project resolution, dry-run executor construction, or kernel admission.

The repaired paths now:

- reject `generation.generate_video` FLF requests missing `image_end_ref`
  with `CapabilityMissingInputError`, naming the missing field and the retry
  action, for both dry-run and live typed-facade calls;
- reject a model/mode/backend cell that is not declared in the model catalog
  before either dry-run or live generic invocation, including
  `stable-audio-3-medium` + `music` + `local` with
  `Available backends: cloud`;
- apply the shared actionable local VibeComfy/ComfyUI prerequisite preflight
  to video as well as image routes, without selecting cloud as a fallback;
- expose a symmetric `astrid.generate.audio(...)` facade with mode inference
  for the current single `music` mode and the same execution/project/dry-run
  semantics as image/video.

## Live proof in an isolated project root

Using a fresh `ASTRID_PROJECTS_ROOT=/tmp/astrid-generation-preflight-CleIGc`
with project `motion-sound-lab`:

| Request | Result | Ledger effect |
|---|---|---|
| `ltx-2.3` / `flf` / `local`, start frame only, `dry_run=True` | typed missing-input error naming `image_end_ref` | none |
| same request, `dry_run=False` | identical typed missing-input error | none |
| `stable-audio-3-medium` / `music` / `local`, generic invoke dry-run | typed matrix error listing `cloud` | none |
| same audio request, live generic invoke | identical typed matrix error | none |

The pre-existing project database was inspected read-only afterward:
`runs=0`, `tasks=0`, and `media=0`. No output staging directory was created.
The process also emitted an unrelated warning while discovering an external
Hivemind pack whose manifest description exceeds its schema limit; this did
not affect the preflight result.

## Guard coverage

`tests/core/generation/test_preflight.py` now covers:

- FLF missing-end parity across dry/live calls and no output staging;
- generic audio matrix rejection before the dry-run runner or database;
- typed audio-facade forwarding and resolved `music`/`cloud` inputs;
- existing local readiness checks and image-facade behavior.

Focused verification: `9 passed` in `tests/core/generation/test_preflight.py`.
The broader public-surface suite passes except for one old test that expected
an inferred local LTX route to reach a mocked executor despite the local
runtime being absent; the new requested behavior intentionally raises the
actionable prerequisite error before that mocked admission.

