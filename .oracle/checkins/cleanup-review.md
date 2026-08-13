# Oracle cleanup review — C0–C3 (cleanup-threejs @ 00ac93fc)

Delegated to DeepSeek V4 Flash via OMP (`--tools read,glob,grep,web_search`,
`--no-session`, `--auto-approve`). Five research-only briefs:

| Brief | Finding |
|---|---|
| `.oracle/briefs/cleanup-review-c0.md` | PASS |
| `.oracle/briefs/cleanup-review-c1a.md` | PASS |
| `.oracle/briefs/cleanup-review-c2.md` | PASS |
| `.oracle/briefs/cleanup-review-c3.md` | PASS |
| `.oracle/briefs/cleanup-review-elegance.md` | PASS |

Raw Flash output: `.oracle/findings/cleanup-review-{c0,c1a,c2,c3,elegance}.txt`

Oracle spot-check (not a re-review): remotion support mux only inside
`if request.profile is not None`; render uses `_remotion_mux_profile(request.profile or canonical)`;
threejs remotion import is only `_execute_remotion`; `git diff 856798fe HEAD -- astrid/core` empty.

**OVERALL: PASS.**Overall: PASS.** Cleanup is COMPLETE. `cleanup-threejs` may merge to main.

Delegated to DeepSeek V4 Flash via OMP (5 research-only briefs). Oracle spot-checked the provenance/mux seams. All five Flash verdicts: PASS. `git diff 856798fe HEAD -- astrid/core` is empty.

### d0878f64 C0 — PASS
- Literal move of 10/11 helpers; payload keys unchanged.
- `_canonical_profile(..., theme_path)` correct at remotion `:811,:889` and threejs `:367,:482`.
- Provenance fix is clean, not a hack: remotion keeps a local `_active_pack_order_for_provenance()` that passes `project_root=REPO_ROOT`, then injects `active_pack_order=` at its 3 payload sites so `patch.object(remotion, "REPO_ROOT")` still works.
- Remotion re-exports preserved; ffmpeg still imports remotion; `_shared` is core-only.

### a0f991bb C1a — PASS
- Support: `_remotion_mux_profile(canonical)` only inside `if request.profile is not None`.
- Render: `_remotion_mux_profile(request.profile or canonical)`.
- Threejs `_render_declared_profile` deleted; support `:357` + render `:468` call the shared helper. No 90000/AAC deletion.

### aa916f6e C2 — PASS
- `_probe` is the hybrid ∪ threejs union plus stream `duration` (the real-render regression fix). Extra fields are harmless; no consumer lost a field.
- Env-skip trio left in place (LEAVE). All 4 test files rewired.

### 00ac93fc C3 — PASS
- All 8 `@remotion/*` pinned 4.0.509; `extract-zip` absent.
- Lock churn is remotion-family + expected transitive re-resolve from `npm install` (esbuild/babel/mediabunny same-major). R3F 8.18.0 + three 0.185.1 still satisfy `@remotion/three` peers. Docs updated; `remotion_min_version: 4.0.455` left.

### Elegance — PASS
- Coupling 7 remotion helpers → 1 (`_execute_remotion`).
- `backends/_shared` is the right home (`_BACKEND_IMPL_PREFIX` auto-exempts it).
- LEAVE table respected. No over-engineering that blocks merge.
