# Explore: single-ledger facade invocation

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

The render plan requires that `rendering.render` (the facade executor) owns
the ONLY project run: backend commands are leaf subprocesses that never create
`run.json`, and when an orchestrator already owns a run, the facade must be
invoked with its existing output context and no new project request.

1. `astrid/core/contracts/capability_runner.py` and
   `astrid/core/execution/executor/runner.py`:
   - What is `run_executor`'s signature? What makes it create a project run
     (a `request.project` set? explicit flag?) vs reuse an existing run
     context? Trace `prepare_project_run` and how an orchestrator's run_root
     flows to a child executor call today (orchestrator/runner.py).
   - What does `maybe_gate` / `require_project` do for executors? Does calling
     an executor from inside an orchestrator create a nested run.json?
2. `astrid/core/gateway/__init__.py` and the executor CLI handler
   (`astrid/core/cli/cli_handlers.py` or wherever `executors run` is
   implemented): what invocation path does `astrid executors run
   rendering.render` take — does it attach a session / auto-bind a project?
   Is there a "no project" mode?
3. How Hype (orchestrator) currently invokes render (`steps.py` spawns
   `python -m ...render.run` directly): confirm it does NOT create a run.json
   for the render step (only the orchestrator run exists). And how
   iteration_video's in-process `render_executor.render(...)` call behaves.
4. Is there an existing "child capability without nested run" pattern in the
   repo (e.g. orchestrators calling executors through a runner that reuses
   output dirs)? Name it with file:line.

## Report format

Ranked findings with file:line evidence. Max 300 words. End with:
- Verified facts (the exact mechanism that decides run creation)
- Unknowns
- Risks (session auto-binding, nested runs, stale output roots)
- Suggested approach (which invocation form the facade should use)
