# Reproducible release inputs

Astrid keeps publishable dependency ranges in `pyproject.toml`, but the release
gate never resolves those ranges directly. Release builds, installed-wheel
smokes, and factoring proofs use three universal, SHA-256-verified locks:

- `requirements/build.lock` pins the PEP 517 builder, backend, wheel writer,
  and their transitive dependencies. The canonical wheel is built with
  `--no-isolation` only after this lock is installed with `--require-hashes`.
- `requirements/runtime.lock` pins every public runtime dependency and
  transitive dependency for the supported CPython 3.11/3.12 Linux/macOS
  matrix. The wheel is then installed with `--no-deps --no-index`, followed by
  `pip check`, so wheel metadata cannot trigger a second resolution.
- `requirements/proof.lock` pins the runtime closure plus the test runner and
  timeout plugin used by source-copy and installed-wheel factorability proofs.
  Those proofs provision a disposable interpreter from this lock; they never
  use host or user-site packages.

Refresh and validate the locks deliberately:

```sh
make lock-build
make lock-runtime
make lock-proof
make lock-validate
```

Lock refresh requires `uv`; lock consumption requires only pip. Review every
version and hash diff like source code. Never hand-edit one pin without
regenerating the complete transitive lock.

The m8 installed matrix also writes `astrid.release_toolchain.v1` evidence.
It records the exact CPython patch and executable, GNU Make, Bash, Git, FFmpeg,
FFprobe, dependency-lock digests, Playwright package-lock digest, and the
installed Playwright Chromium revision/browser version. A missing tool, a
Python-series mismatch, a range/unhashed dependency, or Playwright drift fails
before the installed/browser lanes can be accepted.

`scripts/reshape/editor_browser_smoke/package.json` pins Playwright exactly;
`npm ci` verifies its integrity-bearing lock. The browser revision is read from
the installed `playwright-core/browsers.json`, not inferred from a moving
"current stable" label.

## Remotion adapter provisioning

The optional Remotion adapter is a separate, lockfile-owned Node closure. A
clean checkout must use Node **20.19.4** and npm **10.8.2**, recorded in the
repository `.node-version` and enforced by `remotion/package.json` plus
`remotion/.npmrc`. After installing that toolchain, run from the repository
root:

```sh
python3 scripts/reshape/remotion_gate.py all
```

The gate runs `npm ci` (never `npm install` or `npx`) from `remotion/`, checks
free space before and after installation, generates the renderer types, runs
`npm run typecheck`, and executes the blocking renderer-parity selector. It
refuses to start the install below 2 GiB free and does not provision or commit
`node_modules/`. CI uses the same exact Node/npm versions and lockfile.
