# Replay final polish 2

Date: 2026-08-23 (Europe/Berlin)

This was a fresh black-box replay through the documented CLI and public SDK
only. The projects roots, Astrid home/preferences, working directory, media,
timelines, render outputs, and staging area were all disposable `/tmp` paths.
No source or test files were changed by this replay.

## Wave 1 — references

- Created project `demo` and imported three distinct media rows. Created one
  `Unique Hero` reference and two `Shared Hero` references. The duplicate names
  were accepted and each retained its own canonical media.
- `associate Unique Hero` with the secondary image using role `canonical`
  succeeded; `set-primary Unique Hero` promoted that association and demoted
  the original primary. `show Unique Hero` resolved by display name and
  returned both associations.
- `link --from Unique Hero --to Shared Hero` failed closed with
  `validation_error`, `reason=ambiguous_display_name`, both candidate IDs, and
  recovery to `media references list --include-archived` plus an exact ID.
  Retrying with the exact target ID succeeded, demonstrating ID precedence.
- Missing-name `show`/`link` returned typed `not_found` errors with project
  context and list-and-retry recovery. A foreign-project reference ID returned
  `not_found`, `reason=foreign`; a foreign media ID returned
  `validation_error`, `reason=foreign_media`. Neither failure emitted a
  receipt or changed the reference.
- `archive Unique Hero`, `unarchive Unique Hero`, and a repeated unarchive all
  worked by name. The repeated unarchive reported `changed=false` and retained
  the two media associations and link.

## Wave 2 — rendering quick-start

The literal documented minimal timeline was used: one visual track, one
structured text clip with `clipType: "text"`, and `title.mp4` output.

- The malformed structured-text submission (missing `clipType`) returned the
  typed public-SDK error `RendererUnsupportedError` with the actionable reason
  `clips[0] contains structured text; set clipType to 'text'`. It created no
  kernel run/task and published no video, but it **did leave a replay staging
  directory** under `.bad.mp4.replay/...` in the output workspace. This violates
  the requested pre-admission/no-workspace-artifact contract.
- The invalid output name (`bad`, no `.mp4`) returned
  `RendererProtocolError: output_name must end with .mp4 ...` and published no
  video. It created no run/task.
- The first valid attempt rendered successfully to MP4. `ffprobe` reported
  H.264/AAC, 1920x1080, 2.048 seconds; a decoded frame visibly contained the
  centered white title `HELLO ASTRID REPLAY`.

## Wave 3 — stale project selection

- Selected `demo` at workspace scope in the disposable cwd, then switched to
  a fresh `ASTRID_PROJECTS_ROOT` where that project was absent.
- `projects current --cwd <cwd> --json` failed safely with
  `reason=stale_selection`, `scope=workspace`, the exact preference path, and
  an exact recovery command: `astrid projects select <slug-or-id> --scope
  workspace --cwd <cwd>` after listing projects.
- Omitted-project `media list` safely refused the absent `demo` with a typed
  project-not-found error and list/retry recovery (no mutation). Recreating
  `demo` in the new root and running public `projects select demo --cwd <cwd>`
  repaired `projects current` and omitted `media list` (empty list).

## Verdict

References and stale-selection recovery PASS. Valid text rendering PASS.
Overall replay **FAIL** for the strict requested contract because the missing
`clipType` rejection occurs after render staging begins and leaves a workspace
`.replay` artifact, despite being typed and producing no run/task/published
video. The disposable roots were removed after recording this report.
