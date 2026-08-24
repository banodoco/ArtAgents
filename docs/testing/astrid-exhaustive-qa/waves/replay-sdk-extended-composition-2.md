# Replay: SDK extended-composition propagation (live agent UX)

Date: 2026-08-24 (Europe/Berlin)  
Method: one long-lived public `AstridClient` plus read-only durable-state
inspection; all project/timeline/invocation/read actions went through the SDK;
no source, tests, or product edits  
Fresh disposable root: `/private/tmp/astrid-sdk-extended-replay-PQDlxx`  
Verdict: **PASS — explicit schema composition survives client invocation,
nested reads, exact replay, and ambient-root changes; incomplete composition
still fails closed.**

## Acceptance summary

| Contract | Result |
| --- | --- |
| One client opens with core + timeline + shots + references + runaway | Pass |
| Project and canonical timeline creation use that bound composition | Pass |
| `rendering.timeline_visualize` succeeds through the same client | Pass |
| Bound `client.runs.list` sees the invocation run | Pass |
| Exact invocation replay is stable and creates no second run | Pass |
| Ambient `ASTRID_PROJECTS_ROOT` cannot reroute the bound client | Pass |
| All five migration rows remain present | Pass |
| Explicit core-only reopen rejects the extended database | Pass |

## Fresh long-lived client flow

The registry was explicitly composed with core vocabulary, the three standard
packs (`timeline`, `shots`, `references`), and the `runaway` schema pack. A
single `AstridClient.open(root, registry=...)` context then performed all
domain operations:

```python
with AstridClient.open(root, registry=extended_registry) as client:
    client.projects.create(slug="extended-lab", name="Extended Lab")
    client.timelines.create(
        project="extended-lab", slug="primary", name="Primary",
        set_default=True,
        config={
            "tracks": [{"id": "main", "kind": "visual", "label": "Main"}],
            "clips": [],
            "output": {"resolution": "320x180", "fps": 24,
                       "file": "primary.mp4"},
        },
        registry={"assets": {}},
    )
```

Both writes returned `ok=True`; the timeline was version 1. After the client
was already bound, the process environment was deliberately changed to an
uninitialized sibling root:

```text
bound root:   /private/tmp/astrid-sdk-extended-replay-PQDlxx
ambient root: /private/tmp/astrid-sdk-extended-replay-PQDlxx-ambient
```

The first bound call was:

```python
client.invoke(
    "rendering.timeline_visualize",
    kind="executor",
    project="extended-lab",
    inputs={"formats": ["md"], "filmstrip": "off"},
)
```

It succeeded as kernel run `2c5e12e1b9787871f43ec09215`, with task
`313e35b3de5d8621382fb5624e` and attempt
`01m0styn4shhgdc0zxznxj84k2`. The durable primary manifest was published
under the bound root:

```text
/private/tmp/astrid-sdk-extended-replay-PQDlxx/.astrid/media/sha256/a2/73/
a2731768af35d31aaa162ec009dc54bac5ec20de08bb54f60b73dde16a9e28b7
```

The ambient sibling remained uninitialized (`.astrid/astrid.sqlite3` absent),
so neither capability execution nor nested reads could have silently switched
roots.

## Nested run read and exact replay

Within the same client and with the wrong ambient root still set,
`client.runs.list("extended-lab")` returned exactly one succeeded run, with
the same run ID and `rendering.timeline_visualize` title. This proves the
bound read service sees the run created by the bound invocation.

Calling `client.invoke` again with the byte-identical capability, project, and
inputs returned the same:

```text
run_id:         2c5e12e1b9787871f43ec09215
kernel task:    313e35b3de5d8621382fb5624e
manifest path:  .../a2731768af35d31aaa162ec009dc54bac5ec20de08bb54f60b73dde16a9e28b7
exact DTO:      true
run count:      1 before and after replay
```

The normalized `InvocationResult.to_dict()` values were equal, including the
durable artifact set and content hashes. The second `client.runs.list` also
returned the unchanged single-run ledger.

## Durable migration and fail-closed checks

After releasing the client owner lock, a read-only SQLite inspection showed
the exact five migration rows:

```text
core       1
references 1
runaway    1
shots      1
timeline   1
```

Reopening the same database with the explicitly incomplete `core_only_registry`
was rejected before use with:

```text
MigrationTooNewError:
database contains applied migrations for pack 'references', which is not registered in this composition
```

A follow-up read confirmed all five rows were still present; the failed
incomplete open did not mutate the database. The ambient sibling database was
still absent.

## UX/friction and verdict

The live flow is straightforward once the agent knows that extended schema
composition is an explicit SDK construction concern. The only residual
friction is that composing a custom registry requires importing the schema-pack
composition helpers rather than discovering a single high-level “standard plus
pack” helper. That is a low-severity setup concern, not a propagation defect.

**PASS, 9.8/10.** No P0, P1, or P2 issue was found in this replay. The bound
registry, bound root, nested run reads, idempotent output replay, migration
visibility, and incomplete-registry safety boundary all behaved correctly.
