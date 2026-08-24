# Local render assets fix

Date: 2026-08-23 (Europe/Berlin)

## Live reproduction

The frozen acceptance failure reproduced the two real defects: a canonical
`managed_local` locator under `$ASTRID_PROJECTS_ROOT/.astrid/media` was rejected
as outside the per-project root, and project-local copies reached Remotion but
were blocked by the browser origin mismatch (`localhost` page versus the
`127.0.0.1` invocation asset server).

The fresh black-box replay used only the public CLI and SDK in disposable root
`/tmp/astrid-local-assets-S06ZAk`:

- created project `local-assets` and default timeline `primary`;
- imported a PNG, MP4 (video), and WAV (audio) through `media import`;
- built a public timeline/registry using each imported media's canonical
  managed locator and recorded `content_sha256`;
- invoked `astrid.sdk.invoke("rendering.render", kind="executor", project=...)`.

Before the fix, the same managed registry was rejected by the render asset
boundary. After the fix, the first fresh project-scoped render succeeded as
run `511f3e82323538a9706b766468` / task `86e1dd7416cfd528c9094f136a`.

The published result was a durable managed MP4 with media id
`01m0r7za5jctjxeq9cbqjnrkgc`, hash
`68e9eb55f17a682a1a3e3460532519de0990b095bc8ce63024e9a5a483687104`, and a
durable provenance sidecar with media id `01m0r7za5rttxd9vvbw94yamta`. `ffprobe`
reported H.264 video at 1920×1080, 30 fps, plus AAC audio. No `.staging` path
was returned as the durable artifact locator.

An adversarial fresh `foreign-assets` project reused the first project's
managed registry. Support rejected it with an actionable message identifying
the foreign locator and the active project boundary; no MP4 or provenance
artifact was published.

## Fix

- The shared `AssetMaterializer` now intersects exact registry file paths with
  the active project's kernel `media`/`media_locations` ownership rows.
- Only canonical locators inside this root's managed CAS namespace are
  admitted, and the bytes are rehashed against the kernel content hash before
  staging. Arbitrary sibling-project paths remain rejected.
- Remotion support performs this materialization check during its support probe,
  before renderer execution; the probe uses a disposable stage.
- `InvocationAssetServer` now serves GET/HEAD/OPTIONS with the bounded local
  CORS policy and exposes the Range response headers required by browser media
  loading. It still serves only the invocation staging directory.
- The render stage documentation now describes managed-media ownership and the
  browser-origin behavior.

Focused regression coverage: `tests/core/rendering/test_assets.py` — **27
passed**. It covers exact managed-path/hash admission, tamper rejection,
foreign/traversal rejection, staging cleanup, range serving, and CORS headers.
