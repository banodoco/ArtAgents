# Pack Documentation

This directory is the canonical home for pack documentation. The pack contract
defines the model; authoring and reference guides build on it.

## Canonical Pack Contract

- **[contract.md](contract.md)** — M0 pack contract: vocabulary, capability
  identity, pack axes, discovery contract, manifest convergence, first placement
  map, and deferred scope.

## Authoring & Reference

Pack authoring and reference docs live at the `docs/` root alongside other
current product docs:

- **[creating-packs.md](../creating-packs.md)** — Authoring guide: scaffold,
  populate, and validate packs.
- **[pack-taxonomy.md](../pack-taxonomy.md)** — Machine-readable pack
  classification fields (maturity, domain, origin, stability).
- **[adapter-packs.md](../adapter-packs.md)** — How adapter packs wrap external
  substrates (VibeComfy, RunPod, fal.ai, Moirae).
- **[personal-packs.md](../personal-packs.md)** — Scaffolding and managing
  personal packs.
- **[aliases-vs-forks-vs-overrides.md](../aliases-vs-forks-vs-overrides.md)** —
  Three mechanisms for redirecting or customizing capability resolution.

## Historical Source

The pack contract was originally authored at
`docs/megaplan/epics/pack-system/pack-contract.md`. That file now contains only a
pointer to the canonical location here.
