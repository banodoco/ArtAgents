# Live replay: orientation recovery and timeline ref errors (wave 3)

Date: 2026-08-23 (Europe/Berlin)  
Verdict: **PASS**

## Scope and isolation

This was a fresh, narrow black-box LIVE UX replay. The run used the public
Astrid CLI/help and isolated disposable state; no product source, tests, git
history, or prior QA behavior was used to drive the cases. Commands ran from a
separate cwd so the workspace preference path and omitted-project routing were
exercised as a real operator would see them.

Disposable state (removed after the replay):

- `ASTRID_PROJECTS_ROOT=/tmp/astrid-orientation-root.1LEemo`
- separate cwd `/tmp/astrid-orientation-cwd.zaKHj7`

Two projects were created with the same human display name, but different
slugs: `left-project` and `right-project`, both named `Orientation Showcase`.
Each received one timeline named `Shared Edit`, with different slugs and
stable IDs/ULIDs:

| project | timeline slug | timeline UUID | timeline ULID |
| --- | --- | --- | --- |
| `left-project` | `left-cut` | `c73afb0e-dad5-5b39-bf1e-c688739c3d4b` | `sfvwcbz1tzp7v69gceykrsaq4j` |
| `right-project` | `right-cut` | `3b879545-79d3-550a-a313-bfe7f2aaeda9` | `98x4y4fnmkvzr7enq1csseqmsj` |

## Path 1: malformed public workspace preference

The public selection was first set to `left-project` from the separate cwd:

```sh
python3 -m astrid projects select left-project --json
python3 -m astrid projects current --json
```

Both responses reported the workspace preference path
`/tmp/astrid-orientation-cwd.zaKHj7/.astrid/config.json`, scope `workspace`,
and selected ref `left-project`. Only that disposable preference JSON was then
corrupted (truncated to 10 bytes). The project database and project files were
not touched.

An omitted-project command was invoked:

```sh
python3 -m astrid timelines list --json
```

It exited 1 with the stable five-key envelope and this typed error:

```json
{
  "code": "validation_error",
  "details": {
    "field": "project",
    "path": "/private/tmp/astrid-orientation-cwd.zaKHj7/.astrid/config.json",
    "reason": "invalid_selection_preference",
    "recovery": "repair or remove the malformed preference, then run `astrid projects select <slug-or-id>`",
    "scope": "workspace"
  },
  "message": "the current project preference is invalid"
}
```

This is a typed, non-internal failure. It identifies the preference scope and
exact path, explains why routing was refused, and gives a safe public repair
command. `data` and `receipt` were null; no timeline list or project routing
was performed while the preference was malformed.

Repair used the public command, not direct file editing:

```sh
python3 -m astrid projects select right-project --json
python3 -m astrid projects current --json
python3 -m astrid timelines list --json
```

`projects current` reported `right-project` and the same workspace preference
path. The omitted timeline list then returned only `right-cut` / `Shared Edit`,
proving the repaired preference controls current routing and does not fall
through to the wrong project.

## Path 2: timeline display-name, nonexistent, and malformed refs

With `right-project` selected, the public help described timeline refs as
“Timeline UUID, ULID, or slug.” The following read and CAS-write attempts were
run with omitted `--project`:

```sh
python3 -m astrid timelines show 'Shared Edit' --json
python3 -m astrid timelines show definitely-missing --json
python3 -m astrid timelines show 123 --json
python3 -m astrid timelines save 'Shared Edit' --config '{}' --registry '{}' --expected-version 1 --json
python3 -m astrid timelines save definitely-missing --config '{}' --registry '{}' --expected-version 1 --json
python3 -m astrid timelines save 123 --config '{}' --registry '{}' --expected-version 1 --json
```

All six commands exited 1. A human display name is explicitly not treated as
an address. Both `show` and `save` returned `validation_error` with
`reason: display_name_not_addressable`, and an ambiguity-safe candidate record:

```json
{
  "id": "3b879545-79d3-550a-a313-bfe7f2aaeda9",
  "name": "Shared Edit",
  "slug": "right-cut",
  "timeline_ulid": "98x4y4fnmkvzr7enq1csseqmsj"
}
```

The recovery was explicit: retry with `candidates[0].slug`,
`candidates[0].id`, or the listed ULID. This exposes every supported stable
address form while keeping the human name itself non-addressable.

`definitely-missing` and malformed `123` both failed closed with typed
`not_found` errors. Each included the attempted `ref`, owning `project_id`,
and recovery to run `astrid timelines list --project <project>` and retry with
a listed slug or id. Neither `show` nor `save` returned a receipt or data.

Before the failed ref attempts, a valid `timelines show right-cut --json`
returned config version 1 and the unchanged empty config/registry. After all
six failures, the same valid show returned the identical timeline document.
SHA-256 hashes of the SQLite kernel and both project JSON/plan files also
matched before and after:

```text
astrid.sqlite3  5a5a184edd3172e55477fff201d7b97e6d66e4f30546ebf10e5607317dd3fbd7
left project files  fe12336dd885c01e36d08be076cac4d9b8a05df0b58b3dc5dc4848d807ad9cdb
                   bd8630b18c8996a0e8d7f76318a972b07e6fc5e8381fa748c346ede1901fa4cb
right project files c5681dd08e1518601fcfd86bfa864d45c675336baacf2fdc51a1534ae28ccfd9
                    14f409b8ad2874be38f1fbb67b8644aa43009260770e52b26250edeae4eb67b7
```

## Cleanup and verdict

The disposable projects root and separate cwd, including the corrupted
preference, were removed after capture. No repository source or tests were
changed. The two recovery paths pass: malformed preferences fail with
actionable typed scope/path/repair guidance; public reselection restores
current routing; and timeline show/save reject display-name, nonexistent, and
malformed refs without mutation while returning stable UUID/ULID/slug retry
options.
