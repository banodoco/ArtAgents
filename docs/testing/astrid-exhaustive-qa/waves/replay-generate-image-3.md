# Fresh-agent live replay: generation image (wave 3)

Date: 2026-08-23  
Mode: live CLI/SDK usage only (no pytest, source inspection, or prior QA-report inspection)  
Isolated root: `/tmp/astrid-replay3-vrxbZ5`

## User task

Create project `poster-lab`, then use the canonical generation path to make a
small image of a red paper boat floating on a dark blue pond. Prefer a local or
built-in route without paid credentials; if unavailable, perform the closest
truthful dry run and inspect all admitted run/task state and provenance.

## Actions and observed evidence

1. `python3 -m astrid projects create poster-lab --name 'Poster Lab' --json`
   succeeded. The project was created with id
   `acd13df4-bfa1-5c56-81e5-bcdf6186a3a7`; its `plan.md` and `project.json`
   were present.
2. `python3 -m astrid doctor --json` before generation passed all required
   checks: SQLite quick check, foreign-key integrity, data paths, and schema
   versions (`core=1, references=1, shots=1, timeline=1`).
3. The live SDK facade was exercised with:

   ```python
   astrid.generate.image(
       prompt="a small image of a red paper boat floating on a dark blue pond",
       project="poster-lab", backend="local", model="flux-schnell",
       size="256x256", count=1,
   )
   ```

   The facade admitted and executed the invocation, then raised
   `CapabilityInvocationError: generation invocation failed`. The backend
   selection in the admitted spec was normalized to `execution="cloud"`
   despite the requested `backend="local"`.
4. `runs list` admitted exactly one run:
   `9129ff2d01c4c475e31c3e4165`, capability
   `generation.generate_image`, status `failed`, with one failed child.
   `tasks list` admitted exactly one child:
   `b678ec64e02512faac110f1149`, status `failed`.
5. `runs show --evidence` agreed with the task ledger: `total_children=1`,
   `failed=1`, `succeeded=0`, `cancelled=0`, run status `failed`, and no
   evidence/output entries. `tasks show` agreed on the same run id, child
   status, and terminal timestamp.
6. The child event stream showed the complete lifecycle
   `created -> claimed -> started -> failed`. The terminal failure carried an
   actionable error: `FAL_KEY not found`, with recovery command to set
   `FAL_KEY` or pass an explicit env file. No image was falsely reported.
7. Calling the default SDK close operation on the already-failed run returned
   a typed `terminal_state` error (`the record is in a terminal state`) and did
   not change the run back to success/running. This confirms default close
   cannot contradict a failed child.
8. A final `doctor --json` passed all checks. The project tree contained only
   `plan.md` and `project.json`; no run output, staging directory, or orphan
   staging artifact was left behind.

## Verdict

**PASS for truthful failure handling and ledger consistency; BLOCKED for image
production.** The local/built-in preference did not result in a local
executor: the canonical facade admitted a cloud/FAL execution and failed
cleanly because `FAL_KEY` is unavailable. Run/task IDs and statuses agree,
failure is terminal and actionable, close cannot contradict it, and doctor
reports no orphan staging. The acceptance condition permits this backend
unavailability; producing the requested pixels requires configuring `FAL_KEY`
or an actually available local generation backend/model runtime.
