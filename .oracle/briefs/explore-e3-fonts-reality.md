# Exploration brief E3 — font availability + PIL reality on this machine

Mostly read-only; run small python3/ls checks. No repo modifications. One of several parallel explorers. Goal: verified facts, ranked findings, <300 words.

Context: plan adds a font resolver to `astrid/packs/rendering/backends/ffmpeg/text.py` using system TTFs: primary `/System/Library/Fonts/Supplemental/Arial.ttf` (+ Bold) on macOS, `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` on Linux. Fail-closed when missing. PIL (Pillow) rasterizes; Pillow>=12.2 is already a dependency. Bold/`params.weight>=600` selects the Bold face.

Verify empirically:
1. Exact filenames present: `ls /System/Library/Fonts/Supplemental/ | grep -i arial` — report the exact Bold filename (is it `Arial Bold.ttf`?).
2. Load test: `python3 -c` with `PIL.ImageFont.truetype('<path>', 30)` for Regular AND Bold — report success/failure and the resolved font family name (`.getname()`). Report the python3 used and Pillow version (`python3 -c "import PIL; print(PIL.__version__)"`).
3. Repo env: which python/pytest runs the suite (pyproject `[tool.pytest...]`, any PYENV pin in scripts/CI)? Does the repo's CI config reference Linux DejaVu paths or font setup?
4. Confirm PIL cannot load woff2 (ImageFont.truetype raises on woff2 — check docs/source; do not need to download a woff2, cite the limitation) and that the plan needs no fonttools.
5. grep the repo for existing DejaVu/Arial references (tests or code) that a font resolver must stay consistent with.

Report exact paths, versions, outcomes, risks (e.g. macOS font file naming differences across versions).
