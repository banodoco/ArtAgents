# Explore: docs/contract drift

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-packification-oracle

Explore the docs for stale claims vs reality. Start from:
- docs/packs/contract.md (pack contract; line 9 "Every discoverable executor, orchestrator, and element belongs to a pack")
- docs/packs/pack-taxonomy.md (six taxonomy fields; claims about _core — "permanent visible exception" ~290-313; claim that skills "explicitly skip _core"; claim builtin is visibility:hidden)
- docs/packs/creating-packs.md, docs/packs/adapter-packs.md
- docs/architecture/repo-shape.md (esp. §2 describing integrations/generation backends/experiments as core-by-default; §4-5 pack layout, legacy dirs), docs/architecture/import-tiers.md
- docs/contracts/render-backend-v1.md, docs/contracts/experiment-contract.md, docs/contracts/platform-contract.md
- astrid/packs/builtin/pack.yaml (is visibility: hidden set? status?), astrid/packs/_core/skill/SKILL.md
- .oracle-threejs-archive/plan.md and/or .oracle-threejs-archive/tasklist.md may contain the previous megado run's doc-drift findings — reuse if present

Report verified facts with file:line evidence: (1) every doc claim that contradicts the code (quote both sides); (2) what a locked "kernel table" in contract.md should contain given the code (gateway, session, project, task engine, pack system, registries, SDK, skills installer, structure/doctor, foundation/contracts, timeline store, render protocol, generation protocol); (3) which docs must change when _core becomes a pack, when legacy_workspace dies, when first-party allowlist refreshes. Produce an exact edit list (file → change) for the docs. Ranked findings, <300 words.
