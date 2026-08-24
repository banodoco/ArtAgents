# SDK staging `out` contract check

Date: 2026-08-24 (Europe/Berlin)  
Surface: public `astrid.sdk.invoke` / `invoke_result`, kernel capability handler,
managed-media completion  
Verdict: **stale internal test expectation plus one real public result leak;
both corrected narrowly.**

## Trigger

The broader SDK run surfaced exactly one initial failure:

```text
tests/test_sdk_public_surface.py::
test_invoke_executor_project_routing_allows_out_none_with_in_process_mode
```

The test called:

```python
astrid.invoke(
    "editorial.arrange",
    kind="executor",
    project="demo",
    out=None,
    execution_mode="in_process",
    include_installed=False,
)
```

and monkeypatched the runner to assert that its internal
`ExecutorRunRequest.out` remained `None`. Current execution supplied:

```text
<ASTRID_PROJECTS_ROOT>/.astrid/media/.staging/<transaction-id>/out
```

instead.

## Authority and contract diagnosis

The assertion was from the pre-kernel direct-run shape. A real SDK invocation
is now admitted as a kernel run/task/attempt. `ExecutionService` assigns one
attempt-owned staging transaction, and `CapabilityTaskHandler` deliberately
constructs the in-process runner request with:

```text
out       = <staging transaction>/out
run_root  = <staging transaction>
project_was_auto_resolved = true
```

That behavior is required, not a regression:

- pack code cannot write directly to a caller-selected/project path after
  admission;
- retries cannot bypass the completion fence;
- declared files are prepared and atomically published into managed CAS;
- successful/failed attempts clean their private staging tree;
- durable output locators come from `InvocationResult.outputs.artifacts`.

Keeping `out=None` at the internal runner would either fail executors that
require an output base or force them to invent an unmanaged path. Therefore
the old assertion was stale and has been replaced with a guard for the actual
ownership contract.

## Real user-visible defect

Fresh successful invocations were returning the internal staging path as both
`raw_result.run_root` and `InvocationResult.run_root`, then deleting that path
before returning. This gave agents a locator guaranteed not to exist. Exact
idempotent replays already omitted it, creating additional first-call/replay
drift.

Kernel-managed invocations do not have a durable filesystem run directory:
the run ID belongs to the kernel ledger and successful artifacts belong to
managed CAS. The correction therefore:

1. removes `run_root` from a fresh kernel success envelope;
2. stops synthesizing the projects root when no durable `run_root` exists;
3. returns public `InvocationResult.run_root = None` for normal kernel-managed
   invocations;
4. continues to propagate an explicitly supplied durable/custom `run_root`
   from compatibility kernels;
5. leaves dry-run/direct DTO normalization unchanged.

## Updated regression guard

The renamed test
`test_invoke_executor_project_routing_uses_private_staging_and_cleans_it`
now observes all relevant boundaries:

- internal `out` is named `out` beneath `.staging/<transaction-id>`;
- internal `run_root` is the owning transaction directory;
- the directory exists while the runner executes;
- `project_was_auto_resolved` bypasses only the public project/explicit-out
  conflict for this trusted internal staging request;
- staging is absent after successful completion;
- public `result.run_root` is `None`;
- `raw_result` does not carry `run_root`.

Focused result:

```text
pytest -q \
  tests/test_sdk_public_surface.py::test_invoke_executor_project_routing_uses_private_staging_and_cleans_it -x
1 passed in 1.48s
```

## Live public replay

The replay used the existing disposable canonical alpha fixture but selected a
new output name, forcing a new real kernel attempt rather than an idempotent
read:

```python
from pathlib import Path
import astrid.sdk as sdk

staging = Path(
    "/private/tmp/astrid-alpha-managed-fix.YLb6Pe/.astrid/media/.staging"
)
before = sorted(staging.iterdir()) if staging.is_dir() else []
result = sdk.invoke_result(
    "rendering.render",
    kind="executor",
    project="alpha-lab",
    project_root="/private/tmp/astrid-alpha-managed-fix.YLb6Pe",
    inputs={
        "timeline_ref": "alpha-layer",
        "expected_version": 1,
        "backend": "rendering.remotion",
        "output_name": "staging-contract-alpha.mov",
    },
)
after = sorted(staging.iterdir()) if staging.is_dir() else []
```

Exact observed summary:

```json
{
  "ok": true,
  "run_id": "d2a88cc29ac620c5e693816911",
  "run_root": null,
  "raw_has_run_root": false,
  "staging_before": [],
  "staging_after": [],
  "primary_content_hash": "87ae2265a5e5db9cc6e873c8c22f3729767dbcc8dbf720585303ad34c89cfa44",
  "primary_path": "/private/tmp/astrid-alpha-managed-fix.YLb6Pe/.astrid/media/sha256/87/ae/87ae2265a5e5db9cc6e873c8c22f3729767dbcc8dbf720585303ad34c89cfa44"
}
```

The invocation succeeded, returned a durable managed locator, and left no
attempt staging directory. The dead-path UX leak is gone without weakening
the project-owned publication fence.

## Documentation

`docs/reference/sdk.md` now describes the current kernel contract: `run_id` is
the durable ledger identity, `outputs.artifacts` contains durable locators,
and `run_root` is `None` for normal kernel-managed invocation because staging
is private and ephemeral.

## Scope note

A subsequent full `tests/test_sdk_public_surface.py -x` advances past this
fixed guard and stops at older fake `_kernel_invoke` functions that do not
accept the newer `extra_pack_roots`/authority kwargs. That separate mock-
signature drift predates this discrepancy and was not changed here.

Severity after correction: **resolved**.
