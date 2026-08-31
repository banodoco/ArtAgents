# Getting Started with Astrid

Astrid is a Python SDK and harness toolkit for building and running
agentic UXes — pipelines where agents and humans collaborate to make art.

## Prerequisites

Astrid requires Python 3.11+ and an editable Banodoco workspace-runtime
checkout. The runtime is a separate local service that owns durable workspace
state; the Astrid checkout is a client and pack source, not the state store.

Install Astrid from the checkout and point the client at the neutral runtime
checkout. The first product command starts or reconnects that runtime through
the neutral launcher; no separate database service is needed:

```bash
pip install -e .
export BANODOCO_RUNTIME_CHECKOUT=/path/to/banodoco-workspace-runtime
python3 -m astrid --help
python3 -m astrid projects list --json
```

An existing neutral source manifest can be used instead with
`BANODOCO_LOCAL_SOURCE_MANIFEST`. The manifest records both editable
checkouts and is retained under the runtime support directory after a
successful first launch so later `banodoco-local restart`/reconnect commands
use the same composition. The equivalent explicit operator command remains
`banodoco-local up --profile astrid`.

## Your First Command

From any shell with the runtime configured, check health:

```bash
python3 -m astrid doctor --json
```

Other useful zero-secret commands:

```bash
python3 -m astrid projects list --json
python3 -m astrid projects show demo --json
```

If a direct runtime endpoint is deliberately supplied, set
`BANODOCO_RUNTIME_ENDPOINT` and `BANODOCO_RUNTIME_CREDENTIAL`, or set
`BANODOCO_RUNTIME_DISCOVERY` to the runtime's discovery JSON. Never point
Astrid at a local SQLite/CAS directory; the runtime owns those details.

`astrid doctor` remains a read-only diagnostic and does not create support
state. Product commands and SDK `AstridClient.open()` perform the bounded
neutral launch/reconnect handoff automatically. Set
`BANODOCO_ASTRID_AUTO_BOOTSTRAP=0` to inspect an unavailable runtime without
attempting that handoff.

The seven top-level gateway families are `projects`, `timelines`, `media`,
`tasks`, `runs`, `doctor`, and `backup`; `timelines shots` and `media
references` are nested mounts. `doctor`
and `backup` use runtime routes and report a typed `unavailable` result until
the runtime exposes the requested operation.

Runtime health, project identity, media objects, timeline versions, task/run
state, receipts, and events are authoritative only in the workspace runtime.
The SDK never opens a local Astrid database or content-addressed store.

Historical pre-runtime project trees and local-store migration plans are not
part of the Stage1 live path. If you have one, use its separately documented
historical migration procedure or import its files as ordinary attempt-local
artifacts; do not treat it as current workspace state.

For the complete project, timeline, media, recovery, and failure journeys,
continue with [CLI journeys](guides/cli-journeys.md). For renderer-specific
diagnostics, see [Debugging](guides/debugging.md).

### Canonical timeline schema

The canonical `banodoco_timeline_schema` package is an optional external
dependency. Astrid's default Python install intentionally does not vendor or
declare this private Banodoco workspace package, so clean installs can use the
non-schema surfaces and import Astrid without that checkout. Timeline document
validation, managed rendering/visualization, and the exact canonical-schema
parity assertions require it and fail closed when it is unavailable.

The `dev` extra pins a compatible public source revision so the repository-wide
test suite and CI validate one deterministic schema. This does not add the
schema to Astrid's base runtime dependencies.

Install the package from a compatible Banodoco workspace checkout with the same
interpreter used to run Astrid:

```bash
python -m pip install -e /path/to/banodoco-workspace/packages/timeline-schema/python
python -c "import banodoco_timeline_schema; print('timeline schema available')"
```

The Astrid checkout does not contain `packages/timeline-schema/python`; replace
the placeholder with the path to the external workspace. If the package is not
installed, the timeline parity module remains collectible and skips only its
parameterized canonical-schema checks; its independent compositor checks still
run.

### First visible timeline render

When hand-authoring a timeline, start with root `clips`, a `visual` track,
structured text marked explicitly as `clipType: "text"`, and an MP4 output:

```json
{"tracks":[{"id":"cards","kind":"visual","label":"Cards"}],
 "clips":[{"id":"title","at":0,"track":"cards","clipType":"text","hold":2,
   "text":{"content":"HELLO ASTRID","fontSize":64,"color":"#ffffff","align":"center"}}],
 "output":{"resolution":"640x360","fps":30,"file":"title.mp4"}}
```

The renderer rejects a structured `text` clip without `clipType: "text"` and
checks the default `.mp4` output suffix before starting a render, so these
mistakes do not consume a failed attempt.

## Where to Go Next

- **SDK tutorial** — Walk through the full discover → inspect → invoke →
  read-events loop: [Build Your First Agentic UX](guides/build-your-first-agentic-ux.md).
- **Pack authoring** — Build your own executors, orchestrators, and
  elements: start with [Pack Documentation](packs/) and
  [Creating Packs](packs/creating-packs.md).
- **Contracts index** — Normative contracts that define the SDK surface,
  CLI behavior, error model, output format, and run ledger:
  [Contracts Index](contracts/README.md).
- **Full SDK reference** — DTO catalog and exception hierarchy:
  [SDK Reference](reference/sdk.md).
- **Discovery for agents** — How AI agents consume the capability
  registry: [Discovery for Agents](guides/discovery-for-agents.md).
