# EXECUTE — Batch B1: Baseline lock + pin the data (plan tasks 1, 2)
You are the executor (stealth/ox-alpha). Worktree: /workspace/reigh-phase-a-20260822/Astrid, branch phase-b. Implement directly - you ARE the executor.

NORTH STAR (binding): One authority (one SQLite file + SHA-256 tree). Correctness by primitives (each primitive gets a named test). Invisible failure default (crashes leave orphans or replays, never partial authority). Growth by declaration. Honest latency. Anti-patterns to reject: digest-the-code pinning, second authorities, ceremony without consumer, speculative machinery.

YOUR BATCH (from frozen .oracle/tasklist.md Batch B1 - read it there for full detail):
- T1.1 (normal): B-0 baseline ledger - run the full suite once, record output verbatim to .oracle/evidence/b0-baseline.txt including the two known collection errors (tests/packs/rendering/test_timeline_visualize_parity.py banodoco_timeline_schema; tests/timeline/test_inverses.py).
- T1.2 (normal): Pin the data, not the code - vendor shipped workflows as Comfy API-format JSON under astrid/core/integrations/reigh/workflows/*.json; populate CapabilityEntry.template = (path, sha256) with canonical-bytes digests; admission snapshots workflow bytes into attempt provenance; commit-SHA-pin the floating vibecomfy git requirement (pin FIRST, then validate digests against pinned bytes).
ORDERING: pin vibecomfy commit first, then validate vendored digests.

ACCEPTANCE (oracle verifies exactly):
- Tampered workflow file => execution refuses fail-closed before any byte write (named digest-fence test).
- grep over requirements files shows zero floating refs (git+ without @<sha> absent).
- CapabilityEntry.template populated for every shipped workflow-backed entry; digest matches vendored bytes on disk.
- B-0 ledger file exists with full-suite output and the two collection errors recorded verbatim.

VALIDATION: python3 -m pytest tests/v10 tests/integrations/reigh tests/packs -x -q plus the new digest-fence test file.

DISCIPLINE: commit to phase-b after each task (converge/B1: <task>); run focused tests before each commit; if blocked >30min write BLOCKED: <reason> to /workspace/reigh-phase-a-20260822/B1.blocked and exit 0. When both tasks pass acceptance, write /workspace/reigh-phase-a-20260822/B1.done and exit 0.
