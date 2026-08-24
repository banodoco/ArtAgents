# Live replay: project orientation and current selection (wave 2)

Date: 2026-08-23 (Europe/Berlin)  
Verdict: **PASS with two UX/error-reporting frictions**

## Scope and isolation

This was a fresh black-box replay. I used only the public root/family help,
the Astrid core skill, the CLI, and read-back of returned paths/state. No
source, tests, git history, or prior QA reports were inspected or changed.

Disposable state:

- `ASTRID_PROJECTS_ROOT=/tmp/astrid-orient-root-cfo9LX`
- workspace cwd `/tmp/astrid-orient-ws-SPRY5N`
- second clean workspace `/tmp/astrid-orient-ws2-mPOv3s`
- isolated user home/preferences `/tmp/astrid-orient-home-p7P3tE`
- stale-root probe `/tmp/astrid-orient-stale-root-r9UEG2`

The root census printed exactly the eight families: `projects timelines
media tasks runs serve doctor backup`. It also showed only the documented
nested mounts `timelines shots` and `media references`.

## Replay commands and observations

### Create, select, and orient

```sh
HOME="$PH" ASTRID_PROJECTS_ROOT="$ROOT" python3 -m astrid projects create alpha --name 'Alpha Display' --json
HOME="$PH" ASTRID_PROJECTS_ROOT="$ROOT" python3 -m astrid projects create beta --name 'Beta Display' --json
HOME="$PH" ASTRID_PROJECTS_ROOT="$ROOT" python3 -m astrid projects select alpha --scope user --cwd "$WS" --json
HOME="$PH" ASTRID_PROJECTS_ROOT="$ROOT" python3 -m astrid projects select beta --scope workspace --cwd "$WS" --json
HOME="$PH" ASTRID_PROJECTS_ROOT="$ROOT" python3 -m astrid projects current --cwd "$WS" --json
```

`projects current` in a fresh process/cwd resolved Beta, with the selected
project id, canonical path, workspace preference path, and `scope:
workspace`. `projects current --cwd /tmp` resolved user Alpha. The user
preference was also shown by public output, with no preference-file contents
read.

### Omitted-project routing and explicit override

With Beta selected at workspace scope, these omitted `--project` commands
were run from the workspace cwd:

```sh
python3 -m astrid timelines create beta-timeline --name 'Beta Timeline' --json
python3 -m astrid timelines list --json
python3 -m astrid media import "$WS/probe.txt" --json
python3 -m astrid media list --json
python3 -m astrid tasks create --capability rendering.timeline_visualize \
  --spec '{"timeline_source":"beta-timeline"}' --json
python3 -m astrid tasks list --json
python3 -m astrid runs list --json
```

Every receipt carried Beta's project id. Read-back counts were: Beta 1
timeline, 1 media row, 1 queued standalone task, 0 runs; Alpha 0 media,
0 tasks, and 0 runs. This proves the omitted-project family routing lands in
the workspace-selected project.

The explicit override was then exercised:

```sh
python3 -m astrid timelines create alpha-explicit --project alpha --name 'Alpha Explicit' --json
python3 -m astrid timelines list --project alpha --json
python3 -m astrid timelines list --json
```

The explicit create/list saw only Alpha's timeline, while the omitted list
still saw only Beta's timeline. No cross-project write occurred.

### Rename, stable addresses, and plan read-back

```sh
python3 -m astrid projects update alpha --name 'Renamed Alpha' --json
python3 -m astrid projects show alpha --json
python3 -m astrid projects show a8405653-b009-54ad-8438-0946c9f807f1 --json
```

The display name changed while slug `alpha` and id
`a8405653-b009-54ad-8438-0946c9f807f1` remained valid. The returned canonical
path was `/private/tmp/astrid-orient-root-cfo9LX/alpha`; reading its returned
`plan.md` path produced the expected empty project-plan skeleton (177 bytes).

### Duplicate/confusable refs and wrong-project ids

```sh
python3 -m astrid projects create gamma --name 'Renamed Alpha' --json
python3 -m astrid projects create alpha --name 'Duplicate Slug' --json
python3 -m astrid projects show 'Renamed Alpha' --json
python3 -m astrid projects show not-a-project --json
python3 -m astrid timelines show 'Alpha Explicit' --project alpha --json
python3 -m astrid timelines show "$ALPHA_TIMELINE_ID" --project beta --json
python3 -m astrid timelines show "$BETA_TIMELINE_ID" --project alpha --json
```

Results:

- Duplicate display names are allowed across projects. A project lookup by
  that human name failed closed with `ambiguous_display_name` and two
  actionable `{id,name,slug}` candidates.
- Duplicate slug creation failed with typed `conflict`, `field: slug`, and a
  recovery telling the operator to choose a new immutable slug.
- Unknown project refs returned typed `not_found` with list/retry recovery.
- A timeline id in the wrong project returned typed `not_found` naming the
  project id and recovery command; the Beta row remained active after a
  cross-project archive attempt.
- Timeline display-name refs (`Alpha Explicit`, and two duplicate
  `Same Human Name` timelines) failed with `validation_error` but empty
  `details`. This is less actionable than project-ref handling and is a UX
  friction, though it fails closed without mutation.

### Workspace change, user fallback, stale, and malformed preferences

```sh
python3 -m astrid projects select alpha --scope workspace --cwd "$WS" --json
python3 -m astrid projects current --cwd "$WS" --json
python3 -m astrid projects current --cwd "$WS2" --json
```

Changing the workspace selection to Alpha worked. A clean second workspace
with no workspace preference deterministically fell back to user Alpha. The
public `projects select` help exposes no unset/remove verb, so removal was
not claimed as supported.

For stale handling, the same isolated user preference was resolved against a
different empty disposable projects root. `projects current` returned typed
`not_found`, `reason: stale_selection`, the public preference path, scope,
ref, and recovery (`projects list`, then select a listed project).

For malformed handling, only the disposable workspace preference path
previously returned by `projects select/current` was replaced with invalid
JSON; its contents were not read back. `projects current` returned
`internal_error`, `error_type: ProjectJsonError`, and the message
`invalid JSON in <path>: Expecting value`. Valid-but-unrecognized JSON shapes
were ignored and fell back to user Alpha. The parse failure is deterministic
but its generic internal-error envelope and redacted `<path>` are not very
actionable (second UX friction).

## Final state checks

After malformed workspace fallback, omitted reads from the workspace resolved
to Alpha: 3 active Alpha timelines, 0 media, 0 tasks, 0 runs. Explicit
`timelines archive <Beta timeline id> --project alpha` failed not-found, and
Beta still listed its original 1 active timeline. This is direct evidence of
no cross-project mutation.

## Friction and verdict

The project-orientation contract is sound: workspace wins over user scope,
fresh CLI processes resolve the same selection, canonical project paths are
returned, omitted project-scoped commands route correctly, and explicit
`--project` wins. Stable slug/id addressability survives rename, and errors
for project ambiguity, stale selections, duplicate slugs, and wrong-project
ids are structured and recoverable.

Two non-blocking UX issues remain: timeline human-name refs produce an empty
validation-details object rather than candidates/recovery, and invalid JSON
preferences surface as generic `internal_error`/`ProjectJsonError` with a
redacted path. No product behavior or source files were changed.
