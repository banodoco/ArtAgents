# Rework tasklist — batch 1 attempt 1 (oracle triage)

Checkpoint B1 verdict: **FAIL** (oracle verification 2026-08-28):
- `tests/packs/rendering/test_ffmpeg_support.py` fails COLLECTION: SyntaxError line 75 `)def _media_timeline(...)` — malformed (stray `)`/dedent). The resume agent claimed the file's syntax was fixed, but the committed tree (e3c13deb) is NOT syntactically valid.
- `tests/packs/rendering/test_ffmpeg_backend.py` — not yet collected past the collection error.

Evidence: oracle runs above.

## Rework items (normal; executor deepseek-v4-flash)

### R1-1 — fix collection syntax (test_ffmpeg_support.py)
Locate and fix the malformed construct at line ~75 (and any sibling issues). Ensure the whole file parses: `python3 -c "import ast; ast.parse(open('tests/packs/rendering/test_ffmpeg_support.py').read())"` clean.

### R1-2 — full focused suite green
- `python3 -m pytest tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -q` → ALL pass.
- Watch for the T4 live-encode test (`test_live_encode_stills_text_wav`) — it must run (not hang >120s per-test timeout; the suite has a 120s signal timeout per test — it should finish or be marked fast). If it hangs, make the fixture smaller/faster, don't delete the test.
- renderer.yaml declares text; no remotion refs in the backend.

### R1-3 — commit
`git add -- <exact files>` + `git commit -m "megado B1 rework: fix test syntax + green ffmpeg suite (A5)"`. Never `-A`/`.`/`-am`. Never touch remotion/*, astrid/packs/shots/*, scripts/* (B3), astrid/packs/timeline/cli.py or astrid/sdk/invocation.py or astrid/core/timeline/* (B2's).

## After green
Fresh independent review pass against FULL B1 acceptance (T1–T4), then grok oracle check-in.