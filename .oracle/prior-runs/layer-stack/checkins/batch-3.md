# Checkpoint 3 — Batch 3 (Layer Stack) — PASS

Oracle: Grok 4.6. Delegated Flash facts + critique
(`.oracle/findings/oracle-b3-{facts,critique}.txt`).
Validated cited lines. Host: `45 passed`; ruff 1469=1469.

## PASS

Batch 4 may start.

**Delegated:** Flash facts + critique (`.oracle/findings/oracle-b3-{facts,critique}.txt`).
Host `pytest -q tests/packs/rendering/test_ffmpeg_compositor.py tests/packs/rendering/test_ffmpeg_finalizer.py tests/core/rendering/test_freeze.py` → **45 passed**. Ruff 1469=1469.

**Scope** (`edf0859a` vs `cf947761`): compositor dir + `pack.yaml` +1 + new compositor tests + freeze id only. Concat `finalizers/ffmpeg/` byte-identical. Freeze hunk is only `rendering.ffmpeg-compositor` (`test_freeze.py:397–399`).

**Filtergraph** (`run.py:615–749`): color base `[0]` `d=total_seconds` from `plan.total_frames` (646, 636–638, 882). `-## PASS

Batch 4 may start.

**Delegated:** Flash facts + critique — `.oracle/findings/oracle-b3-{facts,critique}.txt`. Host `pytest -q tests/packs/rendering/test_ffmpeg_compositor.py tests/packs/rendering/test_ffmpeg_finalizer.py tests/core/rendering/test_freeze.py` → **45 passed**. Ruff **1469=1469**.

**Scope** (`edf0859a` vs `cf947761`): new compositor dir, `pack.yaml` +1, compositor tests, freeze id only. Concat `finalizers/ffmpeg/` is byte-identical. Freeze hunk is only `rendering.ffmpeg-compositor` (`test_freeze.py:397–399`).

**Filtergraph** (`run.py:615–749`): color base `[0]` duration from `plan.total_frames` (646, 882). `-c:v libvpx-vp9` immediately before `-i` iff `alpha and vp9` (649–652). Per layer: optional `format=yuva420p`, scale/pad/setsar/fps/setpts; `colorchannelmixer` only when `opacity<1` (675–684). `overlay=0:0:format=auto:eof_action=pass` (687–693); no `alpha=`. `-t` pins length (745).

**`eof_action=pass`:** correct for top-short, z=0-short, both-short, and a short middle of N>2. Secondary EOF reveals the chain below (black base if nothing remains). `repeat` would freeze the dead layer — the stale fill the B1 note forbids.

**`support()`** (`388–417`): rejects `layer=None` (concat stays the only consumer), `blend≠normal`, `<2` distinct z, duplicate z. Unequal lengths are accepted and padded — right call vs the B1 note.

**Proofs:** real decode (select→PNG→PIL). Green box `(0,254,0)` / outside red `(252,0,0)`; short-top frame 8 red; zero-alpha all red; windows sum 20 vs `plan.total_frames=10`. Audio is lowest-z `RENDERED` (708–711), else `anullsrc`.

**Elegance:** 1083 vs concat 1620. Graph builder is one function. Helper duplication is cleanup, not B3.

Flash’s extra short-bottom pixel test is insurance, not a defect — DEFER to Batch 6.
