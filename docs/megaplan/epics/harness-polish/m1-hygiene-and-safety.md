# m1 — Hygiene & Safety

## Outcome
A clean, honest repo: no secrets tracked in the working tree, no build/output artifacts
under version control, lint + type-check actually running over the `astrid/` package (with a
recorded baseline), and the stale submodule + machine-specific npm paths fixed. Nothing here
changes runtime behavior — it makes the repo safe to work in and surfaces the lint backlog.

## Scope (IN)
- **Untrack secrets & flag rotation.** `git rm --cached this.env`; confirm `.gitignore`
  covers it. Leave a clearly-named follow-up note (e.g. in this milestone's PR body and a
  `SECURITY-FOLLOWUP.md`) that the `FAL_KEY` / `FIREWORKS_API_KEY` in `this.env` are exposed
  and require **manual** key rotation + history scrub by a human. Do NOT rewrite history.
- **Repo hygiene — untrack committed artifacts:** the 26 tracked `.DS_Store` files, root
  `__pycache__/` (throwaway `.pyc`), `out/*.comfy.log` + report markdowns, generated media
  under `runs/` (`*.mp4`, `*.png`), `scorecard.png` (root + `remotion/`), `plan_revision.json`.
- **Fix `.gitignore` rules that miss the repo root:** `*/out/` does not match root `out/`; add
  `/out/`. Audit other rules (`*/__pycache__`, etc.) for the same root-miss class. Verify
  `tests/fixtures/**/*.mp4` and `avatars/*.png` that are INTENTIONAL assets are not collateral
  damage of blanket `*.mp4` / `*.png` rules — add negation rules (`!tests/fixtures/...`) as needed.
- **Remove the stale submodule:** `.gitmodules` references `astrid/packs/seinfeld/ai_toolkit/upstream`
  but `astrid/packs/seinfeld/` does not exist. Deregister the submodule cleanly
  (`git submodule deinit` / remove `.gitmodules` entry / `.git/modules` cleanup) so
  `git submodule update` stops failing. (This is the one allowed `packs/`-path touch — it's a
  dead submodule reference, not a pack refactor.)
- **Fix machine-specific deps:** `package.json:11-12` hardcodes
  `file:/Users/peteromalley/Documents/banodoco-workspace/...` for `timeline-ops` /
  `timeline-schema`. Make `npm install` work off the author's machine (relative path, published
  version, or documented optional-dep guard — pick what matches how these are actually consumed).
- **Turn the lights on:** `pyproject.toml` lint/type config `include` lists `scripts/reshape/**`
  etc. but never `astrid/`. Extend ruff + mypy to cover `astrid/`. **Record a baseline** of the
  resulting findings (committed file, e.g. `docs/lint-baseline.md`, or a ruff baseline config).
  Do NOT attempt to fix the surfaced lint/type errors in this sprint — the baseline IS the deliverable.

## Scope (OUT / anti-scope)
- **No git history rewrites, no force-push, no `filter-branch`/`filter-repo`.** History scrub is a flagged human follow-up.
- **No actual credential rotation** (happens in a vendor dashboard, not the repo).
- **Do not fix the lint/type backlog** that turning on coverage surfaces — only baseline it.
- **No pack refactors.** The only `packs/`-path action permitted is removing the dead seinfeld submodule entry.
- Do not delete `tests/fixtures` media or `avatars/` — those are (or may be) intentional assets; protect them.

## Locked decisions
- Use `git rm --cached` (untrack, keep on disk) for artifacts, not `git rm`.
- Secrets history-scrub + key rotation are explicitly deferred to a documented human follow-up.
- Lint coverage is turned on + baselined, not remediated.

## Open questions (resolve during plan)
- Which `runs/` and `out/` paths are genuinely generated vs. intentionally-kept reference assets?
  Inspect before untracking; when ambiguous, keep tracked and note it rather than risk deleting a kept asset.
- For `package.json` local file-deps: are `timeline-ops`/`timeline-schema` published anywhere, or
  is the JS/remotion path optional? Determine how they're consumed before choosing the fix.

## Constraints
- Reversible only. Every action is `--cached` untracking, gitignore edits, or config edits.
- The working tree on disk must be unchanged except for the intended config files.

## Done criteria
- `git status` is clean after the changes; `git ls-files` shows none of: `this.env`, `.DS_Store`,
  root `__pycache__/*.pyc`, `out/*.comfy.log`, `runs/*.{mp4,png}`, `scorecard.png`, `plan_revision.json`.
- `git submodule status` no longer references the missing seinfeld path; `.gitmodules` is consistent.
- `ruff check astrid/` and `mypy astrid/` both RUN (exit non-fatally on findings) and a baseline is committed.
- A `SECURITY-FOLLOWUP.md` (or PR-body section) names the exposed keys and the manual rotation/scrub steps.
- `npm install` no longer depends on a path that exists only on the author's machine (or the dep is documented optional).

## Touchpoints
- `.gitignore`, `.gitmodules`, `.git/modules/` (submodule dereg)
- `pyproject.toml` (ruff `include`, mypy config), `pytest.ini` (cross-check, leave correct)
- `package.json:11-12`
- `this.env` (untrack), root `out/`, `runs/`, `__pycache__/`, `scorecard.png`, `remotion/scorecard.png`, `plan_revision.json`
- New: `SECURITY-FOLLOWUP.md`, lint baseline file
