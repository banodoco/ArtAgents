# Astrid Documentation

This is the current-docs index. It links to the canonical documentation surface
for product users, contributors, pack authors, and architecture reviewers.
Historical planning and operational records live under `docs/megaplan/` and
`docs/reshape/` — those are not current product docs.

---

## Current Product Docs

These top-level files are the current product documentation surface. They cover
the public concepts, CLI contract, SDK, pack authoring, and operational
reference material.

| Document | What it covers |
|---|---|
| [architecture.md](architecture.md) | Canonical public concepts: orchestrators, executors, elements |
| [sdk.md](sdk.md) | Python SDK walkthrough (discovery, lookup, invocation) |
| [platform-contract.md](platform-contract.md) | Normative v1 platform contract — SDK exports, SemVer, DTO stability, manifest schema, trust model |
| [cli-contract.md](cli-contract.md) | Stable CLI contract for agentic consumers (stream discipline, output modes, error signaling) |
| [error-model.md](error-model.md) | Runtime error model: exit-code taxonomy, structured errors, degraded/unexpected bug policy |
| [env-vars.md](env-vars.md) | Canonical `ASTRID_*` environment variable reference |
| [creating-packs.md](creating-packs.md) | Authoring guide — scaffold, populate, and validate packs |
| [creating-tools.md](creating-tools.md) | How to add new capabilities when Astrid is missing one |
| [pack-taxonomy.md](pack-taxonomy.md) | Machine-readable pack classification fields (maturity, domain, origin, stability) |
| [discovery-for-agents.md](discovery-for-agents.md) | How agents discover capabilities through CLI surfaces |
| [adapter-packs.md](adapter-packs.md) | How adapter packs wrap external substrates (VibeComfy, RunPod, fal.ai, Moirae) |
| [aliases-vs-forks-vs-overrides.md](aliases-vs-forks-vs-overrides.md) | Three mechanisms for redirecting or customizing capability resolution |
| [update-workflow.md](update-workflow.md) | Detecting and acting on local edits to forked capabilities |
| [personal-packs.md](personal-packs.md) | Scaffolding and managing personal packs |
| [skills-install.md](skills-install.md) | Installing Astrid prompt content as skills into Claude Code, Codex, and Hermes |
| [build-your-first-agentic-ux.md](build-your-first-agentic-ux.md) | Tutorial — discover → inspect → invoke → read-events via the public SDK |
| [output-result-contract.md](output-result-contract.md) | Universal result manifest contract for M1-adopter executors |
| [generation/](generation/) | Generation feature, registry, manifest, and modality contracts |
| [run-ledger-contract.md](run-ledger-contract.md) | M2 run ledger contract (exactly one truthful entry per execution) |
| [threads.md](threads.md) | Threads — retired user-facing concept, retained as internal lineage model |
| [HOOKS.md](HOOKS.md) | Claude Code stop hook for re-injecting task-mode rules on stop boundaries |
| [ideas.md](ideas.md) | Suggestions for what to make or learn with Astrid |
| [builtin-dataset-build.md](builtin-dataset-build.md) | How the built-in `training.dataset_build` orchestrator works |
| [ci-lanes.md](ci-lanes.md) | CI lane system exercised by `scripts/reshape/run_ci_checks.sh` |
| [giant-file-rationale.md](giant-file-rationale.md) | M4 inventory of oversized Python files targeted for decomposition |

### Draft / Vision Docs

These documents describe planned or in-progress work and are not yet normative.

| Document | Status |
|---|---|
| [generation-facade-design.md](generation-facade-design.md) | Draft: library-first generation facade |
| [git-backed-packs-plan.md](megaplan/git-backed-packs-plan.md) | Plan: Git-backed, schema-validated pack bundles (moved to megaplan/) |
| [render-adapter.md](render-adapter.md) | Active: Banodoco Remotion render adapter decision record |
| [integration_contracts.md](integration_contracts.md) | Active: Astrid–Reigh cross-repo integration contracts |
| [runtime-correctness-m3-inventory.md](runtime-correctness-m3-inventory.md) | Inventory: non-pack `except`/`assert` sites for M3 runtime correctness audit |

---

## Architecture Docs

Canonical architecture records live in `docs/architecture/`. These are current
design docs, not historical planning.

| Document | What it covers |
|---|---|
| [architecture/repo-shape.md](architecture/repo-shape.md) | Repository shape and module layout |
| [architecture/test-layout.md](architecture/test-layout.md) | Canonical test folder layout, stay-root rationale, SDK/public-contract test policy |
| [architecture/shim-legacy-audit.md](architecture/shim-legacy-audit.md) | Audit of shim/legacy compatibility layers |

---

## Pack Docs

Pack documentation is spread across several current-docs files in the root
(`creating-packs.md`, `pack-taxonomy.md`, `adapter-packs.md`,
`personal-packs.md`, `aliases-vs-forks-vs-overrides.md`) and the canonical
pack contract at [`packs/contract.md`](packs/contract.md).

See [`packs/README.md`](packs/README.md) for the pack doc index.

---

## Templates

Scaffolding templates for new orchestrators, executors, and elements:

| Directory | Contents |
|---|---|
| [templates/orchestrator/](templates/orchestrator/) | `orchestrator.yaml`, `run.py`, `STAGE.md` |
| [templates/executor/](templates/executor/) | `executor.yaml`, `run.py`, `STAGE.md` |
| [templates/element/](templates/element/) | `element.yaml`, `component.tsx`, `STAGE.md` |

---

## Examples

| Document | What it covers |
|---|---|
| [examples/training-workflow.md](examples/training-workflow.md) | End-to-end dataset build and LTX LoRA training workflow |

---

## Operational History

The `docs/megaplan/` directory is **operational history**, not current product
documentation. It preserves planning artifacts, epic briefs, milestone
handoffs, audit syntheses, and harness design records. These files are useful
for understanding why decisions were made, but they are not the current source
of truth for product behavior, contracts, or APIs.

Key entry points:

| Document | What it covers |
|---|---|
| [megaplan/README.md](megaplan/README.md) | Megaplan operational history index |
| [megaplan/agentic-pipeline.md](megaplan/agentic-pipeline.md) | Agentic pipeline design record |
| [megaplan/parallel-runner.md](megaplan/parallel-runner.md) | Parallel runner design record |
| [megaplan/loose-work-consolidation-plan.md](megaplan/loose-work-consolidation-plan.md) | Loose work consolidation plan |
| [megaplan/agentic-state-mutation-coverage.md](megaplan/agentic-state-mutation-coverage.md) | Agentic state mutation coverage record |
| [megaplan/epics/](megaplan/epics/) | Epic briefs and milestone documents (pack-system, harness-polish, builtin-training, etc.) |

The `docs/reshape/` directory preserves Sprint 0–3 reshape planning artifacts,
spike findings, regression baselines, and handoff records. See
[reshape/README.md](reshape/README.md) for the canonical Sprint 0 operator
surface.

---

## Root vs. History Distinction

- **`docs/*.md` (root)**: Current product, contributor, and architecture docs.
  These are the canonical source of truth for how Astrid works today.
- **`docs/architecture/`**: Current architecture records (repo shape, test
  layout, shim audit). Also current, not historical.
- **`docs/templates/`**: Living scaffolding templates. Current.
- **`docs/megaplan/`**: Historical planning. Epic briefs, audit syntheses,
  milestone handoffs, harness design records. Valuable for context, but not
  authoritative for current behavior.
- **`docs/reshape/`**: Historical sprint artifacts. Spike findings, regression
  baselines, sprint handoffs. Not current operating guidance.
