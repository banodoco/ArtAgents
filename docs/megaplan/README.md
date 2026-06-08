# Megaplan Operational History

> **This directory is operational history, not current product documentation.**
> For canonical current docs, start at [`docs/README.md`](../README.md).

These files preserve planning artifacts, epic briefs, milestone handoffs, audit
syntheses, harness design records, and chain-runner configurations. They are
useful for understanding why decisions were made, but they are **not** the
current source of truth for product behavior, contracts, or APIs.

---

## Top-Level Planning Records

| Document | What it covers |
|---|---|
| [git-backed-packs-plan.md](git-backed-packs-plan.md) | Plan: Git-backed, schema-validated pack bundles (moved from `docs/` root) |
| [agentic-pipeline.md](agentic-pipeline.md) | Agentic assessment pipeline sprint brief |
| [parallel-runner.md](parallel-runner.md) | Agentic parallel runner sprint brief |
| [agentic-state-mutation-coverage.md](agentic-state-mutation-coverage.md) | Agentic state-mutation coverage sprint outcome |
| [loose-work-consolidation-plan.md](loose-work-consolidation-plan.md) | Loose-work branch consolidation plan (2026-05-23) |

---

## Epic Directories

Each epic directory contains milestone briefs, chain specs, and handoff notes.

| Epic | Contents |
|---|---|
| [epics/pack-system/](epics/pack-system/) | Pack contract, wakeup note, chain config |
| [epics/harness-polish/](epics/harness-polish/) | M1–M5b harness polish milestones, EPIC overview |
| [epics/builtin-training/](epics/builtin-training/) | Built-in training dataset build contracts, fixtures, placement |
| [epics/timeline-event-sourcing/](epics/timeline-event-sourcing/) | M1–M9 timeline event-sourcing milestones, EPIC overview |
| [epics/run-ledger/](epics/run-ledger/) | M1–M2 run ledger contract and audit dossiers |
| [epics/output-result-contract/](epics/output-result-contract/) | M1–M2 output result contract and exemption burndown |
| [epics/pack-taxonomy/](epics/pack-taxonomy/) | Pack taxonomy EPIC and chain config |
| [epics/astrid-sisypy/](epics/astrid-sisypy/) | Astrid–Sisypy integration epic |
| [epics/identity-unification/](epics/identity-unification/) | Identity unification epic |

---

## Git-Backed Packs Chain

The [git-backed-packs/](git-backed-packs/) directory holds the megaplan chain
configuration, cloud deployment spec, and sprint idea files for the
Git-backed packs implementation. See [git-backed-packs/README.md](git-backed-packs/README.md)
for chain-runner instructions and the sprint index.

The source-of-truth planning document is
[git-backed-packs-plan.md](git-backed-packs-plan.md).

---

## Root vs. History

- **`docs/` root**: Current product, contributor, and architecture docs.
- **`docs/architecture/`**: Current architecture records.
- **`docs/megaplan/`** (this directory): Historical planning. Not authoritative
  for current behavior.
