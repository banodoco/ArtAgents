# Project-authority census lane

Base: Astrid `266c033c` (runtime contract `775ee3b`).

This lane removes the local SQLite/store/repository graph, local receipt/event
services, CAS module, kernel database reader, project-tree CRUD, and timeline
kernel-writer bridge.  Metadata commands remain runtime-client adapters.

## Coverage retained or replaced

| Former v10 family | Replacement evidence | Result |
| --- | --- | --- |
| Projects | `tests/v10/test_domain_cli_projects_timelines.py`, `tests/stage1/test_core_import_authority.py` runtime CLI and no-tree probe | 211 CLI tests and 100 stage1 tests pass |
| Media | `tests/v10/test_domain_cli_media_references.py`, SDK/runtime cutover tests | included in 211 CLI passes |
| Tasks/runs | `tests/v10/test_domain_cli_tasks_runs.py`, `tests/stage1/test_remote_task_project_scope.py` | included in 211 CLI passes |
| Receipts/events | `tests/stage1/test_events_runtime_cutover.py`, generated-client cutover tests, pure receipt contract tests | stage1 passes |
| References/shots | `tests/v10/test_domain_cli_media_references.py` and project/timeline CLI cohort | included in 211 CLI passes |
| Timeline | runtime timeline CLI tests plus retained pure timeline model/event tests; local CRUD/repository tests removed because their authority no longer exists | collection succeeds with pinned schema path |
| Crash/race/durability | runtime generated-client and iteration/runtime acceptance cohorts remain; SQLite writer/UOW-only tests removed | no deleted-authority imports in source |

The deleted tests were limited to tests whose subject or fixture graph directly
required removed local repositories, SQLite UOW/writers, project-tree CRUD, or
the timeline kernel binding.  Runtime-facing CLI and contract tests were
restored after the initial collection review.

## Verification

- `PYTHONPATH=.:../reigh-app/vendor/timeline-schema/python python3 -m pytest --collect-only -q`: 5,026 collected.
- Focused authority/runtime cohort: 100 passed.
- Runtime-facing product CLI cohort: 211 passed.
- Broad run reached 100%; remaining failures are unrelated baseline lanes: CI
  sandbox subprocess JSON output, frozen timeline hash fixture, generic-provider
  generated-client fixture methods, and release-identity seed fixtures.
- Product source scan has no imports of `core.store`, `core.repositories`,
  `core.kernel.read`, `core.io.cas`, local receipt/event services, or the
  removed project CRUD modules.
