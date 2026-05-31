# M2 — Implement the classified integrity/evidence check battery

Companion: `docs/megaplan/epics/astrid-sisypy/design.md` §2 (classified checks) and the FROZEN `tests/agentic/ADAPTER.md` from M1 (the contract — obey it exactly). Read both.

## Outcome
The integrity/evidence checks from design §2 / ADAPTER.md implemented in the M1 adapter as deterministic Python over the FROZEN evidence pack, correctly classified UNIVERSAL / CONDITIONAL / SCENARIO-SPECIFIC, each with explicit `na`-skip semantics, and each unit-tested against crafted valid AND tampered evidence packs.

## Scope (IN)
- **Universal checks** (run on every pack via `project_universal_checks()`):
  - U1 claim-vs-evidence; U2 canonical-surface enforcement; U3 chain-integrity — for EACH chained log present, call ITS verifier (timeline→`LocalFsBackend.verify_chain`, task-run→`task.events.verify_chain`, audit→`verify_audit_ledger`), `na` if that log absent; U4 no-cross-project-leak; U5 auditability; U6 deliverable hygiene.
- **Conditional checks** (apply only when the triggering artifact/verb is present; else `na`):
  - C1 head/sidecar consistency (timeline head.json present); C2 artifact-provenance — verify each `produces` path exists AND its hash matches the `produces_check_passed.cas_sha256` event (NOT run.json); C3 no-mutation-on-read (read/audit-verb scenarios only); C4 projection-fidelity — only against a frozen read-only assembly.json snapshot, else `na`.
- **Scenario-specific checks** (declared per scenario, not auto-applied):
  - S1 append-not-rewrite with an explicit erasure/repair EXEMPTION (must NOT fire on a legitimate erasure that rewrites payloads + downstream hashes); S2 idempotent-reattach (reattach scenarios only).
- **Result shape** exactly per ADAPTER.md: `{id, status: pass|fail|na, evidence_refs, detail}`; `na` scored as pass.
- **Unit tests**: for each check, a crafted evidence-pack fixture proving it (a) PASSES on a valid pack, (b) FAILS on a tampered/inconsistent pack (e.g. flipped hash → chain-integrity fail; orphan produces path → artifact-provenance fail; extra event after read verb → no-mutation-on-read fail; erasure pack → append-not-rewrite stays PASS via exemption), and (c) returns `na` when its trigger is absent.
- Wire the universal+conditional checks into the runner so every scenario's pack is scored; surface results in the summary.

## Locked decisions
- Checks read FROZEN evidence only — never live repo state.
- Each verifier is invoked exactly as ADAPTER.md specifies (library call or CLI) — do not re-derive a hash chain by hand if a verifier exists.
- Classification is fixed by design §2 / ADAPTER.md; if implementation reveals a check is mis-classified, update ADAPTER.md additively and note it (do not silently reclassify).

## Open questions for the planner
- Exact tamper fixtures: smallest crafted pack per check that deterministically exercises pass/fail/na.
- For U1 claim-vs-evidence: the claim-extraction patterns (reuse the legacy `auditor.py` `_CLAIM_PATTERNS` logic as a starting point; cite it).
- For C2: how to resolve a `produces` path captured in the pack back to its `cas_sha256` event (path→event join).

## Constraints
- Whole battery must run fast (< a few seconds on a small pack) and be total-functional (missing artifact → `na`, never crash).
- No false positives on legitimate operations — especially the S1 erasure exemption and C4 skip-when-no-snapshot.

## Done criteria
- All checks implemented and classified per ADAPTER.md.
- Per-check unit tests pass, covering valid + tampered + na cases.
- The M1 `_smoke` scenario now also reports a checks block; a second fixture scenario with a deliberately tampered primed pack shows the relevant check FAILING.

## Touchpoints
- `tests/agentic/adapter.py` (checks), `tests/agentic/checks/` (if split out), `tests/agentic/tests/` fixtures, `tests/agentic/ADAPTER.md` (additive updates only). Read-only: the three verifier modules.

## Anti-scope
- Do NOT migrate the 29 scenarios (M3) or build net-new scenarios (M4/M5).
- Do NOT decommission the legacy harness.
- Do NOT modify `astrid/` production code or Sisypy.
- Do NOT change M1's ADAPTER.md contract non-additively.
