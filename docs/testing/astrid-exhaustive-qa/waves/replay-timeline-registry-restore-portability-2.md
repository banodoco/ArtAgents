# Replay: cross-root timeline registry portability 2

Date: 2026-08-24 (Europe/Berlin)

## Verdict

**Conditional pass.** Backup/restore and version-pinned rendering now work
without rewriting the canonical timeline. The saved registry remains an
immutable source-root payload while the renderer creates a destination-specific
materialized registry and durable output. Visualization is reachable and
produces its evidence pack, but still emits `MEDIA_MISSING`/`UNSUPPORTED_MEDIA`
warnings for the old absolute locator instead of resolving the restored managed
media transparently. This is the remaining portability friction.

## Fresh live journey

No source, tests, or prior QA reports were used to drive the journey. A fresh
source root, destination root, and self-contained backup were created under:

- source: `/tmp/astrid-registry-portability-src-CcSqmZ`
- destination: `/tmp/astrid-registry-portability-dst-IpodWy`
- backup: `/tmp/astrid-registry-portability-backup-parent-f1Vzf1/backup`

Using only the public CLI, I:

1. Created project `portable-maker` and default timeline `primary`.
2. Generated a valid 2-second MP4 fixture with visible `PORTABLE` text and
   imported it with `media import`, producing managed CAS hash
   `b2b2356b1fa0d6b3d78fb6f06104232e17be829996e9f19b617bf214a263093c`.
3. Saved timeline version 2 with a registry containing an absolute source CAS
   `file` locator and `type: video`, deliberately omitting
   `content_sha256`.
4. Captured fresh `timelines show` and `timelines history`, then created a
   self-contained backup.
5. Restored into the fresh destination root. Restore reported one rebased
   managed media locator and one restored media file.
6. Immediately ran `doctor`, `media list`, `timelines show`, `timelines history`,
   `timelines visualize primary --format png,md --filmstrip off`, and
   `timelines render primary --expected-version 2 --backend rendering.remotion`.
   No timeline save or repair was performed after restore.

## Immutable canonical state

The restored `timelines show` retained exactly the source-root locator:

`/private/tmp/astrid-registry-portability-src-CcSqmZ/.astrid/media/sha256/b2/b2/b2b2356b1fa0d6b3d78fb6f06104232e17be829996e9f19b617bf214a263093c`

Fresh show equality before/after visualization and rendering: **true**.
Fresh history equality before/after visualization and rendering: **true**.
The timeline stayed at `config_version: 2`; history stayed at versions `[1, 2]`.

The destination media read model correctly pointed to:

`/private/tmp/astrid-registry-portability-dst-IpodWy/.astrid/media/sha256/b2/b2/b2b2356b1fa0d6b3d78fb6f06104232e17be829996e9f19b617bf214a263093c`

## Visualization

`timelines visualize` succeeded and published a durable manifest, PNG pages,
asset index, diagnostics, structure, and reading guide. It correctly pinned
the kernel snapshot at version 2. However, diagnostics included:

- `MEDIA_MISSING: asset 'portable' local file was not found`
- `UNSUPPORTED_MEDIA: path escapes project root — local reference is not contained under project sources`

The visualizer did not mutate the timeline and therefore preserved canonical
state, but its UX does not yet use the restored managed-media alias that the
renderer can resolve. This should be addressed if warning-free restored
visualization is a release requirement.

## Version-pinned render

The first post-restore render succeeded with `--expected-version 2`:

- run: `b26d126742d7db7024bab9473e`
- task: `3f5b43403fded90c509fffa9d0`
- MP4 media id: `01m0ska6fe4szqhr0rwwcdeaw1`
- MP4 hash: `262a78f47ea79ef0737de8c51a0f32138043fbc622ea3a95c491863d9eebef56`
- provenance media id: `01m0ska6fjwx2b856w233r0rvz`
- provenance hash: `2c1dd0f42b4eb7b6b3fe6b0fe59d6fc49bfec1333394d9398b5a8035d35543cb`

The output is a playable H.264/AAC MP4 at 1920×1080, 30 fps, 2.048 seconds.
An extracted frame visibly shows the intended `PORTABLE` title.

The provenance sidecar proves the two-level registry identity:

- canonical `registry_hash`: `34007a705f7000297be979642b8a8b38c32a79ea8738106e02e4c057760640f9`
- destination `materialized_registry_hash`:
  `d2217257801b29e0189e4c6dd89e44b385d8ba787801b1d90fc6be048b1c259a`
- materialized registry locator: destination CAS path above

The canonical hash is stable from the unchanged source-root registry; the
materialized hash is intentionally destination-specific.

## Adversarial locator checks

Three fresh projects were created with same-shaped registries and no product
code changes:

- `foreign-ref`: referenced the restored `portable-maker` media locator;
- `arbitrary-ref`: referenced a copied file under a hash-shaped but
  unregistered destination CAS path;
- `tampered-ref`: referenced a same-shaped path containing non-video bytes.

All three render attempts failed during support with an explicit
`not an owned managed media locator` message, exit code 1, and no MP4 or
provenance artifact. The ownership boundary is therefore fail-closed for
foreign, arbitrary, and tampered same-shaped paths.

## Friction / follow-up

The core restore → show → pinned render journey is now smooth and preserves
event/version truth. The remaining ergonomic gap is visualizer-specific: it
still treats the immutable source-root absolute locator as missing after
restore, even though the media identity and destination managed locator are
available in the kernel and rendering resolves them successfully.
