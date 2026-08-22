# Plan brief - Phase B build (read-only planning)
You are the PLANNER. READ-ONLY. Working dir: /workspace/reigh-phase-a-20260822/Astrid (branch phase-b).
Read first: .oracle/northstar.md, .oracle/agent_goal.md (frozen contract, done criteria), docs-corpus/31-forward-map.md (B-1..B-6 workstreams), docs-corpus/27-build-spec.md sections 3-7 (registry, routes, completion UoW, worker, trust), docs-corpus/16-capability-map.md (19 capabilities), grok/worker-wgp-report.md (Wan mechanics), docs-corpus/29-ground-truth-sensecheck.md.
Code: THIS repo at HEAD phase-b - packs/shots/generation_repository.py + migrations exist (Phase A); integrations/reigh/capabilities.py + local_bridge_server.py routes exist; core/integrations/reigh/multipart.py exists. Read enough to ground tasks in real files.
Produce markdown with EXACTLY:
### 1. Tasklist covering the ENTIRE agent goal
Ordered tasks for B-1..B-6 per docs-corpus/31-forward-map.md: each with id, title, exact files, done-criterion (1-6 from agent_goal), dependencies, acceptance check. Ground in real code paths.
### 2. Additional areas to explore
5-7 areas of uncertainty (e.g. VibeComfy scratchpad format + digest pinning mechanics; ComfyUI CPU-mode viability on this box; Wan2GP headless driving contract details; orchestrator child admission envelope shape; setup-journal placement vs product SQLite).
### 3. Open questions
Only plan-changing ones.
### 4. Effort estimate
Best-effort total implementation effort with clear greater-than-2-weeks huge-run determination.
### 5. North Star check
How the plan advances each principle and avoids each anti-pattern (.oracle/northstar.md).
Cap 1800 words. No file writes.
