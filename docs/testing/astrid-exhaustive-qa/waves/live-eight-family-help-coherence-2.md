# Live eight-family help coherence wave 2

Date: 2026-08-24

## Scope and method

This was a fresh-agent, public-surface pass. I began with `python3 -m astrid
--help`, then used `help`, each of the eight family help screens, and the
nested `timelines shots` and `media references` help screens. I did not use
private SDK calls or inspect implementation to construct the journeys. Live
commands ran with disposable `ASTRID_PROJECTS_ROOT` directories; help
side-effect checks compared the complete root directory before and after the
help-only pass.

The eight family census is present and stable: `projects`, `timelines`,
`media`, `tasks`, `runs`, `serve`, `doctor`, and `backup`. The root help and
product help both describe the same family set, and the family help screens
expose the following public verbs:

| Family | Verified verbs |
| --- | --- |
| projects | create, list, show, update, select, current |
| timelines | create, list, show, save, archive, unarchive, history, diff, visualize, render, shots |
| media | import, list, show, verify, relocate, relate, references |
| tasks | create, list, show, cancel, retry, events |
| runs | list, show, cancel, retry-failed, events |
| serve | serve options and clean startup/shutdown |
| doctor | diagnostics and JSON state/checks/next_action |
| backup | create and restore |

## Live evidence

Fresh help-only root: `/private/tmp/astrid-help-sideeffect-3yrTb2`. Root
`--help`, product `help`, all eight family help screens, and nested timeline
shots/media references help left the root empty. This confirms that cold-start
discovery does not create a project, database, receipt, or config file.

Fresh live root: `/private/tmp/astrid-eight-live-Bqq7EQ`. The following compact
journey completed through the public CLI:

* `doctor --json` correctly reported `ok: true, state: "uninitialized"`.
* `projects create`, `projects select`, and `projects current` succeeded.
* `timelines create primary` succeeded with a minimal renderable canonical
  config; `timelines visualize primary --format md --filmstrip off` succeeded
  before the reference cross-check below.
* `media import` of a generic fixture, `media verify`, `media references
  create`, and `timelines shots create` succeeded.
* `tasks create` for `rendering.timeline_visualize` and `runs list` succeeded.
* `backup create` produced the documented human-readable backup summary.
* `serve --host 127.0.0.1 --port 0 --no-open-editor` announced its bridge,
  then terminated cleanly with return code 0.
* `backup restore` into a second disposable root succeeded; doctor reported a
  ready project and the restored media/workspace state.

The timeline save example in `docs/guides/cli-journeys.md` was also replayed.
Its former `{width,height}` config was accepted as a draft but then failed at
visualization because it lacked canonical `tracks` and `clips` arrays. The
example now uses a minimal renderable config and includes copyable visualize
and render commands.

## Contract/help corrections

The product help summary was stale: it omitted `projects current`,
`timelines unarchive`, `timelines visualize`, and `timelines render`. Those
summaries now match the family help screens. The core skill, CLI contract, and
CLI journey guide now carry the same verb inventory and first-run order.

The old global help wording claimed that `--json` always emitted the exact
five-key SDK envelope. Live replay showed the intentional exceptions:

* product and nested commands emit the five-key
  `ok/data/error/receipt/idempotency_key` envelope;
* `doctor --json` emits its diagnostic object (`ok`, `state`, `checks`, and
  `next_action`);
* `serve` and `backup` do not expose a `--json` flag.

Help, the core skill, and the CLI contract now state that distinction. The
first-run guide now puts doctor after the census and explains that a pristine
root is `uninitialized`, not unhealthy.

## Cross-family issue found during the wave

There is one separate runtime defect that prevents an unqualified PASS. In
both `/private/tmp/astrid-eight-live-Bqq7EQ` and an independent fresh replay,
the sequence `media references create` followed by
`timelines visualize primary --format md --filmstrip off --layout linear`
failed with:

```
database contains applied migrations for pack 'references', which is not registered in this composition
```

Visualization succeeds in the same type of fresh project before a reference is
created, so this is a real cross-family composition regression rather than a
help typo. The reference row is created successfully; the failure occurs when
the visualization task later opens its database composition. No claim is made
here about whether a failed visualization writes a run, because this wave was
focused on public discovery/help and the issue should receive its own focused
pre-admission/ledger investigation.

## Verification

Focused checks passed:

```
python3 -m pytest -q tests/test_pipeline_dispatch_aliases.py tests/v10/test_domain_cli_surface.py -k 'help or census'
# 13 passed, 39 deselected

python3 -m pytest -q tests/v10/test_domain_cli_projects_timelines.py tests/v10/test_doctor.py tests/v10/test_selection_isolation.py -k 'help or timelines or doctor or selection'
# 80 passed
```

The help/doc changes are limited to the public gateway help, core skill, CLI
contract, and CLI journey guide; the cross-family failure remains explicitly
unfixed and called out above.
