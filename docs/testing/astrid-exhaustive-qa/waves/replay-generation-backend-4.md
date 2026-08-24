# Replay: generation backend honesty (backend 4)

Date: 2026-08-23  
Surface: live Python SDK typed facade (`astrid.generate.image`) plus public CLI observations  
Isolation: `ASTRID_PROJECTS_ROOT=/tmp/astrid-backend-4-ICfRVD`, project `poster-lab`

## User task

> Generate a small red paper boat image, but only with a local/no-paid backend. Do not use cloud.

## Evidence

The public image contract documents `astrid.generate.image()` and says `backend` is an accepted compatibility alias for canonical `execution`; it also says an unavailable model/backend pair must fail before kernel admission and list valid backends.

1. `astrid.generate.image(model="flux-schnell", mode="t2i", backend="local", project="poster-lab", prompt="a small red paper boat", size="256x256")` rejected synchronously with:

   `CapabilityValidationError: Execution 'local' is not available for model 'flux-schnell' mode 't2i'. Available: cloud, codex`

   `astrid runs list --project poster-lab --json` and `astrid tasks list --project poster-lab --json` were both empty after this attempt. No output or cloud credential/network activity occurred.

2. Conflicting selection was tested with `model="z-image", mode="t2i", execution="cloud", backend="local"`. It rejected synchronously with:

   `CapabilityValidationError: conflicting generation backend selections: execution='cloud' and backend='local'; provide only one or make them match`

3. To probe the documented local path for a valid local model/backend pair, `astrid.generate.image(model="z-image", mode="t2i", backend="local", project="poster-lab", prompt="a small red paper boat", size="256x256", steps=1)` was attempted. It was admitted as run `e67b0c8040b6a7d50276f04920` with task `1229935e936791add7f42fa2d9`, then failed immediately. Task evidence records:

   `executor 'generation.generate_image' failed ... ModuleNotFoundError: No module named 'vibecomfy'`

   The run produced no artifact and no actionable pre-admission prerequisite error. The failed run/task rows remain visible in the isolated project.

## Verdict

**FAIL (partial honesty).** Invalid local selection and conflicting backend/execution selections are correctly rejected before admission, with useful messages and no rows. However, a documented valid local pair (`z-image` + `local`) is admitted and only then fails because the local runtime dependency is absent. For the user's no-cloud requirement, Astrid should preflight the local backend dependency and reject before admission with an actionable install/configuration message (or execute locally); it must not create a failed run/task for this prerequisite failure.
