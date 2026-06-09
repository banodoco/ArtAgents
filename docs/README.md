# Astrid Documentation

Astrid is a Python SDK and harness toolkit for building and running agentic UXes —
pipelines where agents and humans collaborate to make art.

## Which journey matches you?

### I'm new here

Start with **[Getting Started](getting-started.md)** to install, run your first
command, and get oriented.  Then follow
**[Build Your First Agentic UX](guides/build-your-first-agentic-ux.md)** — a
step-by-step tutorial through discover → inspect → invoke → read-events via the
public SDK.

### I want to author packs

Pack authoring docs live under **[docs/packs/](packs/)**.  Start with the
**[pack contract](packs/contract.md)** for vocabulary and identity rules, then
**[Creating Packs](packs/creating-packs.md)** for the scaffold → populate →
validate workflow.

### I'm building agentic consumers

If you're building AI agents that consume Astrid capabilities, start with
**[Discovery for Agents](guides/discovery-for-agents.md)** for how agents discover the
capability registry, then the **[SDK Reference](reference/sdk.md)** for the DTO catalog,
and the **[Platform Contract](contracts/platform-contract.md)** for the normative v1 SDK
boundary.

### I'm contributing to Astrid

Contributor-facing architecture docs live under
**[docs/architecture/](architecture/)**.  See
**[Repo Shape](architecture/repo-shape.md)** for module layout,
**[Test Layout](architecture/test-layout.md)** for test organization, and
**[Decisions](architecture/decisions.md)** for design records.

## Reference

- **[Contracts Index](contracts/README.md)** — Every normative contract: platform, CLI,
  error model, output result, run ledger.
- **[Generation Subsystem](generation/README.md)** — Multi-modal generation
  (image, video, audio) registry, manifest, and modality contracts.
- **[CLI Contract](contracts/cli-contract.md)** — Stable stdout/stderr discipline, JSON
  mode, exit codes.
- **[Error Model](contracts/error-model.md)** — Exit-code taxonomy and structured error
  envelopes.
- **[Environment Variables](reference/env-vars.md)** — Canonical `ASTRID_*` reference.
- **[Creating Tools](guides/creating-tools.md)** — Adding new capabilities.
- **[Skills Install](guides/skills-install.md)** — Installing Astrid prompt content as
  skills into Claude Code, Codex, and Hermes.
- **[HOOKS](guides/hooks.md)** — Claude Code stop hook for re-injecting task-mode rules.
- **[Ideas](guides/ideas.md)** — Suggestions for what to make or learn with Astrid.

## Examples

- **[Training Workflow](examples/training-workflow.md)** — End-to-end dataset
  build and LTX LoRA training workflow.

## Templates

Scaffolding templates for new orchestrators, executors, and elements live under
**[docs/templates/](templates/)**.
