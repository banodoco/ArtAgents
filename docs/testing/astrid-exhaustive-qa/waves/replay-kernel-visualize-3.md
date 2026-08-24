# Replay: kernel timeline → visualization 3

Date: 2026-08-23  
Surface: public `python3 -m astrid` CLI, SDK discovery/invoke, and read-only artifact inspection  
Scratch root: `/tmp/astrid-replay-kernel-visualize-3-clean.Qj23sJ` (removed after replay)

## Verdict

PASS. A fresh project and default timeline were created and saved only through
public timeline/project APIs. `rendering.timeline_visualize` succeeded for the
default selector, slug, UUID, and ULID, with PNG/SVG/Markdown requested across
calls. Each success produced a kernel run and child task plus durable managed
media artifacts; no user-visible legacy timeline/run directory was created.

## Clean setup

```text
project: replay-three
timeline: kernel-main
timeline UUID: e2c5ef4e-f001-5c68-8f4d-ccc47aa8ee10
timeline ULID: bhxjcxwzb7j21z0ez5rr3vyr52
document: {"tracks": [], "clips": []}
config_version after save: 2
```

The public CLI census/help exposed the expected product families; SDK
capability discovery exposed `rendering.timeline_visualize` and its public
selector/format schema.

## Selector and format replay

All four rows returned `ok=true`, with one run and one child task each.

| selector | formats | run / task | durable presentation outputs |
| --- | --- | --- | --- |
| omitted (project default) | `png` | `882020f503c93ae5a1da013901` / `9dbff823a0e81f07c0c2fb8556` | `PG001.png`, `PG002.png` |
| `timeline_slug=kernel-main` | `svg` | `d0dbdac7353b6f844b765b39bc` / `85f000d2137db59c5b81d205db` | `PG001.svg`, `PG002.svg` |
| `timeline_slug=e2c5ef4e-f001-5c68-8f4d-ccc47aa8ee10` | `md` | `73b58bf0f1ced7a6011d5a9396` / `7b8ec3f6ec6232fa7117ee1066` | `structure.md` |
| `timeline_slug=bhxjcxwzb7j21z0ez5rr3vyr52` | `png`, `svg`, `md` | `13071cfeb7f503f40aef162518` / `f942a049b203add599813b2b9e` | PNGs, SVGs, `structure.md` |

Every result also published `manifest.json`, JSON indexes/diagnostics, and
the reading guide as managed media. Reading the durable manifests showed the
same identity in every snapshot: `qualified_ref=TL01`, `stable_id=TL01`,
slug `kernel-main`, and the setup UUID/ULID above. This confirms selector
equivalence rather than merely successful execution.

Before and after the four invocations, public `timelines show` and
`timelines history` were byte-equal (`history_len=2`); visualization's private
projection did not mutate kernel timeline state. The project contained only
`plan.md` and `project.json`—no legacy `timelines/` or user-visible `runs/`
directory.

## Cross-project admission fences

A second public project, `replay-other`, was left with no timelines. Passing
the first project's source/ref/list forms raised `CapabilityValidationError`
before admission:

- `timeline_source=[<replay-three project path>]`
- `timeline_slug=kernel-main`
- `timeline_slug=<first-project UUID>`
- `timeline_slug=<first-project ULID>`
- `timeline_source=[<first-project path>, <first-project path>]`

For every case, project show, timeline list, runs list, tasks list, media list,
and SQLite `(size, mtime_ns)` were unchanged. No run, task, artifact, or DB
write was admitted. Representative errors were “timeline input is not owned
by project 'replay-other'” and “no kernel timeline with ref …”.

## Edge probes

- `timeline_slug=kernel-main` plus `all=true`: typed
  `CapabilityValidationError` (“mutually exclusive”), with no state delta.
- `all=true`, `formats=["md"]`: succeeded as run
  `2feab94f42cba55a529af000f8` / task `db7a0ee991a86b5d7ce3813dba`; it
  published the Markdown evidence pack for the one active timeline.
- `formats=["jpeg"]`: typed `CapabilityValidationError` (“choose png, svg,
  md, or all”), with no run/task/artifact/DB delta.

No source code or tests were changed by this replay. The scratch root was
cleaned after collecting the evidence.
