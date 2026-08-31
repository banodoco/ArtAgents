# Iteration Assemble Executor

`iteration.assemble` writes render adapter files for `rendering.render`. The
public `video_editing.iteration_video` route supplies runtime-derived manifest
and quality mappings directly; the `prepare_dir` input remains only as a
file-backed compatibility form for direct assembler calls.

Inputs:

- `iteration.manifest.json`
- `iteration.quality.json`

Outputs:

- `iteration.timeline.json`
- `iteration.manifest.json`
- `iteration.report.html`
- `iteration.quality.json`
- `hype.timeline.json`
- `hype.assets.json`

The executor does not re-walk provenance and does not summarize. It resolves
renderers by artifact `kind`, uses `generic_card` loudly for unsupported kinds,
and refuses `data_quality < 0.6` before adapter files are created unless
`--force` is supplied.

Only `--mode chaptered` is supported in v1. `--direction` is preserved as a
label; it is not parsed into structured creative instructions.
