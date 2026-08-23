# Reproducible release inputs

Astrid keeps publishable dependency ranges in `pyproject.toml`, but the release
gate never resolves those ranges directly. Release builds and installed-wheel
smokes use two universal, SHA-256-verified locks:

- `requirements/build.lock` pins the PEP 517 builder, backend, wheel writer,
  and their transitive dependencies. The canonical wheel is built with
  `--no-isolation` only after this lock is installed with `--require-hashes`.
- `requirements/runtime.lock` pins every public runtime dependency and
  transitive dependency for the supported CPython 3.11/3.12 Linux/macOS
  matrix. The wheel is then installed with `--no-deps --no-index`, followed by
  `pip check`, so wheel metadata cannot trigger a second resolution.

Refresh and validate the locks deliberately:

```sh
make lock-build
make lock-runtime
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

