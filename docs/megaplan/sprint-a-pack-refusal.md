# Astrid Sprint A — System refuses canonical-bypass invocations

**Profile:** `solo/bare` (tier 1 DeepSeek end-to-end, bare robustness — plan → finalize → execute; no critique pass needed for a mechanical 30-minute change).

## Goal

Make Astrid pack `run.py` modules refuse direct invocation when called outside the canonical `astrid <verb> run <id>` path. This closes the **canonical_path_bypass** friction pattern — the most-cited MAJOR issue across v6, v7, and v8 dogfoods — at the call site, in the channel the agent is already watching, with a clear remediation message.

The test pipeline already *detects* this bypass post-hoc; the principled fix is making the system itself refuse. Detection then becomes redundant (kept for visibility).

## The mechanism (deliberately simple)

1. Add ONE shared helper file: `astrid/packs/_canonical_entrypoint.py`. Defines `guard_canonical_entrypoint()` — a function that:
   - Reads `os.environ.get("ASTRID_INTERNAL_INVOCATION")`.
   - If unset, prints a remediation message to stderr and `sys.exit(2)`.
   - If set, returns silently (no-op).

   Remediation message shape (substitute `<pack_id>` per pack):

   ```
   error: this pack is not meant to be invoked directly.
   use the canonical CLI:
       astrid executors run <pack_id> --input ... --out ...
     or:
       astrid orchestrators run <pack_id> --input ... --out ...
   (direct `python -m astrid.packs.<...>.run` invocation is reserved for
   internal use by the astrid runner.)
   ```

2. Wire `guard_canonical_entrypoint()` into each pack's `run.py` `__main__` block. Two equivalent patterns; pick whichever matches the pack's existing style:

   ```python
   if __name__ == "__main__":
       from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint
       guard_canonical_entrypoint("builtin.hype")
       main()
   ```

3. Set `ASTRID_INTERNAL_INVOCATION=1` in the env passed to the pack subprocess in:
   - `astrid/core/orchestrator/runner.py` — wherever it spawns the pack's `run.py`
   - `astrid/core/executor/runner.py` — same

That's the whole change. ~30 lines added across the codebase.

## Touchpoints

- **Create**: `astrid/packs/_canonical_entrypoint.py` (~15 lines)
- **Edit**: every pack's `run.py` `__main__` block (one import line + one call line). Approximately 15–20 packs under `astrid/packs/`. Locate via:
  ```
  find astrid/packs -name run.py -exec grep -l '__name__ == "__main__"' {} \;
  ```
- **Edit**: `astrid/core/orchestrator/runner.py` to inject the env var when spawning pack subprocesses.
- **Edit**: `astrid/core/executor/runner.py` — same.

## Verification

Three checks, in this order:

1. **Direct invocation rejects:** `python3 -m astrid.packs.builtin.orchestrators.hype.run --help` should exit 2 with the remediation message on stderr.
2. **Canonical invocation works:** `python3 -m astrid orchestrators run builtin.hype --help` should print the orchestrator help normally (the env var is set internally).
3. **Existing tests pass:** `pytest tests/ --ignore=tests/agentic/` — no regressions. Pre-existing `generate_image/executor.yaml` float-type breakage is allowed (separately ticketed).

## Hard constraints

- **Do NOT stash, reset, checkout, or otherwise touch the user's uncommitted working-tree changes.** ~149+ files are uncommitted and load-bearing.
- **Do NOT commit.** Leave changes uncommitted.
- **No `git stash`.**
- **Do NOT add complexity beyond the simple mechanism above.** No registry, no decorator, no class hierarchy, no per-pack opt-out flag. The deliberate simplicity is the point: one helper, called in one place per pack.

## Out of scope

- Stateful contracts (`author patch` requiring recent `author check`) — separate sprint.
- Scaffolding-verb enforcement (refusing pack registration outside `executors new`) — separate sprint.
- Test-runner-side enforcement (Sprint B: report shape, missing tool calls) — separate sprint.
- Refactoring pack run.py modules beyond the two-line `__main__` block addition.
- Removing the universal_checks `canonical_path_bypass` detector in the auditor — keep it for visibility.

## Done criteria

1. `astrid/packs/_canonical_entrypoint.py` exists with `guard_canonical_entrypoint(pack_id: str)` exported.
2. Every pack run.py that has a `__main__` block calls the guard.
3. Both runners (`orchestrator/runner.py`, `executor/runner.py`) set `ASTRID_INTERNAL_INVOCATION=1` in the env passed to pack subprocesses.
4. Direct invocation of any pack `run.py` exits 2 with the remediation message.
5. Canonical invocation via `astrid <verb> run <id>` works unchanged.
6. `pytest tests/ --ignore=tests/agentic/` passes (modulo pre-existing breakages).

## Why solo/bare

- Mechanical change. Pattern is identical across every pack.
- No novel architecture, no judgment calls, no security implications.
- Brief is fully specified — file paths named, line shape named, env var name named.
- Critique pass would have nothing to push back on.
- DeepSeek end-to-end suffices; ~$0.20–0.50 spend, ~10–15 min wall-clock.
