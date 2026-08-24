# Integrated tasklist — unified execution plus Phase B

The two frozen source tasklists are preserved in the merge parents. This merged
record removes duplicate batch numbering while retaining every required outcome.

## Unified execution track

| ID | Deliverable | Gate |
|---|---|---|
| U1 | Relax completion/output normalization for evidence and mixed outputs; migrate schema and read models. | Fresh and migrated DB probes; media-only regression; file-only/mixed completion. |
| U2 | Add one generic `CapabilityTaskHandler` with manifest harvest and media/evidence classification. | Generic-vs-bespoke parity and typed failure evidence. |
| U3 | Route executor/orchestrator SDK invocation through kernel admission, claims, leases, attempts, child dependencies, events, receipts, and terminal state. | At least six representative process runs; zero authoritative `run.json`. |
| U4 | Rewire ledger readers/writers, retaining only a kernel-stamped derived projection if needed. | Production writer census and docs-alignment gate. |
| U5 | Complete docs and empirical verification. | Full suite, CLI census, kernel/event/receipt assertions, oracle review. |

## Phase B track

| ID | Deliverable | Required evidence |
|---|---|---|
| B1 | Digest-pinned generic VibeComfy binding, typed ports, and CPU journey. | Tamper fail-closed, pinned requirements, stable output proof. |
| B2 | Registry fan-out, validators, and one conformance fixture per shipped capability. | Missing prerequisite is named and truthful without code changes. |
| B3 | Leased parent orchestration, deterministic attempt-independent child keys, fenced admission, replay coordinator, checked transitions, and travel/join/edit ports. | Every fence branch; duplicate race; deterministic interleaving with zero duplicates and exactly one parent terminal. |
| B4 | Wan2GP binding and five-gate upgrade/rollback pipeline. | Gates 1–4 CPU-green; shape checks; N+1 accepted then rollback to N. |
| B5 | Sidecar setup journal, signed manifest, Range resume, disk preflight, doctor repair, and availability probes. | Kill/resume, hash mismatch, disk-full, repair, and truthful `doctor setup` path. |
| B6 | Registry-plus-fixture boot-manifest digest and fail-closed startup. | Digest disagreement refusal; completion provenance; frozen receipt shape unchanged. |

## Ordered seams and ownership

1. Resolve committed source-history conflicts and validate the phase surface.
2. Replay live UX/kernel changes, reconciling authority and lifecycle overlaps.
3. Serialize registry/schema/fixture edits and update 20→22 table expectations.
4. Regenerate the stacked-render proof on the final tree; never select either
   historical pixel sample by fiat.
5. Run the combined phase, live-UX, SDK/CLI, bridge, doctor, backup, timeline,
   media, generation, rendering, compileall, and diff gates.

## Stop/record rules

Record `blocked` for unavailable GPU-only prerequisites, `failed` for reproducible
contract violations, `undetermined` for insufficient evidence, `retryable` for an
owned safe retry, and `escalate` for authority/risk outside the integration role.
No task deletes a test merely to make the merge green. Keep safety and integration
refs until the complete combined gate passes; promotion, push, tags, and branch
deletion are separate actions.
