# Project Asset Library — Architecture & Integration

Status: **proposed**
Date: 2026-08-09
Companion docs:
- [asset-library-design.md](asset-library-design.md) — the library design + recorded decisions (Q1–Q10)
- Ticket: [`.megaplan/tickets/01KZKXM3ZP5A3WF6R691Y1RS39-project-asset-library.md`](../../.megaplan/tickets/01KZKXM3ZP5A3WF6R691Y1RS39-project-asset-library.md)

## 1. The system

The feature is a **closed loop across four domains**. Three are stores; one is
flow. The Reference record is the hub that ties the three stores together.

```text
             LIBRARY (canon — semantics)              RUN (history)
       characters · scenes · shots · references        run.json · manifest
             │        │                                    │
             │        │  owner {kind,id}                   │  provenance
             │        ▼                                    ▼
             │   ┌────────────────── REFERENCE ────────────────────┐
             │   │             role · view · status · provenance   │
             │   └───────┬──────────────────────────┬──────────────┘
             │           │ source_id                │ bind
             │           ▼                          ▼
             │    SOURCES (vault)           TIMELINE (cut — occurrences)
             │    bytes · sha256           registry keys ·
             │           ▲                 astridLibrary (v:1) ·
             │           │                 pinnedShotGroups (derived)
             ▼           │  promote                  │ resolve
   default/override      │                          ▼
   lists, preferred      │                GENERATION RUN ──► outputs/
   take (canon)          │                                       │
                         └─────────────── promote ───────────────┘
```

**The six flows:** promote · reference · take · bind · resolve · generate.

**The three invariants:** entities never hold bytes · the timeline never holds
semantics · every view is derived, never duplicated.

**The five primitives:** Source · Entity · Reference · Binding · Resolver.

## 2. Reuse map — how it relates to existing Astrid primitives

Nothing is built on greenfield; every new surface rides an existing rail.

| Existing primitive | Reuse | Extension |
|---|---|---|
| `sources/`, `add_source`, `register_source_file` (`core/project/source.py`, `project.py`) | durable media store | `promote_source_file` — **physical copy**, sha256 dedupe, stable `src-<ULID>`, `promoted_from` provenance |
| Timeline `AssetRegistry` / `asset_registry_replaced` (`core/timeline/banodoco_schema.py`, `events/schema/payloads/asset_registry.py`) | materialized resolver | a CLI writer (today populated only via Supabase/editor import); no schema change |
| `timeline.config_replaced` + expected-version CAS (`core/cli/timeline_edits.py`) | binding writes | envelope + occurrence merged into full-config replacement |
| `clip.generation` free-form dict (`banodoco_schema.py`) | envelope carrier | versioned `astridLibrary = {v:1, ...}` + writer/resolver validation |
| `pinnedShotGroups` (`core/timeline/banodoco_schema.py`) | **derived** occurrence view (binding canonical, Q16) | never a written store; the binding writer materializes it atomically; doctor reconciles foreign writes |
| Reference role vocabulary (`core/experiments/schema.py:43`) | reference roles | `view` orthogonal to role; provenance slot on the edge |
| `result_manifest.py` hashing (`core/_shared/result_manifest.py`) | integrity/dedupe backbone | promotion reuses manifest hashes directly |
| `editorial.scenes` / `shots` | **detected segments** | import as drafts only; rename to avoid "scene" collision (Q9) |
| `training.pool_build` / `pool_merge` | occurrence machinery | resolver may **emit into** the chain, never **live inside** it (Q10) |
| `project/run.py` — `finalize_project_run`, `mirror_hype_artifacts`, `record_contributing_run`, `bind_managed_timeline` | provenance + run→timeline linkage | provenance records carry the binding context for auto-`candidate` (Q4) |
| `project/ownership.py` — `require_project_owned_artifact` | project-owned enforcement | recognize `library/*` + `sources/*` as owned |
| `themes/` reference shapes | field-naming precedent | repo-global; not the library store |

## 3. Coordination map — how it relates to other initiatives and tickets

| Other work | Relationship | Open coordination |
|---|---|---|
| **Shot-First Composition** (`.megaplan/initiatives/shot-first-composition/`) | library `Shot` is the reusable canon; their `ShotPlan` is the composition-side occurrence; **shared `shotId` namespace** | **Q12 — one shared mint *function*** + reservation/adoption; settle ownership before `init` |
| **Typed-timeline-data-automation** (Shot-First's data epic) | binds `prompt/v1` to shots by stable `shotId`; we bind `generation.astridLibrary` to clips | **Q11 — complementary, separate write seams, unified read lens** (`library describe --shot`) |
| **Timeline Visualization** (`.megaplan/initiatives/timeline-visualization/`) | consumer of the association model (`--shot`, `--asset`) | none — benefits from shared shotId |
| **Pluggable-timeline-renderers** | storyboard proof consumes bindings; resolution stays renderer-agnostic | `timeline_storyboard` is the sole permitted consumer-adapter change |
| **Asset-cache retention bug** `01KSZ60BSTRJGXJWH8VMXN40A1` | the library is the fix direction: promotion copies bytes out of the TTL cache; `sources/` GC ref-counts | link both tickets (done); GC grace policy |
| **Timeline event-sourcing** (`timeline-event-sourcing/m1-schema.md`, `timeline-event-sourcing/m6a-astrid-supabase-contract.md`) | orphan-asset question answered by our registry GC rule | **Q19 — legacy entries are opaque pins, never canon** |

## 4. Deliberate boundaries (what we do not build)

- **No new timeline event kinds** in the MVP (bind via `config_replaced`; granular events deferred, intent-log as insurance).
- **No `AssetEntry` / timeline schema changes** (avoids cross-repo Reigh/Supabase migration).
- **No library event-sourcing** (atomic JSON files; history is a sidecar JSONL, WAL-ordered, replayable later — Q17).
- **No renderer contracts/backends and no renderer-dependent resolver logic**; `timeline_storyboard` is the **sole** permitted consumer-adapter change.
- **No second persistence backend**; local-first, fail explicitly on unsupported Supabase writes until Phase 2.
- **The binding is canonical; `pinnedShotGroups` is a derived materialization**, never a written store (Q16).
- **No persistent cache**; the revision-keyed index is a rebuildable derived view maintained by `store.py` (Q18).

## 5. Architecture questions (O1–O9) — superseded by design doc Round 2

These were the architecture-level questions. **They are now answered** — the
design doc's Round 2 (oracle **Q11–Q19**) settled each:

| Architecture question | Settled as |
|---|---|
| O1 two binding mechanisms | Q11 — complementary; separate write seams, unified read lens (`library describe --shot`) |
| O2 minting authority | Q12 — one shared mint *function*; reservation/adoption; dangling FK is a status, not an error |
| O3 library concurrency | Q13 — `revision + expected_revision` CAS in `store.py`, now |
| O4 replace reference image | Q14 — new Source, mutate Reference pointer, runs pin by sha256 |
| O5 resolver capabilities | Q15 — executor-declared shape, shipped hardcoded behind it; fails closed |
| O6 occurrence layer | Q16 — binding canonical; `pinnedShotGroups` derived |
| O7 history embedding | Q17 — sidecar append-only JSONL, WAL-ordered |
| O8 performance cliff | Q18 — instrument → memoize → index-with-validation |
| O9 legacy migration | Q19 — legacy readable, never canonical; opaque pins |

The O1–O9 reasoning below is retained as the historical argument; treat the
design doc's Q11–Q19 verdicts as authoritative.

**O1 — Two binding mechanisms to a shot.** Shot-First's data epic binds `prompt/v1`
to a shot by `shotId`; we bind `generation.astridLibrary` to a clip. Are these
competing roads to the same shot, or complementary (one for data, one for
reference-media)? If they converge, should `astridLibrary` eventually *alias*
the prompt association — or does keeping them separate preserve cleaner seams?
Risk: an agent has two places to look for "what is this shot."

**O2 — How does "single minting authority" actually resolve?** Q3 demanded one
mint. But Shot-First requires that "a ShotPlan can exist with no canon" — a
composition authored before any library shot exists. If the library is the mint,
that's impossible. Is the coherent model: a *namespace* both sides use, where
authority means "whoever creates the record first," and the other side holds a
foreign key that may dangle temporarily? Or is there a sharper rule?

**O3 — Concurrency for the library itself.** Timeline binds have CAS. Library
entity files are atomic writes with no optimistic-concurrency control. For
agent-shaped sessions where two agents could edit the same project, is a
single-writer-per-project assumption safe, or does `store.py` need a
compare-and-set on entity revision too? What's the cheapest thing that doesn't
regret itself later?

**O4 — "Replace a reference image" semantics.** A better portrait of Mara
arrives. Does that create a **new** Source + **new** Reference record (canon
immutable, old record archived), or **mutate** the existing Reference to point at
a new source revision? Byte identity and semantic identity diverge here; which
choice keeps the provenance graph honest without inventing a churn problem?

**O5 — Resolver capability ownership.** The resolver maps roles → executor flags
and enforces limits (e.g. `fal.h3_video` takes ≤9 `image_ref`). Is that mapping a
core responsibility (hardcoded, as the plan implies), or should each executor
*declare* its reference capabilities in its `executor.yaml` and the resolver read
them? The latter scales to packs that evolve independently — does it justify the
new contract?

**O6 — Is the occurrence layer over-engineered?** Between intent and the actual
clip there are four layers: library `Shot` → binding → occurrence
(`pinnedShotGroups`) → clips. Shot-First treats `pinnedShotGroups` as a
compatibility fallback, not canonical. If the binding itself were the occurrence
(grouping is derivable from the clips' shared `astridLibrary`), we drop one
concept. Is the double-bookkeeping (binding + occurrence group) a smell, or does
it buy something real (repeatable shots, grouping across non-adjacent clips)?

**O7 — History embedding.** The entity file carries an embedded `history` of
revisions (Q1 tripwire: replayable into events later). Is in-file history the
right call, or a sidecar? In-file keeps entities self-contained and atomic; a
sidecar keeps the hot read path small. Which cost appears first in an
agent-heavy workload?

**O8 — First performance cliff.** Every resolve walks binding → library →
references → sources → filesystem. For a long timeline with many binds and a big
canon, where's the first cliff, and is the mitigation an in-process resolver
cache, a denormalized project index, or is it genuinely fine because resolves are
rare (per generation run, not per frame)? The plan assumes the latter — worth
testing the assumption.

**O9 — Legacy registry / pinnedShotGroups migration.** Existing timelines carry
registry entries and pinned groups from Supabase/editor imports, with no library
behind them. Do we retroactively associate them (a `library adopt-timeline` that
requires explicit mappings, as planned) — or is that a dead-end that should
just stay "legacy, readable, never canonical," and new work is the only thing
that gets library bindings? What signals would tell us the retroactive path is
worth its cost?

---

The O1–O9 questions above are retained as historical argument; the design doc's
Round 2 verdicts (Q11–Q19) are authoritative. Genuine residuals for the planner:
Q3 minting coordination (settle before `init`), Q5 ordered-edge schema
validation, Q11 binding-precedence rule, Q12 reservation-reaper policy, and the
sources GC grace policy.
