# Replay: local image generation preflight (wave 5)

Date: 2026-08-23  
Surface: live public Python SDK usage only  
Prompt: “Generate a small red paper boat image, but only locally/no paid/cloud.”  
Isolation: fresh `ASTRID_PROJECTS_ROOT` for each probe

## Public-doc path exercised

The public Astrid generation docs identify `astrid.generate.image()` as the
typed facade and `sdk.invoke("generation.generate_image", kind="executor", ...)`
as the direct SDK surface. The image contract documents `z-image` + `t2i` +
`local` and says local readiness validation must happen before kernel admission.

## Live observations

1. `python3 -m astrid doctor --json` on the empty root was read-only. It
   reported `ok: false` with expected missing-root/database diagnostics, and
   created no files.
2. Typed facade call:

   ```python
   astrid.generate.image(
       model="z-image", mode="t2i", backend="local",
       prompt="a small red paper boat", size="256x256", steps=1,
   )
   ```

   rejected synchronously with `CapabilityPreconditionError`:
   `Local generation is not ready: local generation requires the 'vibecomfy'
   Python package; it is not installed ... Next: <python> -m pip install
   vibecomfy && <python> -m vibecomfy --help`.
3. Direct SDK call:

   ```python
   sdk.invoke(
       "generation.generate_image", kind="executor",
       inputs={"model":"z-image", "mode":"t2i", "execution":"local",
               "prompt":"a small red paper boat", "size":"256x256", "steps":1},
       project="replay-local-5",
   )
   ```

   rejected with the same actionable `CapabilityPreconditionError`. The SDK
   also emitted an unrelated installed-pack manifest warning for `hivemind`,
   but did not proceed past the local precondition.
4. Invalid selector probes remained clear and pre-admission on another empty
   root:

   - `flux-schnell` + `backend="local"`: `CapabilityValidationError`,
     “Execution 'local' is not available ... Available: cloud, codex”.
   - `z-image` + `execution="cloud"` + `backend="local"`:
     `CapabilityValidationError`, “conflicting generation backend selections ...
     provide only one or make them match”.

## Admission / side-effect check

Both local failures occurred before project DB creation, run/task admission,
staging, output creation, or network/cloud dispatch. `find` and `ls -la` on
both fresh roots showed no entries; no paid/cloud path was attempted.

## Verdict

**PASS.** The live typed and direct SDK local-generation paths correctly reject
an unavailable local runtime before any Astrid state is admitted, provide setup
guidance, preserve local-only intent, and keep invalid/conflicting selectors
understandable. Doctor remains read-only and accurately reports an uninitialized
root.
