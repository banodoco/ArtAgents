# Final maker polish: addressing, render preflight, and stale selection

Date: 2026-08-23  
Surface: live public CLI/SDK usage in fresh disposable roots, followed by focused regression tests

## Live reproductions

1. A fresh project with media and a reference named `Blue Voice` rejected
   `media references associate --project maker "Blue Voice" ...` as
   `not_found`, even though `show`/`unarchive` accepted the name. The exact
   reference id worked.
2. Two project-local references named `Duplicate` made `update Duplicate`
   fail closed. The response included both candidate ids and the failed update
   left the read model unchanged.
3. A foreign reference id was rejected as typed `not_found` with
   `details.reason=foreign`, project scope, and a list/show recovery command.
4. A minimal timeline with a structured `text` object but no `clipType` was
   accepted by `astrid.support("rendering.remotion", ...)` and rendered an
   H.264 file whose first frame had `YAVG=0` (black). Adding
   `clipType: "text"` produced a visible frame (`YAVG=1.03034`).
5. A default render named `bad.mov` reached Remotion and failed late with a
   codec/filename error. A default render named `bad.mov` now fails in the
   service before creating a renderer workspace with the required `.mp4`
   suffix and a retry command.
6. Selecting `old` in one projects root, switching `ASTRID_PROJECTS_ROOT`, and
   running `projects current --json` returned a typed stale-selection error
   with the stale scope, preference path, selected ref, and exact reselect
   command (`astrid projects select <slug-or-id> --scope user`). It did not
   route to the wrong root.

## Changes

- Reference mutations now resolve exact id first, then one exact project-local
  name, before hashing or writing. `associate`, `update`, `archive`,
  `set-primary`, and link endpoints share this contract. Ambiguous names carry
  candidate ids; missing/foreign refs carry typed details; all failures are
  zero-write.
- Rendering support checks reject structured text without `clipType: "text"`
  and reject text clips without string `text.content`. Timeline semantic
  validation applies the same guard.
- Render-service admission validates the output suffix against the selected
  container (default `.mp4`) before workspace creation.
- Getting-started, core, and rendering skill guidance now includes a minimal
  known-good timeline with root `clips`, a visual track, structured text,
  `clipType`, `output.resolution`, and `.mp4` output.
- Stale project selection diagnostics now preserve scope/path and provide an
  exact scoped `projects select` command.

## Focused verification

```text
180 passed in 40.49s
```

Command:

```bash
python3 -m pytest -q \
  tests/v10/test_preferences.py \
  tests/sdk/test_references.py \
  tests/v10/test_domain_cli_media_references.py \
  tests/core/rendering/test_service.py \
  tests/core/rendering/test_output_name.py
```

Additional timeline/render support checks: 51 passed in 4.06s.

## Strict replay follow-up

Replay wave 2 exposed one remaining issue: the invalid structured-text
request was correctly rejected, but support probing happened inside the
output-local render workspace, so replay capture left a
`.bad.mp4.replay/...` directory. The service now performs request-sensitive
renderer support selection in an OS temporary directory before creating the
caller output parent, replay root, or output-local staging directory. The
selected capability is then reused for the actual render. Runtime failures
after workspace creation retain the existing replay capture and temporary
directory cleanup behavior.

Fresh live proof with a pre-existing `sentinel.txt` in the output parent:

- missing `clipType` → typed `RendererUnsupportedError`; parent contents stayed
  exactly `['sentinel.txt']`; replay root did not exist;
- `bad.mov` → typed `RendererProtocolError`; parent remained unchanged;
- valid `HELLO ASTRID` → H.264/AAC MP4, 2.048 seconds, decoded frame with
  `YAVG=1.03034` (visible non-black title).

Focused rendering regression suite after the change: **95 passed in 12.52s**
(`tests/core/rendering/test_service.py` and
`tests/core/rendering/test_output_name.py`).

No user project roots, credentials, cloud calls, or unrelated source areas
were changed by this wave.
