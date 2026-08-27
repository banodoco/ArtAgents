# Evidence matrix — storyboard layer run

| Criterion | Command/artifact | Result |
| --- | --- | --- |
| D1 schema/loader | `pytest tests/test_storyboard_schema.py -q` (17 passed) + live `validate` on 25-section intro (OK) | PASS |
| Compiler parity | `pytest tests/test_compiler_golden.py -q` (8 passed); compile output 76 clips / 50 assets / 177.53s | PASS |
| Managed-only imports | assets.json registry entries are CAS locators under .astrid/media/sha256 with content_sha256 | PASS |
| Timing independence | --vo-align plan.json start mapping + section timing default_hold override | PASS (vo-align used for render) |
| Variant flip proof | save v2 flipped ex_glitch → codex-pyramid; v3 reverted to final-html; kernel config_version 1→2→3 | PASS |
| Render | timelines render storyboard-intro-final → astrid-intro-storyboard.mp4 177.58s 1920×1080@30 | PASS |
| Frame fidelity | rendered frame @0.5s vs final-slides/open.png: mean-abs-diff 1.3/255 (codec noise only) | PASS |

Known gaps: no JSON-Schema artifact (validator module suffices per settled wave); gen variants require alt_render_path in v1; generationId omitted by policy.
