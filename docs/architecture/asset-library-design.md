# Project Asset Library — Design

Status: **proposed** (recorded decisions below)
Date: 2026-08-09
Ticket: [`.megaplan/tickets/01KZKXM3ZP5A3WF6R691Y1RS39-project-asset-library.md`](../../.megaplan/tickets/01KZKXM3ZP5A3WF6R691Y1RS39-project-asset-library.md)

## 1. The problem

A maker wants to store **project assets** — characters with reference images and
multiple shots/views, and scenes — and **associate them with a timeline** so they
can be reused across generation runs. Today Astrid has **no structured way to do
this**:

- No character/cast/entity model anywhere in `astrid/`.
- `sources/` exists per-project but is a loose drop folder (e.g.
  `projects/desert-plant-growth/sources/` holds ad-hoc reference PNGs with no
  schema, no association).
- The timeline `AssetRegistry` is a materialized key→file map populated only via
  Supabase/editor-import events; it has no CLI writer and cannot model planned
  characters, empty scenes, or ordered shots.
- Reference images are per-run CLI args (`--image-ref`) staged into `runs/<id>/inputs/`
  with a rich role vocabulary, then thrown away.

This is a **build, not a find**.

## 2. Fundamental structure

Three layers, one job each.

| Layer | Owns | Store |
|---|---|---|
| **Library** (new) | semantics: characters, scenes, shots, references | `projects/<slug>/library/` atomic JSON files |
| **Sources** (exists) | media bytes, hashes, provenance | `projects/<slug>/sources/`, content-addressed `src-<ULID>` |
| **Timeline** (exists) | occurrences: clips, bindings, registry | event stream + projections |

**Interaction rules:**

1. **Entities never hold bytes; they hold ids.** All byte access flows through
   Sources via the Reference edge.
2. **The timeline never holds semantics; it holds a frozen snapshot + keys.**
   The cut is a projection. If any tool writes real semantics into the timeline,
   the split collapses.
3. **Every view is derived, never duplicated.** Registry is a projection of
   Sources; assembly is a projection of Events; a Binding is a projection of
   Entities at a revision.
4. **Reference resolution falls back in order:** shot override → scene defaults →
   character defaults (per role).

**The five irreducible primitives:**

1. **Source** — content-addressed bytes (`src-<ULID>`, kind, `content_sha256`, `promoted_from`).
2. **Entity** — versioned semantic identity (Character/Scene/Shot are kinds).
3. **Reference** — the media↔entity edge (owner, source_id, role, view, approved).
4. **Binding** — occurrence↔entity at a revision snapshot (`generation.astridLibrary`).
5. **Resolver** — the pure function from (binding + library + capability) → ordered executor-ready bundle.

Everything else is a specialization (Take ⊂ Reference), a projection (registry ⊂
sources), or a role (character/scene/shot ⊂ Entity).

## 3. The central decision

**Where does semantic state live, and how does it reach the cut?**

- **(a) Put semantics in the timeline** — extend `AssetEntry`/registry. *Rejected*:
  shared event-sourced schema (Reigh/Supabase) → cross-repo migration; one-file-per-URL
  entries can't model planned characters, empty scenes, ordered shots.
- **(b) Library-as-files + timeline-as-pure-projection** — **chosen**. Zero new
  timeline events, zero schema bumps; semantics versioned where only we own them.
- **(c) Something simpler** — open; see Q1.

Sub-decisions riding (b): binding lives in a versioned `generation.astridLibrary`
envelope; entities are atomic JSON files; **promotion may auto-create a candidate
Reference and curation determines canon eligibility** (generation alone creates
nothing); binds are full-config-replacement + CAS with the **binding canonical**
and `pinnedShotGroups` derived; drift is snapshot + explicit rebind, never silent
mutation.

## 4. Related work already in the repo

There is **no existing epic** for an asset library. Partial overlaps:

- **Shot-First Composition** (`.megaplan/initiatives/shot-first-composition/NORTHSTAR.md`,
  active, ~M1) — shot as atomic editorial unit with stable `shotId`; explicitly
  refuses `PinnedShotGroup` as a composition database. **Our binding design must
  keep `pinnedShotGroups` as occurrence-grouping, never semantic.** Synergy: our
  library `Shot` and their `ShotPlan` could share one ID namespace (see Q3).
- **Asset-cache retention bug** (`.megaplan/tickets/01KSZ60BSTRJGXJWH8VMXN40A1-asset-cacheprune-can-evict-assets-a-project-still-references.md`,
  open) — TTL prune can evict a source a project still references. **Our "sources
  are durable" claim inherits this hole**; promotion must physically copy out of
  the cache and the library becomes the missing ref-counting authority (see Q8).
- **Timeline event-sourcing milestones** (`docs/architecture/timeline-event-sourcing/m1-schema.md`,
  `timeline-event-sourcing/m6a-astrid-supabase-contract.md`) — define `asset_ref: {registry_id, content_sha256}`;
  carry an open **orphan-asset / asset-URL-stability** question (`m1-schema.md:104`,
  `m6-reigh-sync.md:84`). Our registry GC answers it.
- **Timeline Visualization** (`.megaplan/initiatives/timeline-visualization/`) —
  `--shot ID` / `--asset ID` navigation; a future consumer of the association model.

## 5. Recorded decisions (oracle Q1–Q19, two rounds)

Each decision records the verdict, the reasoning that won, and its **tripwire**
(the condition that forces a revisit).

### Q1 — Semantic state location. **Plan (b).**
Semantics we solely own should be versioned where only we own them. Coupling
entity-model evolution to the Reigh/Supabase migration cadence makes every
iteration a cross-repo negotiation. Event-sourcing the library is premature —
atomic JSON files replay into events later. **Keep the door open:** store
revisions explicitly (embedded history or sidecar) so a future migration is a
mechanical replay, not archaeology.

### Q2 — Binding carrier. **Keep the dict, but version + validate the envelope.**
`generation.astridLibrary = {v: 1, ...}`; validate at exactly two chokepoints —
the writer and the resolver, which **refuses** unversioned/invalid bindings rather
than best-effort parsing. A typed contract in practice, no schema bump.
**Tripwire:** when a third consumer appears (Reigh, the UI, another service
reading `astridLibrary`) → promote to a typed schema field.

### Q3 — Shot identity unification with Shot-First. **One ID namespace, two records.**
Share the `shotId` namespace (gives Shot-First its join key and Timeline Viz free
navigation across both worlds) but do **not** merge the records — a `ShotPlan`
can exist with no canon and a library `Shot` with no plan; their lifecycles
differ. **Non-negotiable: a single minting authority** (library mints and ShotPlan
holds a FK, or vice versa — never two mints reconciled later). This is a
**coordination decision with the Shot-First owner, not an oracle question**, and
it must happen before either side ships IDs.

### Q4 — Association automation. **Auto-create as candidate; explicit gate for canon.**
Provenance and curation are different concerns: a run that knows its shot/character
and doesn't record the edge is losing data. So promote auto-creates the
Take/Reference with `status: candidate`; the curation gate moves it to
preferred/approved; the resolver's fallback chain **only reads curated statuses**.
Curation becomes a status transition, not a data-entry chore.

### Q5 — Primitive granularity. **Take ⊂ Reference iff the edge carries provenance.**
Reference needs a provenance slot (generation id, prompt hash, parent take).
**Tripwire:** when provenance forces its own record anyway → promote Take to
first-class. Entity-with-kind is fine **provided ordering/membership live on edges
(ranked member-of), not on the kind** — if the generic Entity can't express an
ordered edge, that's the real loss.

### Q6 — Revision policy. **Snapshot + explicit rebind; make staleness loud.**
The auto-rebind "non-controversial fields" middle is a trap — "non-controversial"
is a judgment that drifts and creates two mental models of one mechanism.
Keep semantics uniform; attack the cost: a cheap drift report (`library status`
diffing each frozen binding vs current revisions) + a one-command bulk rebind
with preview. Agents handle "run this check, then this command" beautifully.

### Q7 — Concurrency for binds. **Defer granular events, but log bind intents now.**
Whole-config CAS breaks only where conflict rates are low today (multi-agent binds,
coarse undo, branch/merge — all plausibly 12+ months out). **Insurance:** record
each bind as an intent (clip id + binding payload + timestamp) in a log even while
applying it as a whole-file write — the eventual migration to granular events is a
replay of history, and undo gets a semantic record.

### Q8 — Content vs semantic identity. **Semantic ID leads; sha256 is integrity/dedupe.**
Bytes get re-encoded, upscaled, color-managed — same semantic asset, new hash;
content-as-primary-key forces identity churn on every transcode. **On retention
(the one real hole):** promotion must **physically copy bytes into project-owned
storage**, deduped by sha256 within the project. Then the layers interlock:

- `asset_cache` keeps TTL semantics — it's a cache again, allowed to be lossy.
- `sources/` GC is library-aware: collectible iff no Reference edge **and** no
  registry entry points at it, with a grace period.
- **Orphan-asset rule** (answers `m1-schema.md:104`): a registry entry is
  orphaned iff no clip and no library reference holds it.

This makes the library the missing ref-counting authority the retention bug asks
for — **link: `01KSZ60BSTRJGXJWH8VMXN40A1`**.

### Q9 — The "scene" collision. **Rename; the detection side is the misnomer.**
In film vocabulary, PySceneDetect finds **cut boundaries / shots**, not scenes;
`editorial.scenes` borrowed the name loosely from the tool. Our library Scene is
the term of art. If renaming `editorial.scenes` is off the table, enforce
disambiguation at the identifier level: `DetectedScene` / cut boundaries in new
code and docs; bare "scene" banned in shared contexts. Context disambiguation is
**not** enough — agents reading prompts and CLI help are exactly the population
that conflates the two.

### Q10 — Reuse machinery. **Dedicated resolver.**
The pool→arrangement→timeline chain is occurrence machinery; resolution is a pure
function from intent + library state to executor-ready inputs. Routing resolution
through the clip-extraction chain smuggles semantics into occurrence-land (rule 2,
violated). Relationship is **directional**: the resolver may *emit into* that
chain, never *live inside* it.

### Round 2 — storage, concurrency, resolution (oracle Q11–Q19)

Second oracle pass. Verdicts below are the amended versions after review: Q13,
Q16, Q17, Q19 resolve the same way — make the mechanisms obey invariant #3
("every view is derived, never duplicated") more literally.

### Q11 — Two binding mechanisms. **Complementary; keep separate, unify the read path.**
`prompt/v1 → shotId` binds intent/data to the semantic unit (canon side);
`generation.astridLibrary → clip` binds reference-media resolution to an
occurrence (cut side). Aliasing one to the other collapses the canon/occurrence
boundary (rule 2). The "agent has two places to look" risk is a **read** problem:
solve it with a single query surface (`library describe --shot <id>`) that joins
prompt bindings and clip envelopes through the shared shotId. Two write seams,
one read lens. **Tripwires:** if the prompt association and the envelope ever
carry the same field → merge; and define an explicit **precedence** rule for when
both bindings exist and disagree — one wins by construction, never by accident.

### Q12 — Minting authority. **Mint the namespace, not the record; dangling FK is a status.**
ID generation is one shared function (one ULID shape, one prefix) — the only
thing that must be literally singular, guaranteeing global uniqueness. Semantic
authority belongs to the library once a canon record exists; before that a
shotId held only by a ShotPlan is a **reservation**, and the library FK is
legitimately dangling — a first-class, queryable status (unbound/reserved) via
`library doctor`/lint, never a validation error. The library **adopts** the
reserved ID when canon is created. Forbidden: the library minting a second ID for
a shot that already has a reservation. **Follow-up:** dead reservations need a
reaper — doctor reports them, nothing reclaims them today.

### Q13 — Library concurrency. **Add revision + expected_revision CAS to store.py now.**
Cheapest non-regret: retrofitting later means migrating every entity file and
every caller; adding now is ~20 lines. The single-writer-per-project assumption
is already false (two agent sessions; a crashed-and-retried mid-write produces a
silent lost update — the worst bug to diagnose). The timeline already uses
expected-version CAS — one concurrency idiom system-wide, agents learn the retry
pattern once. **Do not build more:** no locks, no leases, no merge.
CAS-fail → re-read → retry is enough.

**Implementation amendment (2026-08-09, codex + swarm verified):** a **brief
advisory lock on a stable per-record lock file** around re-read → expected-
revision check → WAL append → rename IS required for process safety —
`write_json_atomic` (`foundation/atomic_io.py:108`) makes only the final rename
atomic, so two writers can both read revision N and commit N+1. "No locks" is
amended to mean **no durable/domain locks or leases**; a short per-write
advisory lock is permitted. Prove it with a two-process test asserting exactly
one competing write succeeds.

### Q14 — Replace a reference image. **New Source always; mutate the Reference pointer; runs pin by sha.**
Bytes: always a new Source — the vault is content-addressed and immutable
(sha256 dedupe gives this free). Semantics: mutate `Reference.source_id`,
recording the transition in revision history. A new Reference per byte-change
manufactures churn — every binding pointing at the old record dangles or resolves
stale. History stays honest because runs record the resolved sha256 in the
manifest; past runs pin by hash, not by the mutable pointer. **Enforcement is
structural, not optional:** the resolver's output is the resolved set *with*
content hashes (not paths-with-optional-hashes), and `finalize_project_run`
**fails** if any consumed reference lacks its sha in the manifest. The
pointer-mutation argument is only sound under that enforcement. Reference
`source_id` transitions are **revision history for Reference entities** — same
sidecar as Q17, not a parallel mechanism. Exception: a new role/view is a
different semantic identity → new Reference record, no replacement.

### Q15 — Resolver capabilities. **Executor-declared; ship hardcoded behind the declared-shaped interface.**
Define the capability schema now (roles accepted, max counts per role, type
constraints, flag mapping — small); implement the MVP resolver against that
schema with a hardcoded table shaped exactly like the future `executor.yaml`
stanza; move the data into yaml in Phase 2 with **zero resolver changes**. Treat
the schema as a public, versioned contract from day one — it is the de-facto
interface even while hardcoded. Two requirements either way: the resolver
**fails closed** on undeclared capabilities (an executor with no declaration
accepts no references), and limit-enforcement errors name the executor's
declaration so agents can self-correct.

### Q16 — Occurrence layer. **The binding is canonical; demote pinnedShotGroups to a derived view.**
As a written store it's over-engineered and violates rule 3. Grouping is
computable from clips' shared `astridLibrary.shotId` → it is a view. The binding
writer **materializes** pinnedShotGroups as derived output — atomic with the
binding because both live in the same timeline config document (one full-config
replacement guarded by expected-version CAS; nothing to transact across). The
doctor check's real job is **foreign-writer reconciliation**: Supabase/editor
imports populate pinnedShotGroups without the derivation rule → flag entries not
derivable from clip envelopes and mark them legacy (dovetails with Q19). Nothing
else may write it. **Signal to go purist (derive on read, stop materializing):**
the reconciliation burden grows.

**Implementation amendment (2026-08-09, codex + swarm verified):**
`local_bridge.py:317-321` filters config to `_BRIDGE_CANONICAL_TOP_KEYS`, which
**omits `pinnedShotGroups`** — an editor save would delete the derived
materialization while preserving envelopes. The bridge key must be preserved and
library-owned groups reconciled; `library doctor` must detect **both**
non-derivable foreign groups **and** missing/incomplete derived groups; add an
editor round-trip test.

### Q17 — History embedding. **Sidecar append-only JSONL, WAL-ordered.**
In-file history's cost arrives first and compounds: agents re-read entity files
constantly, so the hot read path (and every agent's token cost) degrades linearly
with edit count, and larger files widen the atomic-rewrite window (interacts with
Q13). Sidecar keeps the entity file the source of truth (`revision` +
`updated_at`); history is audit. **Write order (WAL):** append the history entry
(intended transition, with the new revision) and fsync, *then* write the entity
file (the CAS-guarded atomic rename is the commit point). A crash between them
leaves an orphan log entry — replay treats it as an aborted transition and
discards it; `library doctor` detects `history_head > entity.revision`. This is
the property replayability needs: every committed revision has its log entry.
The sidecar is a proto-event-log — replayable into events later by rename.

### Q18 — Performance cliff. **Instrument → memoize → index-with-validation, design now.**
Resolve is fine (per-run frequency; a per-run memoized loader, no invalidation
problem — it dies with the run). The cliff is directory-scan queries (list
references for entity X, describe shot, adoption/doctor) at **agent-turn**
frequency — 10–100× the resolve rate, against the same unindexed store. Plan:
(1) instrument now — counters/timings on store reads and scans, so the cliff is
observed not guessed; (2) per-run memoized loader in the resolver,
unconditionally, it's free; (3) denormalized index **only when instrumentation
shows scans hurt** — but design its staleness story now: `store.py` is the single
write choke point, the index is maintained in the same process as the CAS write
(staleness only from crashes), entries carry `(entity_id, revision)`, and doctor
rebuilds on mismatch. That is a rebuildable materialization with a validation
key (invariant #3 shape), **not** a persistent cache. Avoid any persistent cache
— staleness plus the multi-writer future from Q13.

### Q19 — Legacy registry / pinnedShotGroups. **Legacy, readable, never canonical.**
Retroactive adoption has an asymmetric failure mode: a half-right mapping
pollutes canon, and polluted canon is worse than a dead legacy lane — everything
downstream (resolution, provenance, agent reasoning) trusts canon. The apparent
forcing function — the retention-bug fix needing GC ref-counts — does **not**
require adoption: sources GC treats legacy registry entries as opaque pins
without any library record behind them (counting references ≠ assigning
semantics). Keep the explicit-mapping adopt-timeline design in a drawer; build it
on these signals: resolver-miss telemetry (agents repeatedly referencing
registry-only assets in new runs — measurable once Q18's instrumentation
exists), a concrete project needing library-driven regeneration, and the mapping
burden proving small in practice.

## 6. Open questions / follow-ups

- **Q3 coordination** — decide minting authority with the Shot-First Composition
  owner before either side ships IDs. (Human decision, not an oracle question.)
- **Q5 ordered edges** — validate that the generic Entity schema can express
  ranked member-of edges; this is the least-settled-by-argument question.
- **Q2 / Q7 tripwires** — third-consumer promotion rule; bind intent-log adoption.
- **Q12 reaper** — dead ShotPlan reservations are reported by doctor but never
  reclaimed; decide a GC policy before reservations accumulate.
- **Q14 enforcement** — `finalize_project_run` failing on a reference without a
  manifest sha is load-bearing for the pointer-mutation model; build it with the
  resolver, not after.
- **Q16 foreign-writer reconciliation** — the doctor check that flags
  pinnedShotGroups not derivable from clip envelopes is the actual guarantee
  (the binding-writer materialization is atomic by construction); go purist /
  derive-on-read if reconciliation burden grows.
- **Q17 WAL check** — `library doctor` detecting `history_head > entity.revision`
  (orphan log entry = aborted transition) is a first-class doctor check.
- **Q18 index design** — the revision-keyed (`entity_id, revision`) index is a
  derived view with a validation key; design the rebuild-on-mismatch now, build
  on evidence from instrumentation.

## 7. Reference materials

- `gpt-5.6-sol` implementation plan (planning subagent output) — `/tmp/astrid-plan/plan.md`
- Discovery synthesis (swarm) — `/tmp/astrid-plan/discovery-synthesis.md`
- Lifecycle/architecture diagram — `~/Documents/gpt-image-outputs/astrid-library-architecture.png`
- Related: `01KSZ60BSTRJGXJWH8VMXN40A1` (asset-cache retention), Shot-First Composition NORTHSTAR

## 8. Simplification round (2026-08-09) — supersedes

A codex simplification audit (goal: **well-engineered + robust, not overkill**)
cut roughly half the machinery. The single biggest over-engineering: a **second
transaction system around bind** (intent WAL, txn recovery, persisted
`pinnedShotGroups`, bridge preservation, doctor reconciliation) despite
registry-first timeline events already making partial failure safe.

**Superseded verdicts** (with the reason):

- **Q13 granularity → one atomic catalog.** Single `library/catalog.json` + one
  catalog `revision` + short project-library lock; validate the whole catalog on
  every write. Per-record files/locks/indexes are concurrency M1 doesn't need.
- **Q14 pointer-mutation → new Reference + archive.** Improved bytes create a new
  Source + new Reference; the old Reference is archived in the same catalog
  write. Old bindings stay frozen on their Source. Removes the dependency on
  mutation history and manifest pinning.
- **Q15 capability schema → defer.** No M1 generation consumer; small explicit
  adapters until the shape stabilizes.
- **Q16 persisted derived groups → derive-on-read.** The storyboard (sole M1
  consumer) groups clips in memory from envelopes; the library never serializes
  `pinnedShotGroups`. Deletes bridge preservation + doctor reconciliation for
  groups.
- **Q17 WAL history → none in M1.** Nothing replays it; current state is
  authoritative; Sources are immutable; timeline binds already have event
  history.
- **Q18 instrumentation/index → one catalog.** One catalog read per command
  removes the scan cliff, telemetry, memoization, and index backstop.
- **Q12 reservation lifecycle + hard launch gate → `shot create --id`.** M1
  ships shots with user-supplied/ULID ids; minting coordination deferred (still
  one shared ULID format).
- **Q11 `describe --shot` + precedence → defer** until the second binding is
  live.
- **Q7 intent-WAL → the existing timeline event stream is the WAL.**
  Registry-first already defines the safe partial-failure state (an unused
  registry entry). Add only "latest registry event → `registry.json`" sidecar
  repair.

**Kept unchanged:** layer separation; frozen versioned envelope; curation gate;
physical copy + registry entry shape (`file`/`type`/`content_sha256`); approved-
only fallback resolution; archive-not-delete; storyboard as sole adapter calling
core resolution; explicit rejection of unsupported non-local writes.

## 9. Agent ergonomics (2026-08-09)

The conceptual model (film grammar) is intuitive, but the ceremony was not for
the batch case — "generate 4 characters and make them canonical" required
~28 commands (create ×4, promote ×N, approve ×N), with a non-obvious
entity-first ordering, implicit approval-as-canonical, and dense multi-concept
flags.

The ergonomics layer **composes existing primitives — no new machinery**:

1. **Batch character creation** — `characters add --name "Mara" --slug mara
   --outputs front.png,profile.png --views front,profile` creates the entity,
   promotes each view, and attaches references in one command. Approved by
   default — the command *is* the explicit canon-making intent; `--candidate`
   opts out. SDK: `lib.characters.canonicalize(...)`.
2. **One-step blessing** — `promote` accepts `--approved`; `promote` /
   `reference add` accept `--create-owner` (auto-create a missing
   character/scene/shot — removes the entity-first ordering gotcha). Promotion
   alone stays candidate by default (never silent).
3. **Legible canonical state** — `character show` and `library status` report
   canonical state explicitly ("Mara — canonical (2 approved refs)"; "3/4
   canonical; Sven needs approved references") so an agent knows when it is
   done.

This preserves the curation gate (approval is never silent) while compressing
the ceremony into intent-shaped commands.

## 10. Extensible metadata (2026-08-09)

Every entity record (character, scene, shot, reference) carries an optional
free-form `metadata: dict[str, Any]`, validated only for JSON-serializability
(and a generous size bound). This is the escape hatch for agent- and
domain-specific notes that do not deserve schema — wardrobe/lighting/mood
details, prompt anchors beyond the reserved ones, custom tags, links to external
resources, provenance cross-refs.

The boundary that keeps it safe:

- **Structural facts stay structural.** The resolver and invariants depend on
  typed fields: `role`, `view`, `rank`, `status`, `owner`, `source_id`,
  `revision`. These are validated and never read from `metadata`. If a fact the
  system must act on is only in `metadata`, it does not exist.
- **`metadata` is advisory and opaque to the resolver.** Carried, preserved on
  revision, returned by `show`/`list` — never interpreted.
- **The cut stays rigid.** The binding envelope (`generation.astridLibrary`) has
  a frozen, validated shape; consumers may not add arbitrary fields to it, and
  the timeline is a projection. Registry entries keep their locked
  `file`/`type`/`content_sha256` shape with no semantics. Flexibility lives on
  library entities, not in the timeline's derived state.

The simplification's "concrete fields, not a generic ranked-edge graph" was
about the relational structure (don't model character/scene/shot as one generic
node-graph); `metadata` is the per-entity extension point that concreteness buys.
