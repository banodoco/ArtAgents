# Project orientation UX fix

Date: 2026-08-23 (UTC)

## Verdict

**PASS. The root project-orientation findings and replay defects are fixed
with no new cross-project mutation or routing leak observed.**

The former `projects select` preference is now an inspectable, operational
selection. `projects current` resolves and verifies it, reports the canonical
project path plus the preference path and supplying scope, and all project-
scoped CLI families may omit `--project` to use it. Workspace selection has
deterministic precedence over user selection; an explicit `--project` always
wins. A stale or absent selection fails closed with structured recovery
details.

Severity-ranked outcome:

1. **P1 fixed — inert selection.** `select` persists a validated slug and
   `current` reads it back. Omitted project-scoped CLI commands route through
   that selection; explicit refs remain authoritative.
2. **P2 fixed — opaque project identity/errors.** Project DTOs now include the
   canonical workspace path. Duplicate slugs, duplicate display-name refs,
   human-name refs, nonexistent refs, and wrong-project timeline refs return
   structured details, candidates where applicable, and retry guidance.
3. **P2 fixed — replay error quality.** Corrupt selection JSON now fails as a
   typed `validation_error` with scope, preference path, and repair/reselect
   guidance. Timeline human-name and malformed refs now return expected forms,
   candidates where available, and retry guidance. Duplicate human names
   remain allowed by contract, but all ambiguous names fail closed; agents
   should use immutable slugs or ids for mutations.

## Contract implemented

- `projects create`, `show`, `update`, `list`, `select`, and `current` expose
  canonical project paths in their SDK DTOs where a project is returned.
- `projects select <ref> [--scope workspace|user]` returns the selected project
  and a `selection` object containing `ref`, `scope`, and preference `path`.
- `projects current` returns the verified project plus the selection source.
  Workspace scope wins over user scope. Missing selection, malformed
  preference, and stale selection are typed JSON errors with recovery details.
- Product CLI project arguments are optional and resolve through the selected
  project. Explicit `--project` is unchanged and wins over selection.
- Project display names are never treated as addressable identifiers. Exact
  name matches produce candidate slugs/ids; duplicate names produce all
  candidates and a fail-closed validation error.
- Duplicate project/timeline slugs, nonexistent project refs, and a timeline
  ref used in the wrong project have structured `field`/`entity`/`ref` details
  and public retry guidance.
- Malformed selection JSON is never treated as an internal error and never
  silently routes an operation. `projects current` and omitted project-scoped
  commands return `validation_error` with scope, canonical preference path,
  and repair/reselect guidance.
- Timeline display-name refs are never silently accepted. One matching name
  returns its candidate id/slug/ULID; multiple matches return all candidates;
  an invalid non-name ref returns the canonical UUID/ULID/slug forms expected.

## Fresh live proof

The proof used a new disposable `ASTRID_PROJECTS_ROOT` and two independent
shell working directories, with the suite-only workspace-config override
removed. It created:

```text
alpha -> display name "Same Name"
beta  -> display name "Same Name"
```

Observed public results:

```text
shell-a: projects current -> alpha, scope=workspace
shell-b: projects current -> beta,  scope=workspace
shell-a: timelines create alpha-main (no --project) -> alpha-main
shell-b: timelines create beta-main  (no --project) -> beta-main
shell-a: timelines list (no --project) -> [alpha-main]
shell-b: timelines list (no --project) -> [beta-main]
shell-a: timelines list --project beta -> [beta-main]  # explicit wins
```

Using `alpha-main` with `--project beta` returned exit 1,
`not_found`, with timeline/project recovery details and no mutation.
`projects show "Same Name"` returned exit 1, `validation_error`, with both
candidate ids/slugs. `projects show does-not-exist` returned exit 1,
`not_found`, with `projects list --json` recovery guidance. The disposable
root was removed after the final public reads.

A second fresh disposable proof specifically replayed the two defects. A
corrupted workspace config returned `validation_error` (not
`internal_error/ProjectJsonError`) with `scope: workspace`, the preference
path, and reselect guidance; an omitted `timelines list` also failed closed
with the same typed error. Two timelines sharing `Same Human Name` produced
an ambiguous-name validation error with both ids, slugs, and ULIDs, while
`not a timeline` produced the expected UUID/ULID/slug list and list/retry
guidance. That root was also removed.

The replay proof also exercised the documented recovery: repeating
`projects select alpha` replaced the corrupt disposable preference with a
minimal valid selection, after which `projects current` returned Alpha again.

## Verification

Passing focused suite:

```text
107 passed in 47.70s
```

This covers the orientation regressions, malformed-preference fail-closed
routing, timeline resolver errors, project SDK behavior, preference
precedence, and project/timeline CLI parser and dispatch behavior. Relevant
changed modules also pass `python3 -m compileall -q`.

The wider worktree contains unrelated concurrent changes; previously observed
failures in project-repository/public-surface suites were outside this
contract and were not used to alter unrelated product code.

## Main changed surfaces

- `astrid/core/preferences.py` — selection provenance and precedence.
- `astrid/sdk/projects.py`, `astrid/sdk/client.py` — current/read-back,
  canonical paths, and selection routing support.
- `astrid/core/cli/domain_projects.py` and
  `astrid/core/cli/domain_product.py` — public current command and omitted
  project routing.
- `astrid/core/repositories/projects.py` and `astrid/sdk/exceptions.py` —
  address resolution and structured errors.
- `astrid/packs/timeline/repository.py` and `astrid/sdk/exceptions.py` —
  timeline display-name ambiguity and identifier-form diagnostics.
- Project-scoped family parsers and public getting-started/skill/CLI journey
  docs — optional project selection and recovery guidance.
- `tests/sdk/test_project_orientation_ux.py` plus updated focused expectations.
