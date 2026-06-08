# Runtime Correctness M3 Inventory

Generated inventory of non-pack `astrid/` Python `except` and runtime `assert` sites.

## Summary

- AST sites inventoried: 744 (742 `except`, 2 `assert`).
- Grep lexical hits after the same source exclusions: 759.
- AST sites not present as direct grep hits: 0. These are parser-normalized multi-line handlers/asserts or sites whose keyword line differs from the AST node line; AST remains authoritative.

## Seed-File Non-Fixed Reasons

- `astrid/gateway.py`: Seed inventory row. Non-fixed AST sites in this file: 5. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/task/run_audit.py`: Seed inventory row. Non-fixed AST sites in this file: 21. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/orchestrate/cli.py`: Seed inventory row. Non-fixed AST sites in this file: 12. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/threads/provenance.py`: Seed inventory row. Non-fixed AST sites in this file: 4. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/skills/__init__.py`: Seed inventory row. Non-fixed AST sites in this file: 3. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/skills/discovery.py`: Seed inventory row. Non-fixed AST sites in this file: 3. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/skills/harnesses/base.py`: Seed inventory row. Non-fixed AST sites in this file: 2. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/audit/context.py`: Seed inventory row. Non-fixed AST sites in this file: 2. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/session/binding.py`: Seed inventory row. Non-fixed AST sites in this file: 4. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/session/cli.py`: Seed inventory row. Non-fixed AST sites in this file: 0. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.
- `astrid/core/task/gate.py`: Seed inventory row. Non-fixed AST sites in this file: 1. Existing broad/error-handling behavior remains classified for follow-up rather than changed during this split.

## Deferred Tickets

- M3-INV-001: Follow up on deferred runtime correctness inventory rows after the split milestones settle.

## Planned Runtime Assert Conversions Completed

- `astrid/core/executor/install.py:239`: completed
- `astrid/core/executor/install.py:245`: completed
- `astrid/core/runpod/sweeper.py:149`: completed
- `astrid/core/session/cli.py:711`: completed

## Inventory

### `astrid/audit/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 41 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/audit/context.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 52 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 56 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/audit/transport.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 58 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 95 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 160 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/audit/util.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/contracts/capability_runner.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 116 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 141 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 144 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/contracts/run_status.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 119 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 136 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 150 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/contracts/schema_validators.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 22 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/adapter/local.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 47 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 61 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 86 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 93 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 97 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 115 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 158 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/adapter/manual.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 114 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/adapter/remote_artifact.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 33 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 89 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 148 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 154 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 157 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 170 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/dirty.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 37 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 91 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 116 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/element/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/element/registry.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 94 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 283 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 298 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/element/schema.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 263 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 294 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/banodoco_catalog.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 70 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 63 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/folder.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 104 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 115 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/install.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 170 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/registry.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 371 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/runner.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 188 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 547 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 560 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/executor/schema.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 284 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 286 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 290 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 801 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 804 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/backends/base.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 34 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 41 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 60 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/backends/codex.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 157 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 159 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/backends/fal.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 143 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 298 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/backends/registry.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 107 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 211 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/generation/verbs.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 109 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/git_util.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 51 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 75 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 132 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 134 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/lineage/variants.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 38 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 166 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 195 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 241 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 269 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 363 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 376 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/model_catalog/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 72 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 91 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 190 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 199 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/model_catalog/registry.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 51 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 184 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/model_catalog/schema.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 318 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 68 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/folder.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 66 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 94 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 105 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/registry.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 328 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 342 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 460 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/runner.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 178 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 263 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 270 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 272 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 362 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 373 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 454 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/orchestrator/schema.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 173 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 177 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/__init__.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 324 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 1035 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 1040 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 1051 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 1053 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/agent_index.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 65 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 106 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 111 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 116 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 342 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 364 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/alias_resolver.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 71 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 171 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 182 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/cli_inspect.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 68 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 82 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 324 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 386 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 458 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/entrypoint.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 89 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 91 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 99 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/gitignore.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 150 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 202 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/install_git.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 80 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 85 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 89 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 123 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 128 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 167 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 178 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 213 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 241 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 279 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 333 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 417 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 441 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 484 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 510 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 543 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/install_local.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 133 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 181 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 267 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 340 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 373 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 393 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 750 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 771 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 886 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 903 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 946 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 1008 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 1011 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/install_trust.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 41 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 194 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 211 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/manifest.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 30 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 37 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/override.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 87 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/resolver.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 23 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 66 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 70 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/store.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 34 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 128 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 178 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 213 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 235 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 261 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 310 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 314 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 406 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 422 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 426 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 428 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/validate.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 293 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 320 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 334 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 377 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 585 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 621 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 631 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 658 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 834 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 855 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 909 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 990 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/pack/validate_layout.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 312 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 376 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 428 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 72 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 501 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 544 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 653 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 758 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 777 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 840 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 907 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 963 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 1016 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/current_run.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 53 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 117 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/jsonio.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 29 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 31 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 33 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 44 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/project.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 259 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 268 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/run.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 125 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 345 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 372 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 555 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 649 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 660 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 712 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 722 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/schema.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 262 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 309 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/project/sidecar.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/data_provider.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 336 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/supabase_client.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 70 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 86 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 108 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 115 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 124 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/task_client.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 79 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 81 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 118 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/timeline_io.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 216 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 287 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 312 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/reigh/worker_jwt.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 61 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 72 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 87 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/runpod/sweeper.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 60 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 101 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 149 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 215 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 263 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 293 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 316 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 352 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 376 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/runtime/in_process.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 136 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 215 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 217 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/runtime/log_capture.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 55 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 177 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/scaffold.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/binding.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 152 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 185 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 192 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 197 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/cli_attach.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 112 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 122 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 135 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 174 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 296 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/cli_sessions.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 106 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 181 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 221 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 231 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 262 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 277 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 333 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 350 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 399 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/cli_status.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 86 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 212 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 264 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 338 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 373 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/config.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 28 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/identity.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 49 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 83 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 90 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/lease.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 89 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 94 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 98 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 327 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 332 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 336 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/lifecycle.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 299 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/session/model.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 88 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 125 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 129 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 143 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/claim.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 236 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 242 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 272 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 303 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 333 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/command_render.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 135 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/events.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 186 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 188 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 251 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 295 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 311 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 335 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 337 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 339 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 886 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 917 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 919 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 923 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 943 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/gate.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 576 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/gate_attestation.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 66 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 107 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/gate_dispatch.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 118 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/gate_finalize.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 246 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/gate_repeat.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 111 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 217 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 361 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 493 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/hook.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 50 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 56 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 66 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 72 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/inbox.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 274 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 301 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 310 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 431 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 568 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 599 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/lifecycle_ack.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 175 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 189 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 233 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 273 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 358 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 383 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 420 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 469 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/lifecycle_skip.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 113 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 127 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 207 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 212 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 217 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/operator_render.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 185 | `assert` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 289 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/operator_view.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 140 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 145 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 301 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 347 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 376 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 419 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 459 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 784 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 791 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/orchestrator_resolver.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 83 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 113 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/plan.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 327 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 422 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 532 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 534 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 536 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 911 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/plan_builder.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 269 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 274 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 279 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 293 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 326 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 361 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 368 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 388 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 400 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 441 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/plan_verbs.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 415 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 418 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 458 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 494 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 523 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 575 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/run_audit.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 37 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 42 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 175 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 180 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 231 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 252 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 263 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 306 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 311 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 372 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 377 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 459 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 464 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 545 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 550 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 576 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 581 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 633 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 645 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 702 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 822 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/run_gc.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 109 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 147 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 163 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 218 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 225 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 300 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/run_store.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 97 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 119 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 124 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 149 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 211 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 235 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 241 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 296 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/session_discovery.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 29 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 71 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 153 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 183 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/task/validator.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 73 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 82 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 101 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 158 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 177 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/theme.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 66 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/_edit_helpers.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 127 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 129 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/banodoco_schema.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 46 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 538 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 611 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/branch.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 166 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 296 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 377 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 41 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 43 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 47 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 143 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/cli_backends.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 42 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 83 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 128 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 164 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 205 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 271 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 280 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 331 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 369 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 409 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 443 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 491 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 527 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 569 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 611 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/cli_crud.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 290 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/cli_edits.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 60 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 111 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/cli_events.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 56 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 269 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 334 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 406 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 414 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 448 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 474 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 483 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 493 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 594 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 609 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 624 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 661 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/crud.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 15 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 176 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 186 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 627 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/erasure.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 321 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 338 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 340 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/eventlog/local_fs.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 166 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 188 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 244 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 270 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 275 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 288 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 324 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 326 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 344 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 401 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 403 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 405 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 450 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/eventlog/selector.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 372 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/eventlog/supabase.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 225 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/events/schema/types.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 800 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 1012 | `assert` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/integrity.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 59 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/inverses.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 828 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 945 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/migration.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 166 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 176 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 394 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 470 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 561 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/model.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 25 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 32 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 39 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 47 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/observability.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 97 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 148 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 159 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 188 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 202 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/operations.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 283 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 404 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/paths.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 108 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 122 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 142 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 170 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 176 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 212 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 227 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 265 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 269 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 289 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 295 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 305 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 309 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 315 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/projection.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 169 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 260 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 726 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 980 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/repair.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 158 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 193 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 195 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 243 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 289 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 300 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/transfer.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 287 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 289 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 302 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/timeline/undo.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 193 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 285 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 307 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 343 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 366 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/update.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 57 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/util/atomic_io.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 28 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 92 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 104 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 140 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 142 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 144 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/util/http.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 127 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 134 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 191 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 200 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/util/log_and_swallow.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/util/png_metadata.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 55 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 92 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 102 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/core/worker/banodoco_worker.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 319 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 348 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 375 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 391 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 410 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 423 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 452 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 508 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/doctor.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 126 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 411 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 448 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 687 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 689 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 691 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/domains/hype/enriched_arrangement.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 95 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 303 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/gateway.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 176 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 178 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 207 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 243 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 279 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/gateway_dispatch.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 71 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 303 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 398 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 531 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 552 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 570 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 589 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/gateway_help.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 24 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/gateway_project.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 124 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/gateway_wait.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 58 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 61 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 64 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 68 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 113 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/modalities/__init__.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 112 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 119 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 130 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 216 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 228 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 287 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 331 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 340 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 366 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 474 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 499 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 584 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/compile.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 71 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/dsl.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 184 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 191 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 506 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/orchestrate/test_runner.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 139 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 244 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/sdk.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 150 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 152 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 176 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 178 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 196 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 198 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/sdk_discovery.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 436 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 457 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 482 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 511 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 523 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 534 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 562 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 566 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 577 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/sdk_generation.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 162 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 207 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 286 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/sdk_invocation.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 298 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 300 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/__init__.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 347 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 417 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 430 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 32 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/discovery.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 69 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 103 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 175 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/base.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 73 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 141 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/claude.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/codex.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 95 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 113 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/harnesses/hermes.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 109 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 129 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 150 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 154 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 161 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/skills/state.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 48 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/structure.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 111 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 114 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 155 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 158 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 286 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 327 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 330 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 440 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 482 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 512 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 563 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 569 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 596 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 719 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 807 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 838 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 882 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/theme_schema.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 204 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 206 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/attribute.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 144 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 228 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 279 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 285 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 299 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 367 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 375 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 390 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 396 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 398 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 420 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/cli.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 118 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 209 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 214 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/index.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 91 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 96 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 131 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 141 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/provenance.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 45 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 56 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 116 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 141 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/record.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 193 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 211 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 227 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 257 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 324 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/schema.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 215 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/threads/variants.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 40 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 51 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 168 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 196 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 242 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 270 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 364 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 377 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/utilities/llm_clients.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 75 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 77 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 131 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 277 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 375 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 395 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |

### `astrid/verify/checks.py`

| Line | Kind | Context | Status | Reason |
| --- | --- | --- | --- | --- |
| 74 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 89 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 91 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 95 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 108 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 110 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 112 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 175 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 283 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 291 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 293 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 295 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 297 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 323 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 325 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
| 368 | `except` | runtime-correctness | `justified-with-caveat` | Classified inventory row retained after M3/M4 layout splits; behavior unchanged and reviewed as non-pack runtime surface. |
