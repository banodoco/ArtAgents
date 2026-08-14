# Adversarial review: Astrid-first sprint plan against unified data model v10

**Review date:** 2026-08-13  
**Normative source:** `unified-data-model-plan-v10-20260813.md` (v10)  
**Plan reviewed:** `astrid-first-sprint-plan-20260813.md` (sprint plan)

## Verdict: NEEDS REVISION

The sprint plan is substantively aligned with v10 and is much closer to executable than a typical first sequencing pass. It preserves the 20-table model, direct run-to-task grouping, task fencing, atomic receipts, byte-hash media identity, whole-document timeline CAS, exactly eight CLI families, the reduced bridge/SDK, and artifact-level removal of old authorities. I found no reintroduction of `run_steps`, `run_step_tasks`, a legacy importer, editor FSA, plan translation, a run-dialect classifier, a parity harness, a cutover ceremony, or compatibility aliases.

It nevertheless needs revision before execution for five reasons:

1. **The plan declares v10 Phase 1 complete too early.** V10 §3 Phase 1 explicitly includes references and shots, but the sprint plan closes the “full v10 §3 Phase 1 gate” in Sprint 3 and does not build `ReferenceRepository` or `ShotRepository` until Sprint 4 (sprint §§2.1, 3 “Sprint 3,” and 3 “Sprint 4”). That is a phase-boundary contradiction, even though the narrower bolded v10 Phase 1 gate does not enumerate those journeys.
2. **A required pre-freeze decision is scheduled after its first consumer.** V10 §7 requires the closed vocabularies to be confirmed before the references/media repositories freeze. Sprint 2 implements `MediaRepository` and relation constraints, while S1-16 assigns the vocabulary deadline to Sprint 4 (sprint §6, S1-16; sprint §3 “Sprint 2”). The plan can otherwise force a schema/repository rework after the Phase 1 claim.
3. **The eight-family completion point is internally inconsistent.** Sprint 5 says it implements exactly eight families and gates on help containing all eight, but Sprint 6 is where `serve`, `doctor`, and `backup` are actually implemented (sprint §§2.1 and 3, Sprints 5–6). This is fixable, but the gate currently cannot distinguish real commands from placeholders.
4. **The compressed and team-size forecasts are not fully reconciled.** The six-sprint low case has no dependency-preserving merged map, and the three-engineer mapping adds up to 11–13 sprints while its headline says 10–12 (sprint §§1.3 and 4.1).
5. **Several acceptance clauses are present as intent but not as explicit command-level proof.** In particular, media mutations do not explicitly require registered events/heads/receipts in their Sprint 2/5 gates, and backup mutation behavior does not explicitly test the blanket v10 §4.1 idempotency/envelope rule. The risk table also omits explicit routing for v10 §6’s “capability writes files directly” and “JSON dumping ground” risks (sprint §§3 and 5).

These are targeted planning defects, not a reason to redesign v10. Applying the concrete fixes in §6 below should make the plan ready to execute.

## 1. Coverage matrix

Status meanings: **OK** = an adequate sprint home and release proof exist; **GAP** = substantially covered but sequencing or acceptance language needs repair; **MISSING** = no sprint home. No requirement is wholly missing.

### 1.1 V10 §5.3 GA acceptance

| V10 item | Sprint/ticket home | Status | Review |
| --- | --- | --- | --- |
| 1. Exactly 20 tables and declared indexes; too-new behavior | S1 work 1–2; S1-01–S1-03; S1-17; S8 migration/catalog rerun | OK | The explicit manifest, extra/missing checks, PRAGMAs, checksum validation, and nonmutating too-new behavior match v10 §§2 and 5.3(1). |
| 2. Real generation/render atomically traverse task, attempt, event, media/location, output, receipt | S3 adapter/completion work and gate; S7–S8 reruns | OK | Sprint 3 names the complete atomic materialization unit and both real adapters, matching v10 §§2.3, 3 Phase 1, and 5.3(2). |
| 3. Synchronous understanding creates run/evidence without task | S3 work, deliverable, gate; S7 dogfood | OK | The no-convenience-task rule and returned run/evidence/media IDs preserve v10 §5.3(3). |
| 4. Direct-child fan-out, dependencies, progress/cancel/retry, no steps | S2 contract; S3 implementation/gate; S7 destructive rerun | OK | Stable ordinals, continuation CAS, direct children, dependency edges, progress and group operations are all named; no step table is allowed. |
| 5. Crash injection and five task races | S1-11; S2 early races; S3 full matrix/crash gate; S7–S8 reruns | OK | All five v10 races are named in Sprint 3, with terminal and output assertions. |
| 6. Editor list/load/save/reload, 409, 422, restart, draft, Range | S1-10/S1-13/S1-14 risk slice; S4 full lane; S7–S8 | OK | Routes, typed errors, draft/poll safety, restart, `GET`/`HEAD`, 206/416 are all covered. |
| 7. Media dedupe, mutation/missing detection, byte identity | S2 media work/gate; S7 failure journeys; S8 suite | **GAP** | Byte identity and failure behavior are strong, but the S2/S5 acceptance language does not explicitly prove event/head/receipt atomicity for `import`, `relocate`, and `relate`; see §3. |
| 8. References/shots exact-media round trip, primary/order constraints | S4 repositories; S5 journeys/gate; S7 | **GAP** | Functional coverage is complete, but it occurs after the plan claims Phase 1 complete, contrary to v10 §3 Phase 1 scope. |
| 9. Online DB + managed-media backup; usable restore; doctor | S6 implementation/gate; S7 restore; S8 artifact | **GAP** | Snapshot, writer lock, validation and atomic activation are covered. Explicit replay/mismatched-key behavior for the mutating backup commands is not stated despite v10 §4.1. |
| 10. Clean install supports local domains with no account/cloud/secret | S5 smoke; S6 clean install; S8 supported-matrix artifact | OK | S8 explicitly exercises editor, project, timeline, media, references, backup and doctor with zero secrets. |
| 11. Removed authorities/families absent from artifact/help; import lint green | S3 and S6 deletion; S5/S6 help/import lint; S8 installed artifact audit | OK | The actual artifact is audited in S8. Sprint 7’s claim that all eleven already pass on an *unpackaged* candidate should be corrected; see §4. |

### 1.2 V10 §5.1 kept invariants

| Kept invariant | Sprint/ticket home | Status | Review |
| --- | --- | --- | --- |
| Task admission | S2 task admission; S3 real adapters | OK | Bounded immutable specs, `spec_hash`, independent fencing and a winner are explicit. |
| Event universality | S1-05; S1 global kernel; S3/S4 repository work | **GAP** | Core/task/timeline/reference/shot events are explicit; media command gates should explicitly require registered ordered events rather than rely on the global definition of done. |
| Task stream | S1-05; S2 admission/gate; S3 association gate | OK | Exactly one same-project stream beginning with `task_created`, with lifecycle/head atomicity, is stated. |
| Atomic receipts | S1-07; S1-08/S1-10; S3 completion/fan-out | **GAP** | Strong for core, timeline, fan-out and completion; media and backup command-level acceptance should inherit it explicitly. |
| Idempotency | S1-06/S1-07 and review checklist; S5 blanket mutation rule | **GAP** | Replay and mismatched canonical bytes are excellent in the kernel. S6 operational mutations lack a named conformance test. |
| Terminal immutability and fencing | S2 lifecycle; S3 five races; S7 rerun | OK | Stale attempts, winning ownership, non-resurrection and terminal retry/cancel are directly asserted. |
| Honest grouping | S2 fan-out contract; S3 run/evidence/fan-out; S7 | OK | Zero-or-many direct children and non-executable runs are preserved. |
| No plan semantics | S1-01/S1-03; S3 deletion/no-step proof; S5 help; S8 audit | OK | Schema, API, code paths, help and artifact are all checked. |
| Timeline CAS | S1-10–S1-12; S4; S7–S8 | OK | Document, registry, event, head and receipt are atomic; stale returns 409 with no mutation. |
| Media identity | S2 media work/gate; S7 | OK | Project-scoped verified-byte SHA-256 is identity; paths/URLs/keys are only locators. |
| Exact associations | S3 task outputs/evidence; S4 references/shots; S5/S7 journeys | OK | Exact media, primary uniqueness, ordering and same-project checks are named. |
| Single writer | S1-04/S1-12; S3 contention; S6 writer-locked backup; S7–S8 | OK | Repositories own semantic writes; direct handler writers, FSA and Supabase are forbidden. |
| File boundary | S3 capability quarantine/manifests; S6 deletion; S7 audit | OK | File-side manifests/diagnostics remain non-authoritative and repository completion materializes truth. |
| No dormant platform | Sprint §1.1 boundaries; S6 removal; S8 artifact/network/dependency audit | OK | Accounts, sync, remote worker, experiments, importer, aliases and plan schema are excluded. |

### 1.3 V10 §2 tables and declared indexes

All table and index coverage points to v10 §2.2 and sprint S1 work items 1–3, specifically S1-01 (exact migration) and S1-03 (explicit `sqlite_master`, FK, CHECK and partial-index manifest), with release reruns in S8. The later sprint named is the first substantive repository exercise, not permission to change the DDL.

| V10 table | First substantive use | Catalog proof | Status |
| --- | --- | --- | --- |
| `schema_migrations` | S1-02 | S1-01/S1-03; S8 | OK |
| `projects` | S1-08 | S1-01/S1-03; S8 | OK |
| `event_streams` | S1-05 | S1-01/S1-03; S8 | OK |
| `events` | S1-05 | S1-01/S1-03; S8 | OK |
| `command_receipts` | S1-07 | S1-01/S1-03; S8 | OK |
| `runs` | S3 run repository | S1-01/S1-03; S8 | OK |
| `evidence_items` | S3 evidence repository | S1-01/S1-03; S8 | OK |
| `tasks` | S2 task admission | S1-01/S1-03; S8 | OK |
| `task_dependencies` | S2 admission; S3 fan-out | S1-01/S1-03; S8 | OK |
| `execution_attempts` | S2 lifecycle | S1-01/S1-03; S8 | OK |
| `task_outputs` | S3 materialization | S1-01/S1-03; S8 | OK |
| `media` | S2 media repository | S1-01/S1-03; S8 | OK |
| `media_locations` | S2 media repository | S1-01/S1-03; S8 | OK |
| `media_relations` | S2 media repository | S1-01/S1-03; S8 | **GAP** — relation vocabulary deadline is currently S4, after this repository consumes it. |
| `timelines` | S1-09/S1-10 | S1-01/S1-03; S8 | OK |
| `shots` | S4 shot repository | S1-01/S1-03; S8 | **GAP** — v10 §3 places this repository in Phase 1, but the sprint plan places it after the S3 Phase 1 closure. |
| `shot_items` | S4 shot repository | S1-01/S1-03; S8 | **GAP** — same phase-order issue as `shots`. |
| `project_references` | S4 reference repository | S1-01/S1-03; S8 | **GAP** — same phase-order issue as references generally. |
| `media_references` | S4/S5 exact-media journey | S1-01/S1-03; S8 | **GAP** — same phase-order issue as references generally. |
| `reference_links` | S4/S5 link journey | S1-01/S1-03; S8 | **GAP** — same phase-order issue as references generally. |

Every named v10 §2.2 index is included in the explicit catalog test. They are exhaustively grouped below by owner to avoid implying that “all indexes” is an unnamed wildcard:

| V10 declared indexes | Sprint proof | Status |
| --- | --- | --- |
| `tasks_run_ordinal`, `tasks_claim_order`, `tasks_project_status`, `tasks_run_status` | S1-01/S1-03; task/run semantics S2–S3; S8 | OK |
| `task_one_primary_result`, `task_outputs_media` | S1-01/S1-03; S3 materialization; S8 | OK |
| `reference_one_primary_canonical`, `reference_canonical_ordinal`, `media_reference_global_unique`, `media_reference_context_unique`, `media_references_media`, `media_references_task` | S1-01/S1-03; S4–S5 constraints; S8 | **GAP** only for the Phase 1 sequencing defect, not catalog coverage. |
| `events_project_changes`, `events_stream_kind_seq`, `events_subject` | S1-01/S1-03/S1-05; S8 | OK |
| `task_dependencies_reverse`, `attempts_lease_expiry` | S1-01/S1-03; S2–S3 lifecycle; S8 | OK |
| `media_project_page`, `media_relations_to`, `media_one_variant_parent` | S1-01/S1-03; S2 media repository; S8 | **GAP** for the unresolved pre-freeze relation vocabulary. |
| `evidence_run_time`, `evidence_task` | S1-01/S1-03; S3 evidence; S8 | OK |
| `shot_items_media` | S1-01/S1-03; S4 shot repository; S8 | **GAP** for Phase 1 sequencing. |
| `references_project_kind`, `reference_links_to` | S1-01/S1-03; S4 reference repository; S8 | **GAP** for Phase 1 sequencing. |

V10 §2.3’s repository-only cross-row constraints are covered by S1 stream/project conformance, S2 same-project acyclic dependencies, winning-attempt and variant checks, S3 full association/evidence/output checks, and S4 reference/shot same-project and canonical-link checks. None is missing, although the S4 subset inherits the Phase 1 ordering gap.

### 1.4 V10 §4 CLI, SDK, bridge and operations surface

| V10 surface | Sprint home | Status | Review |
| --- | --- | --- | --- |
| `projects` family and five commands | S5 | OK | Exact commands and non-authoritative selection are named. |
| `timelines` family, eight commands, nested shots | S5 | OK | CAS/history/diff and nested shot verbs are present; removed migration/sync/audit/repair verbs are absent. |
| `media` family, six commands, nested references | S2 service; S5 CLI | OK | Files/folders only, exact-media reference verbs and no semantic import are explicit. |
| `tasks` family, six commands | S5 | OK | Claim/start/heartbeat remain internal; no plan control leaks. |
| `runs` family, five commands | S3 service; S5 CLI | OK | Evidence and child progress are folded into runs; no step commands. |
| `serve` | S6 | **GAP** | Behavior is correct, but Sprint 5’s “all eight implemented/help-complete” gate precedes implementation. |
| `doctor` | S6 | **GAP** | Exact read-only checks and no repair language are correct; same S5/S6 completion-point inconsistency. |
| `backup create/restore` | S6 | **GAP** | Correct scope and restore safety; add explicit idempotency/envelope acceptance and reconcile the S5 family gate. |
| Reduced SDK | S5, with operational services completed S6 | OK | Lazy discovery, typed invocation/results/errors/receipts and removed raw/legacy seams match v10 §4.2. |
| Frozen bridge | S1 thin slice; S4 full; S6/S8 packaged reruns | OK | Exact route/payload/error/Range and draft-safety coverage is present without a parity harness. |
| Secrets rules | S6; S8 artifact/network audit | OK | Zero-secret core, explicit→environment→keychain order, no scavenging and allowlisted child environment are named. |

### 1.5 V10 §3 phases and §1 cut list

| V10 phase | Sprint mapping | Status | Review |
| --- | --- | --- | --- |
| Phase 1 — core | S1–S3, except references/shots in S4 | **GAP** | The S3 gate covers the bolded Phase 1 proof, but v10 §3’s Phase 1 build scope explicitly includes references and shots. The plan must move them or stop claiming Phase 1 closure in S3. |
| Phase 2 — editor and essential CLI/SDK | S4–S6 | OK | Full bridge, SDK/CLI, serve, operations, clean install, writer removal and zero secrets are covered by the S6 gate. |
| Phase 3 — dogfood and ship | S7–S8 | OK | Fresh-only dogfood, destructive tests, artifact audit and the actual packaged GA matrix match v10. |

Every v10 §1 item marked CUT is accounted for by a combination of the sprint §1.1/§1.4 boundary, S1-01/S1-03 forbidden-schema manifest, S1-15 fallback removal, S3 replacement-path deletion, S5 exact help/API, S6 module/fixture/dependency/FSA/Supabase removal and import lint, and S8 installed-file/import/entry-point/help/dependency/network audit:

| V10 §1 CUT group (all exact mechanisms named) | Sprint proof | Status |
| --- | --- | --- |
| Multi-source/semantic importer; Stage G; project/source/timeline manifest, JSONL, sidecar, registry/assets and `.import_idem_*` import | S1-01/S1-15; S3/S6 deletion; S8 audit; only S2/S5 `media import` remains | OK |
| Both old `run.json` dialects; run/audit JSONL; dialect classifier; audit/timeline chain translation; hash-chain fixtures | S3 deletion; S6 fixture/module removal; S8 artifact audit | OK |
| `bootstrap inspect/import/verify`, `timelines migrate-events`, flip markers, parity reports, authority census, five-lifecycle continuity harness, exact timing/header pins, golden corpus and deep-integration scenario | S5 exact surface; S6 removal; S8 help/artifact audit | OK |
| Editor FSA writer and authority switching/fallback | S1-15; S4 explicit no-fallback; S6 deletion/import lint; S8 | OK |
| 553-test classification, importer-only and task/session/thread layout fixtures, teardown runtime trace pack | Sprint §1.1; S3 selective new tests; S6 fixture removal | OK |
| Nine-stage 0/A–I program | Sprint §§2–3 use only v10’s three phase gates | OK |
| `run_steps`, `run_step_tasks`, `Step`, `TaskPlan`, plan/group/repeat/`for_each`/supersede/cursor/next/ack/skip/hooks | S1-01/S1-03; S3 no-step and deletion proof; S5 API/help; S8 schema/artifact audit | OK |
| Project/source, task-plan, thread/session, lease/current-run/inbox/variant authorities | S3 replacement deletion; S6 module/fixture removal; S8 audit | OK |
| Supabase domain authority, hosted worker, RunPod, publication, cloud sync and experiments from local GA | Sprint §§1.1/1.4; S3/S6 removal; S8 network/dependency/schema audit | OK |
| V9 23-family CLI, standalone folded families, compatibility aliases/deprecations, old SDK raw seams and storage adapters | S5 exact eight-family help and reduced SDK; S6 removal; S8 installed help/entry-point audit | OK |
| Backup preservation manifest/catalog/choreography; generic doctor/repair catalog; secret scavenging | S6 exact reduced implementations; S8 artifact test | OK |
| Old disposition-matrix program and compatibility program | Sprint §1.1 new-only posture; S6/S8 removal | OK |

The kept/simplified exceptions are also preserved: media-byte import (S2/S5), current bridge/provider behavior (S1/S4), task races and proven byte/capability contracts (S2–S3), references/shots (S4–S5), file-side package manifests and diagnostics (S3), and reduced backup/doctor/secrets (S6). The sprint plan introduces no ungrounded product feature. Its team variants, gate scripts, reserve sprints and release ownership are delivery mechanics rather than scope growth.

## 2. Contradictions

| Sprint-plan location | V10 rule violated | Severity | Required fix |
| --- | --- | --- | --- |
| Sprint §§2.1 and 3, “Sprint 3” gate says the **full v10 §3 Phase 1 gate** closes; Sprint 4 first implements references/shots | V10 §3 Phase 1 build scope includes “media storage, references, and shots” before Phase 2 | **High** | Move reference/shot repositories and their §2.3 constraints into S3, possibly leaving editor/CLI journeys for S4–S5; or rename S3 as “Phase 1 execution gate” and do not claim full Phase 1 completion until those repositories land. The former is more faithful. |
| Sprint §6 S1-16 assigns the vocabulary deadline to Sprint 4; Sprint 2 implements `media_relations` kinds/constraints | V10 §7 choice 3 must close before references/**media** repositories freeze | **High** | Close media relation kinds before S2 begins. Close reference kinds/roles/links and evidence kinds no later than their repository start. Record exact enum decisions in S1-16 or split the ticket into dated decisions. |

No other substantive v10 contradiction was found. In particular, the phrase “editor continuity lane” in the sprint executive summary is unfortunate but its actual S1/S4 work is limited to the current provider/persistence/draft/poll tests, bridge contracts and the small v10 end-to-end smoke; it does **not** recreate v9’s parity ceremony. Rename it “editor contract lane” to remove ambiguity, but do not treat this as architectural drift.

## 3. Weak acceptance criteria

| Sprint ticket/work | V10 invariant | Gap and strengthening needed |
| --- | --- | --- |
| Sprint 2 `MediaRepository` and media-service work; Sprint 5 `media import|verify|relocate|relate` | V10 §§2.3 and 5.1 Event universality, Atomic receipts, Idempotency | The plan proves SHA-256 identity, placement safety, dedupe and location detection, but does not explicitly say each meaningful media mutation appends registered ordered event(s), advances the correct project/stream head, and commits projection/location/relation plus a complete receipt atomically. Add replay and mismatched-key tests for import, relocate and relate. |
| Sprint 6 `backup create/restore` | V10 §4.1: every CLI/SDK mutation accepts or generates/returns an idempotency key and uses the new stable machine envelope | Writer locking and restore safety are strong, but neither the work item nor gate states replay/mismatch/envelope behavior for these mutating commands. Add an explicit operational-command conformance test, or amend v10 if backup is intentionally outside project receipts; the sprint plan may not silently choose an exception. |
| Sprint 6 secret enforcement acceptance | V10 §4.3 secret non-persistence/non-propagation | The work item names all forbidden sinks, but the Sprint 6 gate says only “zero secrets.” Add artifact tests proving secrets do not enter task specs, events, receipts, logs or backups and that only an explicitly allowlisted capability environment reaches children. |
| Sprint 4 reference/shot gate | V10 §§2.3, 3 Phase 1 and 5.1 Exact associations | The constraint criteria themselves are adequate; the weakness is their position after Phase 1. Moving them to S3 should retain same-project, exact-media, primary, ordering, contextual-task, symmetric-link and receipt/event assertions, not reduce them to CRUD smoke. |
| Sprint 4 reference/shot mutations and Sprint 5 editorial journeys | V10 §§2.3 and 5.1 Atomic receipts, Idempotency, Exact associations | The plan names receipt/event behavior and round trips, but not statement-boundary/replay proof for primary-canonical replacement, association/link, and shot reorder. Add old-or-complete event/head/association/receipt assertions plus mismatched-key rejection for representative commands. |

The critical exemplars requested by the brief are otherwise faithful: S1-10 exactly states document + registry + event + head + receipt in one CAS unit and stale mutation-free rejection; S2/S3 and the five-race matrix enforce terminal immutability and attempt fencing; media explicitly uses verified-byte SHA-256 and rejects path identity; S1-07 tests identical replay and mismatched canonical bytes; and S1-04 plus S1-12/S3/S7 enforce a single writer.

## 4. Internal consistency findings

### Dependencies and gates

1. **Phase closure precedes a named Phase 1 dependency.** References/shots are S4 even though S3 closes Phase 1. This is the primary sequencing error (v10 §3; sprint Sprints 3–4).
2. **S1 and S2 both claim the fan-out contract freeze.** Sprint 1 work item 11 and S1-16 require the fan-out maximum/continuation envelope to close before Sprint 2; Sprint 2 then says “Finalize” it and freezes the receipt shape. Make S1 the decision/freeze and S2 the conformance/implementation point, or explicitly move the gate. A dependency cannot be both fixed input and in-flight design.
3. **Sprint 5’s eight-family gate precedes three implementations.** Sprint 5 says it implements all eight and that help contains exactly eight, while Sprint 6 implements `serve`, `backup`, and `doctor`. Define S5 as five completed domain families plus reserved/hidden operational entry points, or move the exact-eight executable/help gate to S6. Empty placeholders should not satisfy it.
4. **Sprint 7 cannot fully prove artifact absence on an unpackaged candidate.** Sprint 7’s gate says all eleven GA items pass against an unpackaged release candidate, while v10 §5.3(11), sprint §2.3, and Sprint 8 correctly require installed artifact/help proof. Say “items 1–10 plus provisional source/build proof for item 11” in S7, with final item 11 only in S8.

### Team sizing and sprint-count reconciliation

- The **base eight-sprint case is coherent**: five to six dependable PW per sprint yields 40–48 PW, spanning the 32–46 PW engineering range while reserving integration and release capacity (sprint §1.3).
- The **nine/ten-sprint high case is coherent** as variance reserve, provided S9/S10 remain defect-triggered and do not become feature buckets (sprint §§2.1, 3 and 5).
- The **six-sprint low case is asserted but not scheduled**. S2→S3, S4→S5 and especially S6→S7 contain real producer/consumer gates; “overlap aggressively” does not show which gates remain intact. Add a six-sprint merged map, with entry/exit criteria, or present six as an estimate lower bound rather than an executable forecast (sprint §1.3).
- The **three-engineer arithmetic conflicts with its headline**. The practical mapping in sprint §4.1 totals 11–13 sprints: core 2 + executor/media 2 + Phase 1 integration 1–2 + bridge/references/shots 2 + CLI/SDK 1–2 + productization 1 + dogfood/release 2. Change the forecast from 10–12 to 11–13, or show the overlap that removes one sprint from both ends.
- The solo 20–26-sprint range is plausible for 32–46 focused PW plus integration/release overhead and is honest that base “sprints” become multi-iteration milestones (sprint §4.2).

### Risk and buffer coverage

The buffer policy properly routes event/receipt, editor, media placement, executor race, run grouping, packaging, external-local backup and scope-growth risks (sprint §5) into ordinary sprint slack, S8, S9 or S10 without weakening gates. Two v10 §6 risks lack an explicit row:

- **Old capability writes project files directly.** Sprint 3’s quarantine/manifest boundary and S7 hidden-tool audit mitigate it, but the buffer table has no early signal or destination. Route integration failures to S3 and late materialization violations to S9.
- **JSON fields become dumping grounds.** S1-06 payload limits and S5 typed result/read models mitigate it, but no risk row defines the signal (unbounded payloads or handler-specific JSON queries), correction, or slip destination. Route ordinary correction to the owning repository sprint and systemic late correction to S9.

SQLite contention is exercised in S1/S3/S7 and can reasonably route to S9, but the event/receipt risk row should name it or a dedicated row should do so. With those additions, the reserves cover all v10 §6 build risks. The policy correctly refuses to spend buffer on deferred scope.

The reserve ownership itself also needs one clarification. Sprint 9 names event/receipt, executor/fencing, media atomicity and contention, while Sprint 10 names editor/platform/package. A late reference/shot exact-association defect, timeline repository defect, or backup/restore atomicity defect falls between those labels even though each is a core repository invariant. Expand S9 to cover any material repository/atomicity failure; keep S10 limited to bridge/platform/package failures (sprint §§3 “Sprint 9–10” and 5; v10 §§2.3 and 6).

## 5. Groundedness and cut-list conclusion

No sprint deliverable is an ungrounded v9 feature. Forward migrations are explicitly for unshipped application layouts, not legacy import. The current editor tests verify the live bridge contract, not old/new parity. Developer package/manifest tools remain outside the product CLI promise. Contingency sprints repair existing gates only. The plan’s only problematic extra language is “editor continuity lane,” which should be renamed because v10 §§1 and 3 deliberately abolished continuity ceremony; the scheduled tests themselves are legitimate.

Conversely, every v10 CUT is either affirmatively absent in S1’s catalog/API constraints, deleted with its replacement in S3/S6, or rejected in the S8 installed artifact/help/import audit. The review finds no quiet restoration of plan/step/group/repeat/`for_each`, old run dialects, semantic import, parity, FSA, Supabase, aliases, cutover mechanics, or a ninth CLI family.

## 6. Concrete fixes required

1. **Repair the Phase 1 map.** Move `ReferenceRepository` and `ShotRepository`, including all v10 §2.3 same-project/exact-media/primary/order/link checks, into Sprint 3 before its Phase 1 closure. If capacity makes that impossible, stop calling S3 the full Phase 1 close and move the formal phase gate to S4; update §§2.1, 2.3 and the S3/S4 gates consistently.
2. **Split and advance S1-16 decisions.** Require media relation kinds before S2; evidence kinds before S3; reference kinds/roles/links before reference work begins; and retain the platform-matrix deadline before the S6 Phase 2 exit. Name the decided values or link a required decision artifact.
3. **Make the fan-out freeze unambiguous.** S1 fixes the maximum, continuation envelope and receipt linkage; S2 validates/implements against that frozen contract; S3 completes transactional fan-out. Remove “finalize/freeze” language from S2 unless S1’s gate is correspondingly changed.
4. **Reconcile the CLI gates.** State that S5 completes the five domain families (`projects`, `timelines`, `media`, `tasks`, `runs`) and shared SDK/envelope, while S6 completes `serve`, `doctor`, `backup` and only then gates executable help at exactly eight. Do not count nonfunctional placeholders.
5. **Strengthen media and editorial command acceptance.** Add tests for registered event order, stream/project heads, atomic projection/location/relation/association plus receipt, identical replay, mismatched-key rejection and representative statement-boundary failure for media import/relocate/relate, reference primary/associate/link, and shot reorder.
6. **Resolve operational idempotency explicitly.** Add idempotency-key, replay/mismatch and stable-envelope criteria for `backup create/restore`, or record and approve a normative v10 amendment defining why those operations are outside §4.1. Also make secret-sink and allowlisted-child tests part of the S6 gate.
7. **Correct pre-release acceptance wording.** Change S7 from “all eleven” on an unpackaged candidate to items 1–10 plus provisional source/build proof for item 11; reserve final artifact/help/import proof for S8.
8. **Make the forecast arithmetic executable.** Add a dependency-preserving six-sprint compressed map or demote six from a forecast to a theoretical lower bound. Correct the three-engineer headline to 11–13 sprints unless explicit overlap proves 10–12.
9. **Complete the risk and reserve tables.** Add rows for direct capability file writes and JSON dumping grounds, and explicitly route systemic contention. Expand S9 to any material repository/atomicity invariant—including timeline, references, shots and backup/restore—and preserve S10 as editor/platform/package only.
10. **Remove migration-era terminology.** Rename “editor continuity lane” to “editor contract/provider lane” everywhere; retain only the current provider/persistence/draft/poll tests, bridge contract tests and small v10 end-to-end smoke already scheduled.

After these edits, the sprint plan should be re-reviewed only for cross-reference consistency; no architecture redesign is indicated.
