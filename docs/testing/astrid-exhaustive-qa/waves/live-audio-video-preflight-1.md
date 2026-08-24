# Live UX wave: audio + FLF video preflight

## Verdict

**STOPPED TRUTHFULLY — no requested artifact was produced.** The isolated live
session made only local requests. Video failed because the local runtime could
not import `vibecomfy`; audio failed because the selected model has no local
backend. No cloud/paid request was made, no cloud run was admitted, and no
media files were created. Astrid did admit two kernel runs, both explicitly
`execution=local` and both terminal `failed`; these are honest failed-run
records, not misleading successful runs.

The most serious finding is a preflight-parity failure: FLF video dry-run
accepted a request with the required end-frame omitted (`ok=true`, no run),
even though the public video contract says `flf` requires `image_ref` and
`image_end_ref`. Audio local dry-run also returned `ok=true` despite the
documented audio contract saying local is reserved/follow-up and the selected
model being cloud-only. Both availability/requirement failures surfaced only
after a user proceeded to live execution.

## User journey and evidence

Goal: create `motion-sound-lab`, make a short FLF video from
`tests/packs/builtin/generate_image/fixtures/tiny.png` to
`avatars/portrait.png`, and make a two-second gentle water-splash sound effect,
using local/no-paid routes only.

Isolation: `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-audio-video-preflight-gVr4WS`
(fresh `mktemp` root). The project was created through the public gateway and
the post-create doctor check was green (`quick_check ok`, no FK violations,
schema versions core/references/shots/timeline all `1`). The new project had
only its normal `plan.md` and `project.json` before generation.

Public discovery first:

- `python3 -m astrid --help`/`help` exposed the eight gateway families and
  nested mounts, but no generation family or model/mode/backend census.
- SDK discovery found `generation.generate_video` and
  `generation.generate_audio`. The capability schemas require `model`,
  `mode`, and `execution`; modality docs identify `ltx-2.3` + `flf` + `local`
  as the intended wired video cell, while audio is `music` only and local is
  documented as a follow-up.
- Runtime typed-facade discovery showed `astrid.generate.video(...)` and
  `astrid.generate.image(...)`, but no `astrid.generate.audio(...)`; audio
  therefore required the lower-level public `astrid.invoke(...)` call.

### Preflight 1: deliberately missing FLF end frame

Called the typed facade with `model='ltx-2.3'`, `mode='flf'`,
`execution='local'`, the tiny image as `image_ref`, and no `image_end_ref`,
with `dry_run=True, check_binaries=True`.

Observed result: `InvocationResult(ok=True, dry_run=True, run_id=None)`;
`missing_binaries=[]`; command contained `--image-ref` but no
`--image-end-ref`; `error=null`. `runs list --project motion-sound-lab`
remained empty. This is a concrete dry-run false positive: the user receives
no warning that the defining FLF end frame is missing.

### Preflight 2: complete FLF video and local audio

With both frame paths supplied, video dry-run again returned `ok=true`,
`run_id=None`, and a command containing both `--image-ref` and
`--image-end-ref`. That demonstrates command construction but not local
runtime availability.

Audio was dry-run through the public generic invoke surface with
`generation.generate_audio`, `model='stable-audio-3-medium'`,
`mode='music'`, `execution='local'`, prompt, `duration=2.0`, and WAV output.
It also returned `ok=true`, `run_id=None`, `missing_binaries=[]`, and a
constructed local command. This contradicted the public audio contract and
model documentation, which list the model as cloud-only and local audio as a
future follow-up.

### Live local execution

1. Video (`ltx-2.3` / `flf` / `local`, both frame refs): the typed facade
   raised `CapabilityRuntimeError` with the exact underlying failure:
   `ModuleNotFoundError: No module named 'vibecomfy'`. No output files were
   returned. Kernel run `0518087c58ba438fda3d2f9100` is `failed`, with one
   failed child and empty outputs.
2. Audio (`stable-audio-3-medium` / `music` / `local`): the public invoke
   returned `ok=false`, run `26b749fa6c2cc79b2f5596e4b6`, with the exact
   executor error: `model 'stable-audio-3-medium' mode 'music' has no 'local'
   backend. Available backends: cloud`. The nested recovery metadata says
   `retry with one of the available backends: cloud`; that is technically
   accurate but conflicts with this user's no-paid constraint, so the correct
   user guidance is to stop and install/configure a local audio route rather
   than retry cloud.

The final ledger contained exactly those two failed executor runs and no
successful run or generated media. `runs show --evidence` reported empty
evidence/output arrays for both.

## Severity-ranked UX critique

### P0 — FLF dry-run does not enforce the defining end-frame requirement

The documented `flf` contract says `image_end_ref` is required and that
request validation hard-fails before generation. In live SDK usage, omitting it
was silently normalized into a successful dry-run command. This undermines the
user's trust in “preflight before admitting anything” and can let an agent
approve an impossible request. Fix by applying the same mode-specific
`requires` validation to dry-run and live paths, returning a typed error that
names `image_end_ref` and shows the recovery action. Add a parity check that
dry-run and live request validation produce the same result without creating a
run.

### P1 — dry-run does not expose unavailable backend/model pairs

The audio dry-run accepted `stable-audio-3-medium` + `music` + `local`, even
though the model has only `cloud` and the docs explicitly say local is not
wired. A no-paid user only discovers this after kernel admission. Preflight
should resolve the model/mode/backend matrix and fail with the exact available
backends before admission; it should not claim `missing_binaries=[]` as if the
route were executable.

### P1 — audio has no typed modality facade

The SDK exposes typed `generate.video` and `generate.image`, but no
`generate.audio`; agents must know to drop to generic `astrid.invoke` and
manually supply the capability ID and kind. This increases discovery burden
and makes modality UX inconsistent. Add `astrid.generate.audio(...)` with the
same `execution`, `project`, `dry_run`, and prerequisite-checking semantics.

### P1 — local video prerequisite failure is technically truthful but not
actionable

`ModuleNotFoundError: No module named 'vibecomfy'` is accurate, and the run did
not fall back to cloud, which is good safety behavior. However, the error does
not explain that the requested local backend needs VibeComfy/ComfyUI setup, how
to verify it, or that retrying cloud would violate the user's no-paid policy.
Convert this into a typed prerequisite error with a concise recovery path and
an explicit “no cloud fallback was attempted” statement.

### P2 — capability discovery is split across surfaces

The top-level help gives the eight kernel families but not generation
capabilities. The agent must discover capability IDs via SDK, then read
modality docs to learn actual models, modes, backend cells, and cost/local
status. A public generation census or capability schema field exposing the
model→mode→backend matrix would reduce this avoidable navigation burden.

### P2 — failed-run side effects are safe but should be clearer

The kernel correctly records failed live attempts, and no artifacts were
created. For a user who asked “before admitting anything, dry-run/preflight,”
the distinction between dry-run (no run) and live failure (run admitted) is
important. The invocation result/CLI should say “admitted local run; failed
before output” and link the run ID, while explicitly stating that no cloud or
paid route was used.

## Recommended acceptance criteria

- Missing `image_end_ref` in `flf` returns a typed preflight error in both dry
  run and live validation, with zero ledger side effects.
- A model/mode/backend pair with no local backend fails in dry-run, lists valid
  backends, and creates no run.
- Every generation modality has a symmetric typed facade, or discovery makes
  the generic invoke path unmistakable.
- Missing local runtime dependencies produce actionable prerequisite guidance
  and never auto-select cloud.
- A failed local live attempt reports its admitted run ID, zero outputs, and a
  machine-verifiable `execution=local` provenance marker.

