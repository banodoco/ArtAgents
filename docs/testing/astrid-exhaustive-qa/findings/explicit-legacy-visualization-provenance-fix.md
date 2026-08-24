# Explicit legacy visualization provenance fix

Date: 2026-08-24  
Severity: P2  
Status: fixed and live-replayed

## Defect

An explicit contained `timelines visualize --timeline-source <assembly.jsonl>`
correctly read the legacy filesystem event log, but its evidence manifest
always emitted `inputs.source_mode:"project"`. When a canonical kernel
timeline had the same slug, the manifest's compatibility
`timeline_source:[project_slug]` could not distinguish the two authorities.

## Root cause

The evidence-pack builder hardcoded one mode instead of receiving the already
known executor selection path. Timeline identity itself was correct, so this
was provenance labeling rather than source resolution corruption.

## Correction

The executor now passes the resolved boundary into the pack builder:

```text
explicit timeline_source -> legacy
canonical selector/default/all -> kernel
from_view navigation -> frozen
```

The manifest schema accepts all three. The former optional `project` value is
also retained solely so frozen v1 packs created before this correction remain
valid. Exact `resolved_project` and `resolved_timelines` fields remain
authoritative identity evidence; the historical field is unchanged.

## Proof

In a fresh project with same-slug divergent authorities:

- explicit legacy run `3cdced609016543c2c4ae075a9` emitted `legacy`, UUID
  `ed70ef66-43da-4182-9f14-69361c6c5e10`, ULID
  `01KYPVKMW5STB4W6FE05ED8242`, head version 159;
- no-flag run `8b829f3aadb61c9ef4623541d5` emitted `kernel`, UUID
  `34af4a64-e620-5562-8795-8cca5acdae02`, ULID
  `K1T5FYW5BTWM90EP6GNPR5PN00`, head version 1;
- exact legacy replay returned the same identity and durable manifest;
- kernel show/history/diff and every legacy fixture file remained unchanged;
- a foreign assembly path failed before admission with null IDs and no run
  count increase;
- 29 focused manifest/schema checks passed.

Full live evidence is in
`docs/testing/astrid-exhaustive-qa/waves/live-explicit-legacy-timeline-source-2.md`.

