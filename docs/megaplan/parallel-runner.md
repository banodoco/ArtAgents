# Astrid agentic parallel runner — sprint brief

**Profile:** `solo` (tier 1, light robustness, low depth — DeepSeek end-to-end).

## Goal

The v6/v7 agentic dogfoods run scenarios *sequentially* (one at a time) inside a single Python process via `ThreadPoolExecutor`. With 13 scenarios at ~5–10 min each, wall-clock is ~80–90 min per dogfood, and debugging interleaved stderr is painful.

This sprint adds **process-per-scenario parallel execution with per-scenario filesystem isolation**, cutting wall-clock to ~12–15 min while improving (not regressing) debuggability.

The shape: each scenario becomes its own subprocess with its own `ASTRID_HOME` + `ASTRID_PROJECTS_ROOT`, its own stdout/stderr log files, its own exit code. A coordinator launches up to N at a time (semaphore), waits for all, then invokes `pattern_finder` on the combined results.

## What blocks this today — 3 hardcoded path leaks

Astrid has the two env vars we need (`ASTRID_HOME`, `ASTRID_PROJECTS_ROOT`) and both have resolver functions. But three call sites bypass the resolver and hardcode the default path, so per-scenario isolation is leaky today.

**Fix these first**:

1. **`astrid/core/task/lifecycle.py:569`** — replace the hardcoded `Path(_os.path.expanduser("~/Documents/reigh-workspace/astrid-projects"))` with a call to `resolve_projects_root()` from `astrid.core.project.paths`. This is a real bug that affects any user setting `ASTRID_PROJECTS_ROOT`, not just our test infrastructure.

2. **`tests/agentic/runner.py:186, 348`** — same hardcoded path twice. Import and use `resolve_projects_root()`.

3. **`tests/agentic/auditor.py:31`** — `ASTRID_PROJECTS_ROOT = Path.home() / "Documents" / "reigh-workspace" / "astrid-projects"` is evaluated at module-import time, making it impossible to override via env var even if callers set it. Replace the module-level constant with a function (or property) that reads `os.environ` at call time. Callers at lines 42, 270, etc. need to use the function.

After these fixes, both env vars work end-to-end and per-scenario isolation is clean.

## The coordinator (`tests/agentic/parallel_runner.py`)

A small CLI tool, ~60–100 lines:

```
python -m tests.agentic.parallel_runner --all --parallel 3 [--tag v8]
python -m tests.agentic.parallel_runner specific_transcribe cold_restart_midrun --parallel 2
```

### Behavior

1. **Scenario discovery**: same shape as `runner.py --all` — read scenario YAMLs from `tests/agentic/scenarios/*.yaml` (filter `_schema.yaml`).

2. **Per-scenario isolation**: for each scenario, allocate a fresh isolated home:
   ```
   /tmp/astrid-parallel-<tag>/<scenario>/{home,projects,logs}/
   ```
   Set env for the child subprocess:
   ```
   ASTRID_HOME=/tmp/astrid-parallel-<tag>/<scenario>/home
   ASTRID_PROJECTS_ROOT=/tmp/astrid-parallel-<tag>/<scenario>/projects
   ```
   `mkdir -p` both paths before spawning.

3. **Spawn**: `subprocess.Popen` of `python3 -m tests.agentic.runner <scenario> --tag <tag>` with the env above merged into `os.environ`. Capture stdout and stderr to:
   ```
   /tmp/astrid-parallel-<tag>/<scenario>/logs/stdout.log
   /tmp/astrid-parallel-<tag>/<scenario>/logs/stderr.log
   ```

4. **Semaphore at N**: use `concurrent.futures.ProcessPoolExecutor(max_workers=N)` OR a manual semaphore over `subprocess.Popen` — whichever is cleaner. Default `--parallel 3` (sweet spot for rate-limit headroom).

5. **Aggregate**: as each child finishes, log "[<scenario>] exit=<code> elapsed=<s>". After all done, print a summary:
   ```
   v8 parallel dogfood: 11/13 scenarios passed
     ✓ cold_restart_midrun (passed=1/1, 287s)
     ✗ idempotent_reattach (passed=0/1, 412s) — see /tmp/astrid-parallel-v8/idempotent_reattach/logs/
     ...
   total wall-clock: 873s (~14.5 min)
   ```

6. **Pattern_finder invocation**: after all scenarios complete (including the aggregator pass on each scenario's `tests/agentic/reports/<tag>-<scenario>/summary.json`), run `python -m tests.agentic.pattern_finder --run-dir tests/agentic/reports/<tag>` so the cross-scenario `run.md` synthesis is produced exactly as in the sequential pipeline.

7. **Cleanup helper**: separate CLI `python -m tests.agentic.parallel_runner --cleanup [--tag v8] [--all]`. Removes `/tmp/astrid-parallel-<tag>/` (or all `astrid-parallel-*` dirs with `--all`). Default dry-run; `--apply` to actually delete.

### Constraints on the coordinator

- **Each child sees the full pack registry, key files, etc.** — only `ASTRID_HOME` and `ASTRID_PROJECTS_ROOT` change. The repo at `/Users/peteromalley/Documents/reigh-workspace/Astrid` is shared (read-only by the children for their pack manifests).
- **`~/.hermes/.env`** is shared. Children read DEEPSEEK_API_KEY and FIREWORKS_API_KEY from the same place. Fine.
- **Reports land in the shared `tests/agentic/reports/<tag>-<scenario>/`** — these are the runner's outputs (narrative report + stderr + summary.json + evidence pack). Each child writes to its own scenario dir, no collision.
- **The runner itself is unchanged.** The coordinator dispatches the existing runner per scenario; it does NOT rewrite the runner's per-scenario logic.

## Verification

1. **Unit-shape**: a smoke test that `parallel_runner.py --all --parallel 1 --tag smoke` produces the same per-scenario `summary.json` files as `runner.py --all --tag smoke` would. Differential: no `tests/agentic/reports/smoke-*` files orphaned in unexpected places.

2. **Single-scenario isolation check**: set `ASTRID_HOME=/tmp/parallel-test/home` and `ASTRID_PROJECTS_ROOT=/tmp/parallel-test/projects` manually, run `python -m tests.agentic.runner specific_transcribe --tag iso-check`, confirm:
   - `/tmp/parallel-test/home/sessions/*` has the new session
   - `/tmp/parallel-test/projects/agentic-specific-transcribe-ds-1/` has the project state
   - `~/.astrid/` is untouched
   - The runner completes without errors

3. **Two-scenario parallel check** (cheap): `parallel_runner.py concurrent_disambiguation specific_transcribe --parallel 2 --tag two-test`. Verify both complete, exit codes are independent, logs are isolated per scenario.

4. **Existing `tests/`** still pass: `pytest tests/ -x --ignore=tests/agentic/ -k "session or project_paths"` — anything path-resolution-adjacent should be re-run since the lifecycle.py and auditor.py edits touch resolver call sites.

## Hard constraints (operating notes)

1. **There is currently a v7 dogfood running in the background** (`pgrep -f "tests.agentic.runner --all"`). Do NOT modify `astrid/core/task/lifecycle.py`, `tests/agentic/runner.py`, or `tests/agentic/auditor.py` until that process has exited. Check `pgrep` at the start of the execute phase; if the v7 runner is still alive, poll every 60s with `until ! pgrep -f "tests.agentic.runner --all" > /dev/null; do sleep 60; done` before any file edits.
2. **Do NOT stash, reset, checkout, or otherwise touch the user's uncommitted working-tree changes outside the files explicitly modified in this sprint.** The working tree has ~149 modified files; they're load-bearing. Work alongside them.
3. **Do NOT commit anything.**
4. **No `git stash` under any circumstances.** Past sub-agent attempts violated this; do not.
5. **Do NOT run the v8 parallel dogfood at the end of this sprint.** Build + verify only. The user will kick off v8 themselves after the sprint lands.

## Out of scope

- Changing the per-scenario runner's internal behavior (priming, capture, audit).
- Adding new acceptance criteria or rubric questions.
- Rate-limit handling beyond the `--parallel N` semaphore (no exponential backoff, no per-host throttle).
- Migrating the existing sequential `runner.py --all` interface — keep it working alongside the new parallel runner.
- The `astrid/packs/builtin/generate_image/executor.yaml` float-type bug (separately ticketed; do not fix here).

## Acceptance criteria for this sprint

1. The 3 hardcoded path leaks are fixed and tests for path resolution pass.
2. `tests/agentic/parallel_runner.py` exists with `--all`, `--parallel`, `--tag`, and `--cleanup` flags as documented.
3. The single-scenario isolation check (verification #2 above) passes — projects land in the isolated dir, not in `~/Documents/reigh-workspace/astrid-projects/`.
4. The two-scenario parallel check (verification #3) completes without error and produces 2 independent log dirs + 2 independent project dirs.
5. `pytest tests/ -x --ignore=tests/agentic/ -k "session or project_paths"` is green.
6. A one-paragraph note in `tests/agentic/README.md` documents the new parallel runner with the basic invocation.

## Why `solo/light`

- All work is mechanical: 3 refactor-to-resolver edits + 1 new ~60-line script.
- Brief is tight (lines pre-identified, behavior pre-specified, invocation pre-specified).
- No security, no migration, no public API contract.
- One critique pass catches any "did you actually re-read env at runtime?" type oversight; that's all the rigor needed.
