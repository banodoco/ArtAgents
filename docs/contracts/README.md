# Contracts Index

Astrid's behavior is governed by a set of normative contracts.  Each
contract defines a specific boundary — SDK surface, CLI discipline,
error signaling, output format, or ledger guarantees.

## Precedence Rule

**[platform-contract.md](platform-contract.md) is the normative v1
platform contract and wins on any disagreement with other SDK or
pack-system documents.**  When two contracts appear to conflict, the
platform contract is the final authority.

## Capability & Composition

- **[capability-artifact-contract.md](capability-artifact-contract.md)** —
  The capability/artifact/scoped-config contract: the three primitives,
  composition rule (id-reference + type-match), conceptual↔canonical
  mapping, open-string fallback (Reigh-boundary leniency), and pack
  extension via `extensions.artifact_types.types`.  The definitive guide
  for third-party pack authors shipping typed capabilities.

## Normative Contracts

- **[platform-contract.md](platform-contract.md)** — The normative v1
  SDK boundary: public exports, SemVer rules, deprecation window, DTO
  stability tiers, manifest schema contract, element extensions, and
  disclosure-only trust model.  Wins on disagreement.

- **[cli-contract.md](cli-contract.md)** — Stable contract between the
  CLI and agentic consumers: stdout/stderr stream discipline, JSON mode
  schema, exit-code taxonomy, and the verb reference for `next`,
  `status`, `start`, `abort`, `ack`, `skip`, and `attach`.

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
