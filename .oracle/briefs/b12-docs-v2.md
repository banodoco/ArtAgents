# BATCH 1.2 — run-ledger-contract v2 + aligned docs

You are a normal-pool executor (stealth/ox-alpha) in the worktree /Users/peteromalley/Documents/reigh-workspace/Astrid-unified-oracle (branch oracle-unified-execution). NO git commands. NO formatters. DO NOT touch code files — docs only.

## Task
Rewrite docs/contracts/run-ledger-contract.md as the SINGLE-LEDGER contract for the unified-execution end state being built on this branch:
- Kernel = execution authority: every capability invocation becomes a kernel run+task (admit → claim → start → execute → complete|fail), events + receipts + attempts/leases.
- FS run.json becomes a DERIVED PROJECTION written once from kernel state at finalize: stamped `"authority": "kernel"`, `kernel_task_id`, `kernel_run_id`; never read back as authority; status authority moves to the kernel projection (`derive_run_progress_counts`).
- Remove/replace: "no automatic bridge" section, the FS-only invariant scoping, "canonical" language for run.json status, any claim that direct-mode writes no kernel rows (the unified end state makes sdk.invoke admit kernel tasks).
- Keep accurate sections: argv redaction, log-capture risk, prompt embedding, threads dialect tolerance, doctor read-only limits.
Align to the same end state: astrid/packs/_core/skill/SKILL.md (task-mode/runs sections), docs/guides/async-completion.md, docs/guides/creating-tools.md — remove "test-wired only"/"two-ledger" hedges that the unified execution supersedes; keep honest about what ships when it ships.
Do NOT edit astrid/packs/generation/** or docs/generation/** (user-in-flight).

## Verify
grep gates: zero occurrences of "two ledgers", "no automatic bridge", "test-wired only", "canonical" applied to run.json status across docs/contracts/run-ledger-contract.md, SKILL.md, async-completion.md, creating-tools.md. `python3 -m pytest tests/v10/test_docs_cli_alignment.py -q --basetemp=/tmp/b12-t` green; rm -rf after.

## Report (<200 words)
Files changed + key sentences + gate output.
