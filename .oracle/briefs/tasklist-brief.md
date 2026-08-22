# Tasklist brief - convert the STABLE Phase-B plan into frozen-ready batches
You are the PLANNER. Working dir: /workspace/reigh-phase-a-20260822/Astrid. READ-ONLY - text output only.
NORTH STAR (binding): One authority. Correctness by primitives (each primitive gets a named test). Invisible failure default. Growth by declaration. Honest latency. Anti-patterns: second authorities/mirrored state, cloud fallbacks/silent swaps, ceremony without consumer, speculative machinery.
Read: .oracle/agent_goal.md (done criteria 1-6, huge-run YES + cumulative boundaries after B-2/B-3/B-5), .oracle/plan.md (STABLE v3).
Deliverable: .oracle/tasklist.md content (output full markdown) with:
- Batches B1..BN self-contained ending at natural seams, respecting dependencies (B-1 binding first, B-2 fan-out after, B-3 orchestrators independent-but-hard, B-4 Wan gates, B-5 acquisition journal, B-6 conformance last).
- Per batch: tasks (from plan ids), checkpoint acceptance criteria the oracle verifies exactly, agent-goal criteria advanced, North Star principles/anti-patterns in play.
- HUGE-RUN CUMULATIVE BOUNDARIES predeclared: cumulative big-batch review after the batch completing B-2, after B-3, and after B-5 (rationale: catalog seam, distributed-systems seam, upstream-dependency seam). Record rationale inline.
- Synchronization points where parallel work converges.
- Proposed normal/[XHARD] classification per task ([XHARD] requires full exceptional-threshold evidence; default normal).
- Exact validation commands per batch (python3 -m pytest ... scoped).
Output ONLY the tasklist markdown.
