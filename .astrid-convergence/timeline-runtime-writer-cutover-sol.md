# Timeline runtime-writer cutover evidence

Branch: `codex/zero-shim-timeline-cutover-sol`  
Base: `e080c1dc78960fa3dee04d082cea5b43cc57a6a3`

## Boundary result

- Runtime timeline writes remain behind `AstridClient.timelines.save(...)` with
  an explicit `expected_version`, or the generic host's predeclared settlement
  effect.
- Cut, refine, and assemble are result-only task workers. They emit typed
  attempt artifacts and have no project/timeline mutation flags, event append,
  runtime client, storage backend, or projection writer.
- Cut's inherited unconditional retirement exception was removed. Its
  pure-generative and runtime-materialized-file paths work again without URL,
  workspace, or project-directory fallback.
- The filesystem event-log backend, timeline path selector, local CRUD/repair,
  and live snapshot selectors were already absent at the integrated base. This
  cutover removes their remaining writer-facing protocol/types/edit/branch/
  erasure/undo reachability and the `assembly.json` projection writer.

## Verification

- Focused worker/authority suite: `82 passed, 1 skipped, 2 subtests passed`.
- Pure cut transformations: `27 passed, 2 subtests passed`.
- Pure timeline projection/inverse/integrity contracts: `97 passed, 8 subtests passed`.
- Timeline error/cycle contracts: `59 passed`.
- Manifest/discovery validation: `38 passed`.
- Media plus timeline zero-shim/static authority checks: `52 passed`.
- Full collection: `4756 collected`, with eight remaining collection errors
  confined to the separately owned timeline snapshot/visualizer handoff lane.

