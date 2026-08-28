# EXECUTOR REWORK BRIEF — BATCH 1 ATTEMPT 2 (A5 ffmpeg text + stills + overlay)

Your first commit e3c13deb + a rework attempt left B1's suite RED. The frozen original brief is .oracle/briefs/exec/batch-1-deepseek.md (T1-T4 acceptance). Oracle-verified failures (run them):

PYENV_VERSION=3.11.11 python3 -m pytest tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -q

CURRENT FAILURES (8 support + 2 backend):
1. test_support_accepts_text_clip — clip 'title' has unsupported kind 'text-card'; clips reference missing asset 'main'. Fixture uses text-card kind + missing assets. Decide: the test fixture must use supported clipType 'text' (not 'text-card') + valid asset refs, OR support.py must accept 'text' only (it does). FIX THE FIXTURE to use clipType 'text' and valid assets.
2. test_support_accepts_extra_text_tracks — 'requires exactly one visual track' + 'text clip requires exactly one visual track' + 'needs at least one visual media clip'. support.py REJECTS exactly what T2 requires (extra text-only tracks + stills+text). The relaxation in support.py is incomplete/wrong: it must ACCEPT 1 visual media track + N text-only tracks, with at least one visual media clip. Read the frozen T2 acceptance; fix support.py gates.
3. test_support_accepts_text_fades, test_support_text_to_rgba_png_integration, test_support_text_fallback_to_bold_variant — 'needs at least one visual media clip' → these fixtures likely lack a visual media clip; add one or fix support to accept text+media properly.
4. test_support_rejects_media_with_overlapping_clips, test_support_rejects_audio_fades_on_text, test_support_text_params_validation — assert False: the reject cases are NOT being rejected (support over-accepts). Fix so these still fail closed.
5. test_build_render_command_encodes_visual_only_without_synthesizing_silence — NameError: name 'video_clips' is not defined in command.py. Fix.
6. test_live_encode_stills_text_wav — RenderRequest.__init__() got an unexpected keyword argument 'input_path'. Fix the test to use the correct RenderRequest field (timeline_path + schema_version per the existing suite).

ACCEPTANCE:
- python3 -m pytest tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -q  → ALL PASS.
- T2 boundary: media+text supported; stills+text+extra-text-tracks+text-fades supported; speed/crop/media-overlap/media-effects/unknown kinds/bare-text-no-visual FAIL CLOSED.
- renderer.yaml declares text. No remotion refs in the backend.
- Scope: only astrid/packs/rendering/backends/ffmpeg/{text.py,support.py,renderer.yaml,command.py} + tests/packs/rendering/{test_ffmpeg_support.py,test_ffmpeg_backend.py}. NEVER remotion/*, astrid/packs/shots/*, scripts/*, astrid/core/*, astrid/sdk/*, astrid/packs/timeline/*.
- Commit: git add -- <exact files> && git commit -m "megado B1 rework: green ffmpeg support + backend suites (A5)". Never -A/./-am.

Report: each failure → root cause → fix, full pass counts, commit sha.
