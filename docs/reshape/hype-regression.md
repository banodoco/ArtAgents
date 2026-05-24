# Hype Regression Fixture

Sprint 0 pins a small hype artifact set for reshape regression checks at:

```bash
tests/fixtures/reshape/hype_regression/
```

The fixture is copied from the existing `examples/hype.*.json` artifacts:

- `hype.timeline.json`
- `hype.assets.json`
- `hype.metadata.json`
- `media_manifest.json`

Large media is intentionally not committed. `hype.assets.json` references
`main.mp4` and `broll.mp4`; the acquisition notes and small-file checksums live
in `media_manifest.json`.

## Smoke Test

Run the CI-safe fixture smoke:

```bash
pytest tests/reshape/test_hype_regression_fixture.py -q
```

Expected result without media present:

- required JSON fixtures parse and validate
- timeline media clip asset ids resolve through `hype.assets.json`
- media-dependent assertions skip with a message naming the missing mp4 files

## Optional Media Rerun

After recovering `main.mp4` and `broll.mp4` into the fixture directory, render
the pinned timeline with:

```bash
PYENV_VERSION=3.11.11 \
ASTRID_TIMELINE_COMPOSITION_SRC=$(pwd)/remotion/node_modules/@banodoco/timeline-composition/typescript/src \
python3 -m astrid.packs.builtin.render.run \
  --timeline tests/fixtures/reshape/hype_regression/hype.timeline.json \
  --assets tests/fixtures/reshape/hype_regression/hype.assets.json \
  --out /tmp/astrid-hype-regression/hype.mp4
```

Expected outputs:

- `/tmp/astrid-hype-regression/hype.mp4` exists and is non-empty
- the render uses `main.mp4` for source/audio clips and `broll.mp4` for the
  cutaway media clip
- no source media is written back into the repository
