# Contracts Index

Astrid's behavior is governed by a set of normative contracts.  Each
contract defines a specific boundary — SDK surface, CLI discipline,
error signaling, output format, or ledger guarantees.

## Precedence Rule

**[platform-contract.md](platform-contract.md) is the normative platform
contract for the public SDK and strict-v2 pack grammar.** When contracts
appear to conflict, that document and the canonical pack contract are the
authorities.

## Capability & Composition

- **[capability-artifact-contract.md](capability-artifact-contract.md)** —
  The capability/artifact/scoped-config contract: the three primitives,
  composition rule (id-reference + type-match), conceptual↔canonical
  mapping, open-string fallback (Reigh-boundary leniency), and pack
  extension via `extensions.artifact_types.types`.  The definitive guide
  for third-party pack authors shipping typed capabilities.

## Normative Contracts

- **[platform-contract.md](platform-contract.md)** — Public SDK boundary,
  strict-v2 canonical pack manifests, typed projections, and disclosure-only
  trust model. Wins on disagreement.

- **[cli-contract.md](cli-contract.md)** — Stable eight-family CLI boundary:
  stdout/stderr discipline, JSON mode, exit codes, nested
  manifest-declared mounts, and operational doctor/backup commands.

- **[error-model.md](error-model.md)** — Runtime error policy: the
  canonical three-code exit taxonomy (0=success, 1=degraded bug,
  2=recoverable failure), the `AstridError` envelope contract, rendering
  rules, recovery-command expectations, and authoring rules.

- **[output-result-contract.md](output-result-contract.md)** — Universal
  result manifest (`manifest.json`) contract for M1 executors: required
  fields, kind vocabulary, output entry hashing, directory tree hashing,
  optional partial outputs, and domain-manifest coexistence.

- **[run-ledger-contract.md](run-ledger-contract.md)** — Ledger
  invariant that every in-band execution produces exactly one truthful
  `run.json` entry: three-record taxonomy, exemption catalog, cost
  source precedence, log capture rules, cleanup verbs, and external
  `out=` semantics.

## Timeline & Event Contracts

Timeline and event-sourcing schemas live under
[docs/architecture/timeline-event-sourcing/](../architecture/timeline-event-sourcing/):
M1 schema, M2 clip primitives, M3 secondary primitives, M5 concurrency,
and M6 sync contracts.

## Pack Contract

The pack vocabulary and discovery contract lives at
[docs/packs/contract.md](../packs/contract.md).  It defines capability
identity, pack axes, manifest convergence, and the current pack listing.
