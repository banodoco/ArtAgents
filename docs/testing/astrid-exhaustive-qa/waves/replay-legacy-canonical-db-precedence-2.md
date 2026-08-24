# Live replay: legacy/canonical database precedence

Date: 2026-08-24  
Mode: public CLI plus public kernel read helpers; disposable roots; no product edits

## Verdict

The canonical-authority contract holds when both ledgers coexist. Doctor names the
canonical database and the ignored legacy path, strict mode converts that warning
to `unhealthy`, and kernel reads return canonical runs only. The legacy ledger was
not merged, renamed, deleted, or rewritten.

There is one remaining public-surface friction: a legacy-only root is readable by
the kernel helpers and doctor, but a read-only public `projects list` creates a new
canonical database and then reports an empty project list. A subsequent public
`runs list --project legacy-only` reports `not_found`. This does not leak legacy
rows, but it can make an existing legacy workspace look empty and silently changes
the authority state. Treat this as a P2 migration/CLI consistency issue for a
follow-up; this replay made no product changes.

## Coexistence journey

Disposable root: `/private/tmp/astrid-db-precedence-YojxyC`

The canonical store was created through the public CLI (`projects create`,
`projects select`, `timelines create`, and `timelines visualize`). It contained
project `canonical-lab` and run
`7bff694abfac37f0cab15969e2` (`rendering.timeline_visualize`). A separate
core-only legacy `kernel.sqlite3` was written with the legitimate project
`legacy-lab` and run `01m0sv878nn33zm5g1eqbfer21` (`Legacy evidence`).

Public observations:

- `astrid doctor --projects-root ROOT --json` returned `ready`; its `data_paths`
  check explicitly said `canonical database selected: .../.astrid/astrid.sqlite3`
  and `ignored legacy database path(s): .../kernel.sqlite3`.
- The same command with `--strict-optional --json` returned `ok: false` and
  `state: unhealthy`, with the coexistence warning preserved. Strict mode did not
  erase or hide the authority warning.
- `projects list --json` returned only `canonical-lab`.
- `runs list --project canonical-lab --json` returned only the canonical
  visualization run.
- `runs list --project legacy-lab --json` returned the typed `not_found` envelope;
  no legacy run was exposed through the public canonical reader.

Direct kernel reads agreed:

```text
authority.mode = canonical
authority.selected_path = ROOT/.astrid/astrid.sqlite3
authority.existing_legacy_paths = [ROOT/kernel.sqlite3]
kernel_runs_for_project("canonical-lab") = ["7bff694abfac37f0cab15969e2"]
kernel_runs_for_project("legacy-lab") = []
kernel_run_info("legacy-lab", "01m0sv878nn33zm5g1eqbfer21") = None
```

The canonical and legacy database hashes (including WAL files) were identical
before and after doctor, public list/read commands, and direct kernel reads:

```text
canonical astrid.sqlite3  4ddb0e8969fa5e0e6302202ca5ffb641c587f3ccf96b634d00c2446b8229160c
legacy    kernel.sqlite3  3cdc4a9408df7b472c077b8678975149878478ea0e1f64ff41f0070d641f8aea
both WAL files             e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Legacy-only fallback journey

Disposable root: `/private/tmp/astrid-db-legacy-only-AEDvT6`

Only `kernel.sqlite3` existed initially, containing project `legacy-only` and run
`01m0sv9cd6dh98ar2qv4vxnq6h`.

- Before any public CLI command, `doctor --json` reported `ready` with a warning
  naming `legacy database fallback active: .../kernel.sqlite3` and
  `canonical database is absent: .../.astrid/astrid.sqlite3`.
- `doctor --strict-optional --json` reported `ok: false`, `state: unhealthy`,
  retaining the same fallback guidance.
- `resolve_kernel_database_authority` selected legacy mode, and
  `kernel_runs_for_project("legacy-only")` returned the seeded run; its
  `kernel_run_info` returned the expected `Legacy-only evidence` row.
- At this point `.astrid/astrid.sqlite3` did not exist. The legacy DB and WAL
  hashes were unchanged.

For completeness, the public CLI was then exercised. `projects list --json`
returned `data: []` and created `.astrid/astrid.sqlite3` (356,352 bytes), while
`runs list --project legacy-only --json` returned typed `not_found`. The legacy
database bytes remained unchanged (`18f3b0e1bf634ebb1ee0fae4661c08ace714e94bf6fb9b056e0b7547ed95e842`),
but this confirms the public CLI does not currently honor the helper's legacy
fallback without initializing the canonical store.

## Narrow guard

```text
python3 -m pytest -q tests/v10/test_kernel_database_precedence.py
2 passed in 0.27s
```

The guard covers canonical-over-legacy selection, ignored legacy reads, doctor
diagnostics, and legacy-only helper fallback. No product files were edited in
this live replay.
