# Agent Goal — megado run: Phase B (catalog population + executor bindings + orchestrators)

**North Star:** [North Star](./northstar.md) — this run turns the Phase-A foundation into the working product surface: real executor bindings, the full capability catalog, reliable multi-task orchestration, and self-serve model setup.

## Objective
Implement Phase B per **doc 31-forward-map.md** (workstreams B-1 through B-6) against the build contract **docs-corpus/27-build-spec.md**, on branch `phase-b` of this repo:
- **B-1** Generic VibeComfy executor binding: template-digest pinning, typed ports, generic handler running declared Comfy workflows.
- **B-2** Capability fan-out: registry entries + input validators + conformance fixtures for ~15 remaining capabilities (qwen family, z_image+i2i, upscale, flux_klein, video_enhance, animate_character, inpaint/annotated).
- **B-3** Orchestrator children: leased parents, attempt-independent child keys, receipted admission via executor gate, replay coordinator, checked transition table + deterministic interleaving suite; travel/join/edit families ported.
- **B-4** Wan2GP binding + five-gate upgrade pipeline + rollback drill (N+1 accepted → roll back to N proven).
- **B-5** Model acquisition: setup journal/state machine, signed version-pinned manifest, tier discovery, disk preflight, doctor repair, truthful capability advertisement.
- **B-6** Conformance completion: fixture per shipped capability; conformance-hash stamped into boot manifest; startup fails closed on registry-digest disagreement.

## Authoritative inputs
- docs-corpus/27-build-spec.md (contract), 31-forward-map.md (this phase's plan), 22-codex-roadmap.md, 16-capability-map.md (capability inventory), grok/worker-wgp-report.md (Wan mechanics), 28/29/30.
- Constitution: docs-corpus/15/24/25 + grok/second-opinion-decisions.md.

## Non-goals / blocked
- Real GPU model generation on THIS machine (CPU-only box): generation journeys validate via CPU-mode/tiny-model or deterministic stubs; live CUDA validation is `blocked` (external prerequisite) and must not silently widen scope.
- reigh-app changes (Phase C). SSE. Remote workers. Multi-user anything.

## Authorization
Mutate only this repo on branch `phase-b`; commit at batch checkpoints; push `phase-b` to origin at phase completion. Never merge to main.

## Model policy (USER-PINNED, ALL CLASSES)
Planner = Explorer = Normal executor = Oracle/reviewer = `[XHARD]` = **stealth/ox-alpha**. No switches without owner approval.

## Huge-run determination
YES — human-equivalent estimate >2 weeks (doc 30). Cumulative big-batch review boundaries predeclared: after B-2 completion, after B-3 completion, after B-5 completion. Rationale: schema/catalog seam (B-2), distributed-systems seam (B-3), upstream-dependency seam (B-4/B-5).

## Done criteria
1. B-1: one non-Wan capability end-to-end through the real VibeComfy subprocess binding (deterministic workflow acceptable on CPU) with digest pinning verified.
2. B-2: all listed capabilities registered with validators + fixtures green.
3. B-3: travel/join/edit children admitted via gated R1 with deterministic keys; interleaving suite proves zero duplicates + exactly-one parent-terminal across adversary schedules.
4. B-4: five-gate pipeline runs mechanically; rollback drill passes.
5. B-5: setup journal state machine green incl. crash-mid-download resume; doctor repairs corrupt artifact.
6. Full test suite green on `phase-b` HEAD minus pre-existing baseline failures (the two documented collection errors).

## Validation commands
`python3 -m pytest tests/v10 tests/integrations/reigh tests/packs/shots -x -q` per batch; full `python3 -m pytest tests -q` at phase exit.

## Stop conditions
blocked (no GPU for a criterion that cannot be validated otherwise — record and continue other work), failed (after one rework loop), escalate.
