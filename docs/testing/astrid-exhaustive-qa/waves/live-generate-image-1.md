# Live UX wave: generate an image (poster-lab)

Date: 2026-08-23 (Europe/Berlin)  
Operator: fresh agent-user, live CLI + public SDK usage  
Scope: create a project and use Astrid's canonical generation path for a small image of a red paper boat floating on a dark blue pond. No source changes, no pytest, and no direct pack `run.py` invocation.

## User goal and isolation

I created an isolated root with `mktemp -d`:

`/tmp/astrid-live-generate-YP7jRX`

The project was created as `poster-lab` / `Poster Lab`. No pre-existing project was used or modified.

## Chronological interaction log

1. **Discovery (about 8 seconds total).** Started with `python3 -m astrid --help`, `python3 -m astrid help`, `--version`, and `doctor --json`. The help census was clear about the eight families and said product commands need no configuration, credentials, or hosted service. On a brand-new root, doctor correctly reported the expected missing database and suggested `projects create`.

2. **Project creation (about 1 second).** Ran:

   `ASTRID_PROJECTS_ROOT=/tmp/astrid-live-generate-YP7jRX python3 -m astrid projects create poster-lab --name "Poster Lab" --json`

   This succeeded and returned project ID `36e6137e-8998-5bdd-8c2c-e4173ac74dd8`, receipt/event data, and a generated `poster-lab/plan.md` plus `project.json`.

3. **Project read-back (about 7 seconds).** `projects show poster-lab --json` succeeded, but `projects list --json` failed with an unstructured `disk I/O error`. Doctor then showed SQLite quick-check, FK, and schema checks failing with the same disk I/O error. This was environmental disk exhaustion (the filesystem had only about 158 MiB available and was at 100%); retrying did not cure it. I did not delete unrelated user data.

4. **Generation-path discovery (about 3 seconds).** Read the public Astrid skill, generation README, image contract, and image executor stage documentation. The public docs identify `generation.generate_image`, require `model`, `mode`, `execution`, and prompt, and document local VibeComfy, cloud Fal, and Codex routes. The skill explicitly says the SDK is the canonical entry and says never invoke pack `run.py` directly. The stage doc's CLI quick-start nevertheless shows direct `run.py` commands, which is a discoverability contradiction; I followed the SDK as the canonical path.

5. **Backend readiness.** `codex` was on PATH and `~/.codex/auth.json` existed, so the documented Codex route appeared potentially runnable without a paid API key. Local VibeComfy was also documented but no running ComfyUI endpoint was established. I chose the documented SDK invocation with local execution first, to avoid paid cloud credentials.

6. **Capability inspection (about 1 second).** `astrid.get_capability("generation.generate_image", kind="executor", include_installed=False)` succeeded. It exposed the expected required inputs (`mode`, `model`, `execution`) and generation outputs (`generated_images`, `image_manifest`).

7. **Truthful dry run (about 1.2 seconds).** Ran `astrid.invoke(..., project="poster-lab", dry_run=True)` with:

   - model: `z-image`
   - mode: `t2i`
   - execution: `local`
   - prompt: `a small image of a red paper boat floating on a dark blue pond`
   - size: `512x512`

   The dry run returned `ok=True`, showed the exact generated subprocess command, and reported no missing binaries. It correctly had no run ID, no run root, and no outputs because it was only a preview.

8. **Actual live invocation (about 1.7 seconds).** Ran the same call without `dry_run`. Astrid admitted a kernel run and child task, returning:

   - run ID / kernel run ID: `1bb3174e06302c0c82a1d0fd46`
   - kernel task ID: `f84749937d18a1c15f30068623`
   - kernel attempt ID: `01m0qm12jpzd2cmkmr1j7mwwzc`
   - run root: `/private/tmp/astrid-live-generate-YP7jRX`

   Execution failed immediately with `handler_failed`, `NameError`, message `name 'ExecutorRunRequest' is not defined`. No image, manifest, or project `runs/<id>/run.json` was produced. This is a product/runtime failure, not a missing-credentials dry run.

9. **State inspection and CLI/SDK comparison (about 5 seconds).** Ran `runs list`, `runs show <id> --project poster-lab --evidence`, `tasks list`, `tasks show <id>`, and `runs events`. All returned empty/not-found results. The typed `AstridClient` facade likewise returned `runs.list == []` and `runs.show == not_found` for the admitted ID. Thus the top-level `astrid.invoke` response exposed an admitted run/task, but the CLI and typed read surfaces could not see it. This is a direct run-ID/state disagreement.

## Outcome and provenance

Outcome: **no image generated**. There is no output path to inspect and no manifest/provenance artifact. The only provenance available is the failed invocation response and its IDs above. The dry-run output contained the intended command and output directory, but intentionally created no files.

The filesystem contains the isolated project's SQLite files, `poster-lab/plan.md`, and `poster-lab/project.json`; it does not contain a generated image or finalized run projection. The invocation's `run_root` points at the isolated root, but no child run bundle was finalized.

## UX critique, severity-ranked

### P0 — admitted generation is unusable

The canonical SDK invocation reaches admission, then fails with an internal `NameError` before the executor can run. A normal user receives an `InvocationResult` whose `error` field is `None` even though `ok=False`; the actual failure is nested in `raw_result`. This makes the failure hard to understand or handle programmatically.

### P0 — run/task provenance is split or lost

The SDK returned concrete run/task/attempt IDs, but `runs list/show/events` and the typed client immediately reported no such records. The user cannot inspect, retry, cancel, or locate the admitted work. This violates the documented single-ledger expectation and makes the returned IDs practically misleading.

### P1 — state commands are fragile under ordinary disk pressure

After project creation, `projects list` and doctor produced an unstructured SQLite `disk I/O error`; the error suggested retrying but did not identify the filesystem-full condition. This is especially confusing because `projects show` still worked. Error output should distinguish storage exhaustion and preserve a usable read path.

### P1 — canonical-entrypoint documentation contradicts itself

The agent-facing skill says the SDK is canonical and direct executor `run.py` modules are forbidden, while the generation stage's “CLI quick-start” instructs users to invoke `python -m ...run` directly. A fresh agent has to resolve this conflict manually. The stage docs should show `astrid.invoke`/`AstridClient` examples, or clearly label the subprocess command as internal.

### P2 — local backend readiness is under-explained

The docs say local execution requires a running ComfyUI instance, but capability discovery did not expose a simple readiness check or actionable endpoint status. The dry run reported no missing binaries even though local runtime readiness was not established.

## Suggested next live wave

Fix the `ExecutorRunRequest` admission/execution failure and reconcile the kernel ledger with CLI/typed read models. Then rerun this exact isolated scenario through Codex (no paid API key) and local execution, verifying that the returned run ID appears in `runs list/show`, that `manifest.json` and image paths are recorded, and that `media list/show` can locate the generated artifact.
