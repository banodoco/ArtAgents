# Exploration brief E1 — ffmpeg overlay/fade syntax on THIS machine

READ-ONLY exploration of the repo. Do all experiments in /tmp only. You are one of several parallel explorers feeding a plan revision. Goal: verified facts with commands + exit codes, ranked findings, <300 words.

Context: we will extend an ffmpeg filtergraph builder (`astrid/packs/rendering/backends/ffmpeg/command.py`, existing number formatting convention `:.6f`) to chain text-overlay PNGs onto a concat'd video spine. Planned filter per overlay: input via `-loop 1 -i <png>`, then `format=rgba`, optional `fade=t=in:st=AT:d=FADE_IN:alpha=1` and `fade=t=out:st=END-FADE_OUT:d=FADE_OUT:alpha=1`, then `overlay=0:0:enable='between(t,AT,END)':format=auto`.

Verify empirically (write scratch files under /tmp/e1 only):
1. `ffmpeg -version` — report exact version.
2. Generate a 3s test video (e.g. testsrc) and a small transparent PNG (PIL is available). Run ONE ffmpeg invocation with `-filter_complex` chaining: overlay input `format=rgba,fade=t=in:st=0.5:d=0.25:alpha=1,fade=t=out:st=2.0:d=0.25:alpha=1[ov];[base][ov]overlay=0:0:enable='between(t,0.5,2.25)':format=auto[v]`. Confirm exit 0.
3. Extract a frame at t=0.7 and t=1.5 (overlay visible window) and at t=0.1 (outside window); confirm the PNG content is visible in the first two and absent in the third (e.g. compare frame checksums or visually describe pixel deltas — `ffmpeg -ss <t> -frames:v 1` + PIL pixel check is fine).
4. Check how the existing code passes filter args: read `command.py` — are `-filter_complex` args passed as ONE argv element via subprocess list (no shell)? Does single-quote inside `enable='between(...)'` survive that (it must be literal for ffmpeg)? Report exactly what quoting works when there is NO shell layer.
5. Any pitfalls with decimal formatting in `between(t,...)` / `st=` (existing code uses `:.6f`)?

Report: exact working filter string(s), exit codes, frame-check results, risks. Do NOT modify the repo.
