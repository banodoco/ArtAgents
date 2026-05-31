# Astrid agentic testing — Sisypy migration + extensive coverage design

Synthesis of 6 parallel DeepSeek exploration passes (product surface, data retention,
discoverability, failure modes, existing-suite gaps, abstraction taxonomy).

## 0. Status / framing
- Astrid has a bespoke agentic suite at `tests/agentic/` (29 scenarios, custom runner/auditor/assessor).
- Sisypy is a sibling repo (`reigh-workspace/sisypy`), evidence-over-narrative, already referenced by vibecomfy.
- Plan: embed Sisypy into Astrid (adapter + runner), migrate the 29 scenarios, and EXPAND coverage
  across product surface, data collection/retention, and feature discoverability.

## 1. Unified taxonomy

### Primary matrix (cells; empty cell = coverage gap)
**Axis A — Capability domain:** Discovery · Timeline · Orchestration/Execution · Authoring ·
Data-Retention/Integrity · Infrastructure(sessions/leases/projects/sync) · Platform-targets(GPU/Reigh/RunPod)

**Axis B — Agent challenge:** Locate · Operate · Compose · Author · Resume · Repair · Refuse

### Qualifier tags (not matrix dims — applied as scenario tags)
- **Environment:** fresh · primed · adversarial
- **Evidence depth (proof ladder):** invoked → artifact → chain-integrity → substantiated
- **Scale:** S(1-3 events/1 orch) · M(multi-step) · L(100+ events / many runs)

## 2. Universal adapter checks (run over EVERY evidence pack — the data-correctness backbone)
This is the core answer to "do we save data correctly". Every scenario's frozen evidence is checked, not just dedicated retention tests.
1. claim-vs-evidence consistency — report claims of files/outputs must appear in tree_after + event log
2. canonical-surface enforcement — no `python -m astrid.packs.X.run` / direct import bypass
3. no-mutation-on-read — read/audit verbs produce zero new events, empty git diff
4. append-not-rewrite — "edit/append" ops grow the file / superset JSON, never truncate
5. chain-integrity — verify_chain() ok on assembly.jsonl, run events.jsonl, audit/ledger.jsonl
6. artifact-provenance — every `produces` path exists; sha256(file)==event hash; no orphan artifacts
7. projection-fidelity — project_to_assembly(events) == assembly.json (canonical compare)
8. head/sidecar consistency — head.event_count==len(events), head.last_hash==events[-1].hash, version ok
9. idempotency — reattach (strip ASTRID_SESSION_ID) → no duplicate events, same event_id
10. no-cross-project-leak — run.json.project_slug matches; no sibling-slug references in events
11. auditability — every event has actor.id + ISO ts; mutation events (erase/takeover/abort) carry reason
12. report/deliverable hygiene — report.md exists, ≥30 lines, covers requested numbered sections

## 3. Coverage matrix (Domain × Challenge) — existing vs gap
- Timeline×Operate: 9-12 scenarios (OVERPOPULATED — one-per-CLI-verb bloat → collapse into 1 compose test)
- Discovery×Locate: 3 (vague/specific/search-before-author)
- Session×Resume: 3 (cold_restart, reader_takeover, idempotent_reattach)
- Authoring×Author: 2-4 (new_orch, new_executor, modify, wrap_comfy)
- Execution×Repair: 1 (executor_failure_recovery); Execution×Refuse: 1 (impossible_brief_pushback)
- Timeline×Repair: 2 (tamper_recovery, mass_undo)

**Empty cells (priority gaps):**
- Authoring×Repair (compile-fail → fix loop) — highest priority; authoring riskiest, zero recovery cov
- Timeline×Compose (build multi-track timeline from scratch — collapses the 9 verb tests)
- Execution×Compose (artifact pipeline A→B data handoff, distinct from sequential session handoff)
- Session/Infra×Repair (corrupted .astrid-session, lease contention, disk-full)
- Discovery×Infra (discover existing projects/runs/sessions, not just packs)
- Discovery×Refuse (no tool exists → push back, don't hallucinate a tool)
- Data-Retention domain: ENTIRELY new (durability-after-crash, prune-evicts-live-ref, supabase divergence)

**Whole domains with ~zero coverage:** Supabase sync, GPU/Reigh/RunPod execution, retention/GC,
error-message legibility, large-timeline performance (scale L), same-project concurrent writers.

## 4. Build-first scenarios (tagged to user's 4 focus areas)
FOCUS-1 timeline usage / FOCUS-2 data retention / FOCUS-3 orchestrator exec / FOCUS-4 retention-from-orch

Tier 1 (migrate, must-pass gate):
- cold_restart_midrun [Session×Resume] FOCUS-3
- reader_takeover [Session×Resume] FOCUS-3
- vague_video_request [Discovery×Locate]
- specific_transcribe [Discovery×Locate]

Tier 2 (migrate, core):
- new_executor_for_cli, new_orchestrator_from_dsl, modify_existing_orchestrator [Authoring]
- executor_failure_recovery [Execution×Repair] FOCUS-3
- impossible_brief_pushback [Execution×Refuse]

Tier 3 (NEW — gap fill, spanning focus areas):
- timeline_compose_edit [Timeline×Compose, M] FOCUS-1 — build multi-track timeline; assert chain+projection
- orchestrator_run_persists [Execution×Operate, M] FOCUS-3+4 — run orch; freeze run dir; assert run.json status==success + events.jsonl chain ok + every produces exists & hash matches + finalize wrote artifacts
- artifact_pipeline [Execution×Compose, M] FOCUS-4 — orch A output feeds orch B; assert provenance chain intact across handoff
- durability_after_crash [Data-Retention×Repair, adversarial] FOCUS-2 — SIGKILL mid-append; assert head-rebuild detects desync / no half-written line accepted
- timeline_large_audit [Integrity×Operate, L] FOCUS-1+2 — 500-event log; verify_chain + audit scale, no timeout
- cross_pack_authoring [Authoring×Compose] — compose executors from 2 packs
- broken_authoring_fix [Authoring×Repair, adversarial] — compile error → author check → fix → recompile
- session_corruption_recovery [Infra×Repair, adversarial] FOCUS-2 — corrupt .astrid-session; detect+recover
- no_tool_exists_pushback [Discovery×Refuse] — exhaust search, conclude none, push back
- concurrent_same_project_writers [Infra×Operate, adversarial] FOCUS-2 — 2 writers; exactly one wins lease, no interleaved ledger

## 5. Real defects/risks surfaced by exploration (candidate tickets, independent of tests)
- Supabase event-log backend is transport-mocked/unimplemented — any "synced to Supabase" claim is false (eventlog/supabase.py)
- asset_cache prune() is purely time-based; can evict assets still referenced by a project source (no ref counting)
- head/jsonl desync window: crash between line-append fsync and head atomic-write leaves head.event_count off-by-one
- run_aborted only written on explicit cmd_abort; natural crash leaves run.json status="prepared" with no terminal event
- projection staleness: appending events without re-projection lets assembly.json diverge until regenerated
- discoverability metadata gaps: editor_review (no "grade/critique/brief"), thumbnail_maker (no "YouTube"),
  foley_map (no "sound effects/sfx"), event_talks (no "conference/presentation"), iteration_video (no "compare/before-after")
- skills docs: only 2 SKILL.md across all packs; discovery-for-agents.md tells agents to read skill docs that don't exist
- unknown-id errors (KeyError "unknown orchestrator id") give no "try list/search" recovery hint

## 6. Migration mapping (existing → Sisypy)
- assessment {enforced,graded,observed} → 1:1 (already matches Sisypy)
- events_contain / no_aborts / tool_used / leaf_count_complete → adapter parses events.jsonl + plan.json; map to proof ladder
- shell_calls_under → observed (telemetry)
- no_cross_project_binding → enforced
- subjective: block → redundant; fold into assessment.rubric
- universal checks (detect_contradictions, canonical_path_bypass, deliverable_shape) → Sisypy universal checks
- priming verbs (create_project/start/ack/write/touch) → adapter prime_workspace hook
- adapter must additionally capture: assembly.jsonl, run.json/current_run.json, audit/ledger.jsonl, verify_chain output, git diff

## 7. Open decisions for the user
1. Migrate-in-place (replace custom harness, keep tests/agentic/ path) vs build alongside then cut over?
2. Scope: full migration of 29 + all gap scenarios (megaplan/epic), or first vertical slice (adapter + 4 focus-area scenarios) to prove the harness, then expand?
3. Should the surfaced defects (§5) become megaplan tickets now?
4. Actor model for runs: keep deepseek-subagent + claude dispatch; default tier?
