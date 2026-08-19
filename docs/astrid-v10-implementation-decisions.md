# Astrid v10 Implementation Decisions

**Artifact status:** frozen for milestone m1 (Sprint 1) execution.

**Normative sources:** `unified-data-model-plan-v10-20260813.md` (v10, §2/§4.2/§5/§7), `astrid-first-sprint-plan-20260813.md` (Sprint 1, ticket S1-16), `astrid-first-sprint-plan-review-20260813.md` (concrete fixes 2/3/10), and the m1 plan `m1-event-core-and-20260814-2340`.

**Purpose:** record every value, layout, vocabulary, owner, and deadline that later milestones consume, and record the three settled decisions (SD1–SD3) that resolve the m1 plan's open questions. Reopening any frozen value below requires an explicit v10 amendment or replan; implementation shortcuts that contradict a frozen value are anchor conflicts.

---

## 1. SD1 — Exact v10 DDL preserved; timeline identity is projected, never stored

**Decision:** The normative v10 DDL (§2.2) is preserved byte-for-semantic-content. In particular, the frozen `timelines` table has **no** `slug`, `timeline_ulid`, `is_default`, or event-hash convenience columns, and no migration, repository, or test adds one.

**Consequence for bridge-required timeline identity:**

- Immutable `slug` and lowercase 26-character ULID address metadata are persisted **only** inside the `timeline.created` event payload (canonical envelope, see SD2).
- The project's default timeline ID is persisted **only** inside `projects.settings_json`, repository-owned.
- Repository read models resolve UUID, ULID, and slug addresses transactionally from those two sources. JSON is a read-model input, never a second write authority: no supported write route accepts projected slug/ULID/default values as an authority (NSA-3).

**Escalation path:** any future need for convenience columns is an explicit v10 amendment/replan, not an implementation shortcut (m1 plan §Overview; v10 §5.1 "Exact associations"/"Registered vocabulary").

## 2. SD2 — Hash-chained events via a canonical payload integrity envelope

**Decision:** The frozen v10 `events` table has no `previous_event_hash`/`event_hash` columns. Hash chaining is represented inside `payload_json` as a canonical integrity envelope:

```json
{
  "data": { "...": "domain fields only" },
  "_integrity": {
    "previous_event_hash": "<sha256 hex of the immediately preceding event's canonical payload_json, or null at genesis>",
    "event_hash": "<sha256 hex of this event's canonical payload_json>"
  }
}
```

**Rules:**

- Domain data lives under `data`; integrity metadata lives under `_integrity`. The envelope keeps the exact v10 DDL while satisfying the North Star's hash-chained-events requirement.
- The chain must be proven by an **executable genesis-to-head verification gate** (recompute every link from the first event to the stream head, fail on tampering of either domain data or integrity fields). Presence of the fields alone is not proof (NSA-2).
- `payload_json` remains subject to the existing `json_valid(payload_json)` CHECK; repository read models unwrap `data` and never treat `_integrity` as domain content.

## 3. SD3 — In-tree provider-contract client is the m1 bridge acceptance substitute

**Decision:** The real TypeScript `AstridBridgeDataProvider` editor tree is absent from this checkout. m1 uses an in-tree, field-for-field provider-contract HTTP client as the **blocking automated substitute** for the bridge acceptance lane.

> **Superseded observation (m4):** the m1 "editor checkout absent" statement is
> replaced by the m4 inspection record in §14. m4 inspects the external
> `banodoco/reigh-app` repository at pinned commit
> `bc2d8b0327c1c7dbdcd7b7445440d8ca180dd677` and records the observed
> provider/contract contradictions there, with a reporting-only disposition.
> Nothing in m4 changes the frozen Astrid bridge contract or adds compatibility
> behavior (SD1).

**Limits (NSA-1):**

- The substitute exercises the same frozen HTTP wire contract (`docs/contracts/astrid-bridge-v10.md`) without claiming browser/provider-source parity.
- The actual out-of-tree TypeScript `AstridBridgeDataProvider` suite is a **hard named follow-up** (see §12). S1 must not be declared complete or described as editor-source parity until the human acceptance decision records that rerun (or an explicit recorded exception).

## 4. Schema-pack contract — the 11-field `schema-pack.yaml`

**Decision:** Schema packs use a distinct `schema-pack.yaml` file — **not** the capability-pack `pack.yaml` — with exactly these 11 snake_case top-level fields:

| # | Field | Shape | m1 rule |
|---|-------|-------|---------|
| 1 | `id` | string | unique pack id (e.g. `timeline`) |
| 2 | `version` | positive integer | independent forward-only pack versioning |
| 3 | `depends_on` | list of strings | only the grammar `<pack> >= <positive integer>`; all three shipped packs depend only on `core >= 1` |
| 4 | `migrations` | list of descriptors | each descriptor has `version`, `name`, `path`, and owned tables, so catalog tests derive ownership without parsing SQL |
| 5 | `stream_types` | list of dotted names | namespaced, registry-validated |
| 6 | `event_kinds` | list of dotted names | namespaced, registry-validated (e.g. `timeline.saved`) |
| 7 | `command_kinds` | list of dotted names | namespaced, registry-validated (e.g. `timeline.save`) |
| 8 | `repositories` | list | pack repository declarations (kernel-writer backed) |
| 9 | `conformance` | list | pack conformance-kit dimensions |
| 10 | `cli_mounts` | mapping | explicit in-tree CLI mounts |
| 11 | `bridge_mounts` | list | explicit bridge mounts |

**Composition rule:** startup registers only the three in-tree schema packs via one explicit `register_pack()` call; there is no dynamic discovery, install/uninstall, or capability-pack loader reuse (v10 §2 "Boundary now, loader later"). Parsing reuses only `load_manifest_mapping()` for YAML loading; everything else is strict validation.

## 5. Managed media layout

**Decision (frozen before m2 media fixtures):**

- Managed data root: `${ASTRID_PROJECTS_ROOT}/.astrid/`.
- Database: `${ASTRID_PROJECTS_ROOT}/.astrid/astrid.sqlite3`.
- Managed media (content-addressed): `${ASTRID_PROJECTS_ROOT}/.astrid/media/sha256/<first2>/<next2>/<digest>`, where `<digest>` is the lowercase SHA-256 hex of the verified bytes and `<first2>`/`<next2>` are its first four hex characters split into two pairs.
- Staging: `${ASTRID_PROJECTS_ROOT}/.astrid/media/.staging/<txn_id>` (per-transaction staging, quarantined until publish).
- **Copy-to-managed is the default.** Reference-in-place is explicit and recorded as `media_locations.realm = 'external_local'`; it never becomes a default and never bypasses the repository transaction.
- Media ingestion behavior itself remains out of m1 scope; only the layout contract is frozen here.

## 6. Fan-out maximum and continuation envelope

**Decision (contract recorded in m1; fan-out is not implemented in m1):**

- Maximum **256 new children per command** (one transaction).
- A fan-out command creates one run plus directly created child `task_id`s and any evidence IDs; the receipt returns the `run_id`, ordered task IDs, and evidence IDs (v10 §2.1).
- Larger fan-out is submitted in receipt-linked continuation chunks to the same run. Each continuation envelope carries:
  - `run_id` — the run being extended;
  - `expected_version` — the expected run-stream head (CAS);
  - `start_ordinal` — first new `run_ordinal` to allocate;
  - `tasks` — child task specs;
  - `dependencies` — execution edges.
- The command returns the allocated ordinal range and the next expected version. Concurrent or replayed chunks can neither collide nor extend a terminal run (v10 §2.1).
- m1 records this contract only; Sprint 2 validates/implements against it, Sprint 3 completes transactional fan-out (review fix 3).

## 7. Locked DDL vocabularies (recorded verbatim, not reopened)

The following DDL-baked enums are frozen exactly as transcribed in the normative v10 §2.2 DDL. Changing any value requires a v10 amendment (review fix 2: media relation kinds closed before m2; reference kinds/roles/links closed before reference work).

- `events.actor_kind` — `('local','system','executor')`
- `runs.status` — `('running','succeeded','failed','cancelled')`
- `tasks.status` — `('queued','blocked','running','succeeded','failed','cancelled')`
- `task_dependencies.kind` — `('hard','soft')`
- `execution_attempts.status` — `('claimed','running','succeeded','failed','cancelled','expired')`
- `media.media_kind` — `('image','video','audio','text','document','data','other')`
- `media_locations.realm` — `('managed_local','external_local','remote')`
- `media_relations.kind` — `('derived_from','variant_of','uses_as_input','mask_for','audio_for')`
- `project_references.kind` — `('character','place','object','clothing','other')`
- `media_references.role` — `('canonical','used_as_input','depicts','inspired_by')`
- `reference_links.kind` — `('belongs_to','wears','located_in','associated_with','related_to')`

## 8. Proposed evidence kinds

**Decision:** evidence kinds are proposed as `observation`, `measurement`, `validation`, `decision`, and `error`. This is the m1 proposal; `evidence_items.kind` has no DDL CHECK and the list closes in Sprint 3 before evidence repositories freeze.

**m3 closure:** the list is now **closed** exactly as `observation`, `measurement`, `validation`, `decision`, and `error` (m3 plan step 1/4; no DDL change — `evidence_items.kind` remains an open column enforced by the kernel `EvidenceRepository`).

## 9. Release-owner deadline for the platform matrix

**Decision:**

- **Owner:** the named **Astrid Release Owner** role.
- **Deadline:** end of **Sprint 5** (before Sprint 6 Phase 2 work begins).
- Assigning an individual to the role is an organizational follow-up; the artifact names the role and deadline, it does not invent a person in code (m1 assumption).

## 10. Error envelopes — CLI/SDK proposal vs frozen bridge envelopes

**Decision:**

- The **bridge** (HTTP) error envelopes are immutable and frozen in `docs/contracts/astrid-bridge-v10.md`: `{"error": "<code>", "detail": "<string>"}` plus status-specific fields (`config_version` on 409, `issues[]` on 422). The bridge never leaks internal receipts.
- The **CLI/SDK** stable error envelope is a **proposal** in this milestone and freezes in m4. It is a separate document (`docs/contracts/error-model.md` lineage) and must not be conflated with the bridge envelope. No CLI/SDK envelope value is frozen by this artifact beyond the m4-freeze commitment.

## 11. Hard follow-up — the real editor suite

- The actual out-of-tree TypeScript `AstridBridgeDataProvider` suite must be rerun against the repository bridge when that editor checkout becomes available (v10 §5.3 criterion 15, info priority).
- This is a **hard named follow-up** owned by a human trigger. The in-tree substitute (SD3) does not satisfy it and no runtime code invents browser/provider-source parity.
- S1 completion and the "editor-source parity" description both remain gated on the human acceptance decision (NSA-1).
- **m4 supersession:** the m4 external-gate disposition (§14) supersedes the "when that editor checkout becomes available" framing for m4: the external commit is now pinned and inspected, the contradictions are recorded, and the lane is reporting-only retained evidence. The human-triggered rerun requirement remains a hard named follow-up.

## 12. m3 closed contracts — soft archive, context rule, link symmetry, and aggregate streams

**Status:** closed in milestone m3 (Sprint 3) and recorded here because repositories, events, and conformance specs consume these values; none of them changes frozen DDL vocabulary (section 7 remains verbatim).

- **Soft archive (SD1-m3).** Archiving a reference is non-cascading: `project_references.archived_at` is set and one receipt-backed event is emitted, while associations (`media_references`), links (`reference_links`), events, and media bytes all remain. Default lists hide archived rows; direct historical lookup (`show` with history allowed, explicit inclusive lists) still returns them; new active mutations against an archived reference fail closed.
- **Producing-task context rule.** Only the DDL-approved roles `used_as_input` and `inspired_by` may carry a `context_task_id`, and `used_as_input` requires one. Every context task must share the reference's project **and** must have produced the exact associated media through `task_outputs` — same-project exact-media provenance, not a free-form task reference.
- **Link symmetry.** Only `related_to` is symmetric and stored in canonical `min(from_reference_id)`/`max(to_reference_id)` order so reversed retries converge on the same row; `belongs_to`, `wears`, `located_in`, and `associated_with` remain directional (their names describe the direction).
- **Pack aggregate streams.** References and shots use their own registered aggregate stream types — `reference.reference` and `shot.shot` — with subject types `reference` and `shot`, so events can identify reference/shot subjects without placing pack vocabulary in kernel DDL (v10 §2.3 law 5; m3 plan step 1). Each pack's executable repository (`ReferenceRepository`, `ShotRepository`) receives only the caller's kernel `UnitOfWork`.
- **Run continuation and evidence vocabulary.** `core.run.continue` / `core.run.continued` are the receipt-linked continuation command/event pair (section 6 contract, now implemented); `core.evidence.recorded` is the kernel evidence event appended on the run stream.

## 13. m4 contract freeze — SDK envelope, receipt shape, and error taxonomy

**Decision (frozen in m4, Step 2):** the SDK/CLI contract is frozen in
`docs/contracts/astrid-sdk-v10.md`:

- The domain result envelope has exactly the keys `ok`, `data`, `error`,
  `receipt`, and `idempotency_key`.
- Error objects have exactly `code`, `message`, and bounded JSON `details`,
  using exactly the codes `validation_error`, `not_found`, `conflict`,
  `stale_version`, `terminal_state`, `idempotency_mismatch`, `integrity_error`,
  `unavailable`, and `internal_error`.
- The exposed receipt shape and the project-scoped idempotency rules
  (deterministic IDs derived from command kind/scope/key, canonical semantic
  request hashing, replay, mismatch-before-mutation, generated-key return,
  timestamps/txn-ids/incidental paths outside request identity) are exactly as
  recorded there.
- **Bridge responses never expose the receipt**: no receipt, no idempotency
  key, no `txn_id`/`request_hash`/`project_seq`/`event_ids`/`result` data is
  serialized by any bridge route (see `docs/contracts/astrid-bridge-v10.md`
  §7).
- The conservative m4 platform matrix is frozen in
  `docs/contracts/supported-platforms.md`: Linux CI, CPython 3.11 and 3.12,
  editable development install, Node 20.19 floor, and current stable Chromium
  for the external editor lane, owned by the Astrid Release Owner with a
  Sprint-5 deadline. This development matrix is distinct from m6 release
  packaging; CI must actually execute both Python targets and the editor lane.

## 14. Inspected Reigh provider state and external-gate disposition (m4)

**Status:** external, reporting-only, retained evidence. **Authority:** the m4
brief grants `reigh-timeline-main` **tests-only** authority; no authority is
granted to modify or coordinate changes in the external `banodoco/reigh-app`
repository (SD1).

**Inspected commit:** `banodoco/reigh-app` at pinned commit
`bc2d8b0327c1c7dbdcd7b7445440d8ca180dd677`.

**Pinned external test selectors (run independently in the Step 19 lane):**

1. `src/tools/video-editor/data/AstridBridgeDataProvider.test.ts`
2. `src/tools/video-editor/testing/__tests__/providerCompatibility.astrid.test.ts`
3. `src/tools/video-editor/hooks/useTimelinePersistence.test.tsx`
4. `src/tools/video-editor/hooks/usePollSync.test.ts`
5. `src/tools/video-editor/lib/timeline-save-utils.test.ts`

**Observed source contradictions (Astrid frozen contract authoritative):**

1. `AstridBridgeDataProvider.saveTimeline` **ignores `expectedVersion`** (soft
   conflicts enabled by the external compatibility suite).
2. It sends a **`{config}`-only save body** without the frozen
   `registry`/`expected_version` fields.
3. It performs a **separate registry PUT** (split write authority).
4. It retains a **local-file/FSA path** (filesystem authority).

**Disposition (frozen for m4):**

- The frozen Astrid bridge contract remains authoritative. No compatibility
  routes, soft-CAS behavior, config-only save body, split registry authority,
  or FSA fallback is added to Astrid (SD1).
- External Reigh correction authority for m4: **DENIED**. A Reigh-side
  correction requires its own recorded authorization or a North Star amendment
  and is tracked as a named upstream follow-up.
- **Absent-local-pin observation:** the pinned Reigh commit is not present in
  the Astrid checkout at m4 finalization; the Step 19 lane must fetch and
  verify it mechanically (`git rev-parse` of requested vs resolved SHA) and
  record both.
- The lane is **reporting-only**: it runs always, retains schema-validated
  disposition evidence, and external incompatibility is **never** an input to
  `make m4-gate` success and never widens Astrid's route surface.
- **Upstream owner/authorization needed:** a Reigh-side correction requires the
  upstream repository owner's recorded authorization (or a North Star
  amendment) before any change; the named follow-up tracks that trigger.

## 14A. Always-run disposition lane (m4 plan Step 23, task T24)

**Lane:** `.github/workflows/bridge-latency.yml` step "Run pinned Reigh
disposition lane (always, reporting-only)" plus
`scripts/reigh_disposition_report.py`. The lane runs **always**
(`if: always()`), so setup failures, selector failures, and latency
failures all retain results instead of skipping the report.

**What the lane verifies and records** (schema
`astrid.reigh_external_gate_disposition.v1` at
`artifacts/m4/reigh-external-gate-disposition.json`):

- The **requested and resolved Astrid SHAs** (the PR head ref vs the
  checked-out `git rev-parse HEAD`); a mismatched checkout is rejected and
  fails the reporting job closed.
- The **requested and resolved Reigh SHAs** against the pinned commit
  `bc2d8b0327c1c7dbdcd7b7445440d8ca180dd677`, with pin presence and
  reachability recorded (`reigh.pin_present`, `reigh.pin_checked_out`).
- **Setup:** `npm ci` from the Reigh lockfile before any selector runs.
- The **five pinned selectors, each run independently**:
  `AstridBridgeDataProvider.test.ts`, `providerCompatibility.astrid.test.ts`,
  `useTimelinePersistence.test.tsx`, `usePollSync.test.ts`, and
  `timeline-save-utils.test.ts` (per-selector status, return code, duration,
  and log retained under `artifacts/m4/`).
- The **bridge latency target** (`make bridge-latency-check`, GET and
  warm-save p95 ≤ 500ms) with pass/fail/unavailable status.
- The **four source contradictions** (ignored `expectedVersion`,
  `{config}`-only save body, separate registry PUT, local-file/FSA path),
  the **soft-conflict state**, the **authority decision** (external Reigh
  correction authority DENIED for m4), the **owner/follow-up**, timestamps,
  and an overall **`compatible|incompatible|unavailable`** status.

**Semantics (unchanged from section 14):** the lane always runs and retains
results; absence or malformation of the emitted evidence fails the reporting
job closed (as does an Astrid checkout SHA mismatch). External incompatibility
is recorded as retained evidence and is **never** an input to `make m4-gate`
success, and Astrid's frozen route surface is never widened. A Reigh-side
correction remains a hard named follow-up requiring the upstream repository
owner's recorded authorization (or a North Star amendment) before any change.
Locally (no Reigh checkout), the lane records `unavailable` statuses, matching
the absent-local-pin observation in section 14.

## 15. Temporary owner-lock deviation (SD3-m4) with m6 closure

**Decision (temporary North Star deviation, fail-closed, m4 only):** m4
enforces an **exclusive-owner lock** — an OS-level exclusive lock file beside
the database, held for the process lifetime, acquired **before** any second
writable connection or queue can open. A second concurrent writer process fails
closed with a typed `unavailable` error.

- During m4 exactly **one process** owns the database at a time: the serve
  process, or a standalone CLI/SDK process when no server owns the database.
- The lock is recorded as an explicit temporary deviation from the North Star's
  concurrency model (CF-A2410DC6D581F4B178BE / CF-BBA66D60FBD98B49F5E1).
- **m6 closure design:** mutations route through the serving process via
  loopback RPC, or an exclusive service-owner protocol is adopted; the lock and
  this deviation are **removed in m6**.

## 16. Reserved save-as-copy route (planned m6, not implemented in m4)

**Decision (reserved contract, CF-08C82BBD608F2CCF8A7E /
CF-F0DB9D4F2A612C886B3B):** m4 freezes the planned semantics of the save-as-copy
bridge route; m4 does **not** implement it and does **not** register a
`timelines copy` CLI verb.

Planned route: `POST /projects/:slug/timelines/:ref/copy` — reserved semantics:

- **Request body:** optional target name (object; may be empty/absent).
- **Idempotency key:** deterministic derived key from source timeline identity
  + source head + canonical copy payload.
- **CAS on the source head:** a stale source head returns
  `409 timeline_version_conflict` with the current head, zero mutation.
- **Response:** the new timeline row — fresh id, `config_version` 0, and
  `copied_from` recorded in the `timeline.created` event payload.
- **Error mapping:** 404/409/422 per the frozen bridge error vocabulary.
- **No receipt exposure:** the response never exposes a receipt or idempotency
  key.
- **m4 behavior:** the route is NOT implemented; it resolves through the
  existing "any other path → 404" grammar rule, and no `timelines copy` CLI
  verb is registered. Implementation and the CLI verb land in **m6**.

## 17. Media relation kinds and repository rules (frozen)

**Decision (frozen in m4, Step 2; CF-87F043FF00C45F104054):** the media relation
vocabulary is exactly the five frozen DDL kinds (section 7, verbatim):

`derived_from`, `variant_of`, `uses_as_input`, `mask_for`, `audio_for`.

The repository enforces exactly these rules, and the service delegates all
relation rules to the repository:

- same-project ownership (every explicit `media_id` and locator-alias lookup is
  project-scoped; cross-project returns `not_found`);
- self-edge rejection;
- duplicate rejection;
- one `variant_of` parent;
- variant-cycle rejection.

There is **no per-kind direction matrix** and none may be invented; `variant_of`
direction is defined only by the one-parent rule.

---

**Record of amendments:**

- **m4 amendment 1 (Sprint 4–5):** added §13–§17 (SDK contract freeze,
  inspected Reigh provider state and external-gate disposition, temporary
  owner-lock deviation with m6 closure, reserved save-as-copy route, media
  relation rules) and superseded the m1 "editor checkout absent" observations
  in §3 and §11. No previously frozen m1–m3 value was reopened by this
  amendment.