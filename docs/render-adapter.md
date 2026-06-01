# Render Adapter — Banodoco Publishability Decision Record

**Status**: active (SD2, 2026-06-01)  
**Scope**: How the Remotion render path consumes `@banodoco/*` packages and why
they remain adapter-installed rather than published dependencies.

## Packages

Three `@banodoco` scoped npm packages are required by the Remotion render
compositor in `remotion/`:

| Package | Purpose |
|---|---|
| `@banodoco/timeline-composition` | Remotion composition root, theme API, and codegen plugin registry |
| `@banodoco/timeline-schema` | Canonical `TimelineConfig` Zod schema shared by CLI and editor |
| `@banodoco/timeline-theme-2rp` | 2RP theme package (effect components, theme.json, per-effect schema) |

## Current Publishability Blockers

All three packages are **not publishable** to a public npm registry. The
blockers:

1. **`private: true`** — Each `package.json` declares `"private": true`,
   which blocks `npm publish` by design. The packages were authored as
   workspace-internal modules, not public distribution units.

2. **No LICENSE files** — None of the three package directories contain a
   `LICENSE` file. A license declaration (in `package.json` and/or a
   `LICENSE` file) is required before any public or even private-registry
   publication that carries redistribution rights.

3. **`@banodoco` npm org path not established** — The `@banodoco` npm
   organization is not registered or configured as a publication target.
   Even if `private` were removed, there is no destination registry, no
   CI publication workflow, and no versioning policy for these packages
   as independent artifacts.

## Adapter Path (Current State)

Until publication blockers are resolved, the render path consumes these
packages through an **adapter install** — the `remotion/package.json`
declares them as GitHub tarball dependencies:

```json
"@banodoco/timeline-composition": "https://github.com/banodoco/timeline-composition/archive/refs/tags/v0.0.6.tar.gz",
"@banodoco/timeline-theme-2rp": "https://github.com/banodoco/timeline-theme-2rp/archive/refs/tags/v0.1.1.tar.gz"
```

(`@banodoco/timeline-schema` is pulled transitively as a dependency of
`timeline-composition`.)

The render executor (`astrid/packs/rendering/executors/render/run.py`)
validates that `node_modules/` exists after `npm install` **and** that
each of the three `@banodoco/*` package directories is present.  It fails
with a clear message naming the missing package(s) and pointing at this
document — it does **not** pull these packages into the Python package
graph. The default `pip install astrid` (or `pip install
astrid.whl`) does not require Node.js, npm, Remotion, or any `@banodoco`
package.

## Owner Actions Required Before Publishing Can Replace the Adapter Path

Before the adapter path (GitHub tarball → npm registry package) can be
replaced, the package owner must complete these actions:

1. **Add LICENSE files** — Choose an open-source license (e.g., MIT,
   Apache-2.0) and add a `LICENSE` file to each package root. Update
   `"license"` in each `package.json`.

2. **Remove `private: true`** — Set `"private": false` or delete the key
   from each `package.json`.

3. **Establish the `@banodoco` npm org** — Register or configure the
   `@banodoco` scope on the target registry (npmjs.com or a private
   registry). Add the `publishConfig` block to each `package.json` if a
   non-default registry is used.

4. **Set a versioning policy** — Decide whether these packages version
   independently or in lockstep. Tag releases (`v0.X.Y`) and ensure
   `remotion/package.json` can pin to semver ranges instead of tarball
   URLs.

5. **Wire CI publication** — Add a publication workflow (e.g., GitHub
   Actions) that runs `npm publish` on tag push, with appropriate
   credentials.

6. **Update `remotion/package.json`** — Replace the GitHub tarball URLs
   with semver-ranged npm dependencies (e.g.,
   `"@banodoco/timeline-composition": "^0.1.0"`).

7. **Update the render executor guidance** — Update the error message in
   `astrid/packs/rendering/executors/render/run.py:_validate_project_dir`
   to point at the published package names instead of the adapter install
   instructions. Update this document to reflect the new state.

## `timeline-theme-2rp` — Optional / Adapter-Local

`@banodoco/timeline-theme-2rp` is a **theme package**, not a core render
dependency. The Remotion compositor resolves themes at runtime and applies
a fallback `banodoco-default` theme when no theme is specified (see
`astrid/packs/rendering/executors/render/run.py:_theme_for_props`).

This means:
- **For Python installs**: `timeline-theme-2rp` is never in the Python
  dependency graph. It lives exclusively in the adapter (Remotion) side.
- **For render users**: If a timeline references the `2rp` theme slug,
  the theme package must be installed in `remotion/node_modules`. This
  is handled by the existing adapter install path.
- **For default Python import**: `import astrid` does not touch any npm
  packages, Remotion, or theme data. The render adapter is opt-in and
  only activated when explicitly invoking `rendering.render`.

## Rule: Default Python Install Must Not Depend on Render Packages

This decision record enforces a hard gate: **`pip install astrid` (or
wheel install) must never require Node.js, npm, Remotion, or any
`@banodoco` package.** The render path is an optional runtime adapter
that users opt into by:

1. Installing Node.js and npm
2. Running `npm install` in `remotion/`
3. Invoking `rendering.render`

The render executor fails closed — if `node_modules/` is absent or any
required `@banodoco/*` package directory is missing, it raises
`FileNotFoundError` with guidance (including a pointer to this document)
before any `@banodoco` import is attempted. This keeps the default
Python SDK importable on any machine with only Python dependencies.

## Related Documents

- [adapter-packs.md](adapter-packs.md) — General adapter pack conventions
- [STAGE.md](../astrid/packs/rendering/executors/render/STAGE.md) — Render executor stage documentation
- `astrid/packs/rendering/executors/render/run.py:_validate_project_dir` — Fail-closed validation
- `remotion/package.json` — Adapter dependency declarations
- SD2 gate decision — `state.json` settled decision record
