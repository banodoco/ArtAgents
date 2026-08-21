# Astrid Documentation

Astrid is a Python SDK and harness toolkit for building and running agentic UXes —
pipelines where agents and humans collaborate to make art.

**Where to start:** agents begin at [AGENTS.md](../AGENTS.md) +
[`astrid/packs/_core/skill/SKILL.md`](../astrid/packs/_core/skill/SKILL.md);
humans begin at [Getting Started](getting-started.md).

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
- **[Debugging Renderers](guides/debugging.md)** — Validating, smoking, and
  debugging pluggable timeline renderers; the failure replay bundle.
- **[Render Backend v1](contracts/render-backend-v1.md)** — The protocol-v1
  pluggable renderer contract and the renderer-author golden path.
- **[Skills Install](guides/skills-install.md)** — Installing Astrid prompt content as
  skills into Claude Code, Codex, and Hermes.
- **[HOOKS](guides/hooks.md)** — Retired task-mode stop hook (documented as a retired notice).
- **[Ideas](guides/ideas.md)** — Suggestions for what to make or learn with Astrid.

## Examples

- **[Training Workflow](examples/training-workflow.md)** — End-to-end dataset
  build and LTX LoRA training workflow.

## Templates

Scaffolding templates for new orchestrators, executors, and elements live under
**[docs/templates/](templates/)**.
