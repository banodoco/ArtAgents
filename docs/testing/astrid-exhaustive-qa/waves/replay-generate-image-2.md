# Replay: generate image (live agent UX)

## Verdict

**FAIL.** Project creation, capability discovery, admission, and task
inspection work, but no image was produced. The live UX also exposes two
serious state problems: `runs list/show` remained `running` after the child
task was already `failed`, and the SDK `runs.close()` defaulted to
`outcome="succeeded"`, converting all three failed runs into runs reported as
`succeeded` with `failed: 1, succeeded: 0`.

## Chronology and evidence

All commands used a fresh `ASTRID_PROJECTS_ROOT`:

`/private/tmp/astrid-replay-generate-image-I5VcMp`

1. `python3 -m astrid --help` exposed the eight-family gateway. Initial
   `doctor --json` correctly reported a missing database and instructed the
   agent to run `projects create`.
2. `projects create poster-lab --name "Poster Lab" --json` succeeded with
   project id `d9ec02b9-9966-56ad-8e0d-f0a936a259e8`. `projects show/list` and
   the post-create doctor check were consistent; the project `plan.md` was
   created.
3. Typed SDK discovery found the canonical executor
   `generation.generate_image`, requiring `mode`, `model`, and `execution`.
   It advertised backends `local`, `cloud`, and `codex`, and models including
   `flux-schnell` (the initial `gpt-image-1` attempt truthfully returned the
   available-model list).
4. The canonical typed invocation was attempted three times for the requested
   prompt, `mode=t2i`, `size=256x256`, `count=1`:

   - `93bd64a50cf629916efd91384f` / task
     `06ec7435b2918a004b38c8fdc8`: `codex`, initially invalid model
     `gpt-image-1`; admitted, then failed with an actionable unknown-model
     error listing valid models.
   - `d905ec1a679e60fc0bce210be9` / task
     `d6977b5f5910bf669d0cd993a3`: `local` + `flux-schnell`; admitted, then
     failed because that model has no local backend (the error suggested
     `cloud` or `codex`).
   - `8d52518bc027331b0945217097` / task
     `dbfbae1e553fb07110af20d747`: `codex` + `flux-schnell`; admitted, then
     failed because the Codex session produced no `ig_*.png`.

5. CLI `runs list`, `runs show --evidence`, `tasks list`, and `tasks show`
   exposed every run/task id and showed all three child tasks as `failed`.
   Typed `AstridClient` list/show calls returned the same IDs, specs, and
   child-failure progress. This is good inspectability, but before explicit
   close the run rows incorrectly reported `status=running` while progress
   reported `status=failed` and the tasks had terminal `finished_at` values.
6. `AstridClient.runs.close(project_id, run_id)` was used to terminalize the
   admitted runs. Its default `outcome="succeeded"` changed each run to
   `status=succeeded` despite `failed=1` and `succeeded=0`. This is a direct
   semantic mismatch visible in both typed SDK and CLI output.
7. Final `doctor --json` was structurally healthy (SQLite quick check, FK,
   and schema checks passed) but warned of **3 orphaned staging directories**
   under `.astrid/media/.staging`.

## Output/provenance location

For a successful project-scoped generation, the run root is expected at:

`/private/tmp/astrid-replay-generate-image-I5VcMp/poster-lab/runs/<run-id>/`

The generation capability advertises `images/` and `manifest.json` beneath
that run root; the manifest is the generation provenance surface. No
`poster-lab/runs/` directory or image/manifest output was created for any of
these failed attempts, so there is no output to inspect or view.

## Remaining friction

- The generation UX requires a model/backend pair but does not make the valid
  pair obvious before invocation; discovery is verbose and the first invalid
  attempt is the practical way to learn the registry.
- `flux-schnell` being listed among image models while `local` is unsupported
  is surprising; the error is actionable only after a failed admission.
- A Codex backend is exposed as a built-in/no-paid-credential route, but the
  live attempt yielded no output and only a low-level “no ig_*.png” error.
- Run terminal state is stale until explicit close, and the close default can
  falsely mark failed work as successful. This is the highest-severity UX/data
  integrity issue observed.
- Three orphaned staging directories remain after the failures.
