# m1 — Hygiene & Safety

## Outcome
A clean, honest repo a fresh contributor can actually clone-install-run: no secrets tracked, no
build/output artifacts under version control, lint advisory over `astrid/`, stale submodule + npm
paths fixed — PLUS a working install (declared deps, `[project]`, one env story, `doctor` wired in)
and the two trivial-but-high-visibility user gremlins fixed (unknown-command no longer silently runs
`hype`; README invocation is correct). This is the safe, **zero-cross-epic-collision** milestone — it
runs first. (Tier bumped solo→`directed` because of the folded onboarding/CLI work.)

## Scope (IN) — folded contributor-onboarding & user-gremlin fixes (HA4/HA2)
- **Make the install actually work.** Add a minimal `[project]` section to `pyproject.toml` (name,
  version, `requires-python`), move dev deps to `[project.optional-dependencies].dev`, verify
  `pip install -e '.[dev]'` succeeds. **Declare `runpod_lifecycle`** (imported in `core/runpod/sweeper.py`,
  `storage.py` but undeclared anywhere). (`pyannote.audio` is imported only by a *pack* executor — out of
  scope; note it for the pack track, don't fix here.)
- **Dep-audit via `doctor`.** Extend `astrid/doctor.py` with a check that every non-pack `astrid/` import
  resolves to a declared dependency, and **wire `python -m astrid doctor` into CI as an advisory lane** +
  reference it in README onboarding. (`doctor`/`setup_cli` exist today but are invisible — surface them.)
- **One env story.** Rationalize the four env files: `.env.example` is the template → contributor copies to
  `.env` (gitignored); `doctor` checks the required keys from `.env.example` are present; document the single
  "copy `.env.example` → `.env`" step in README; deprecate `this.env`/`.env.local` from the default search path.
- **Unknown-command guard (user gremlin).** `pipeline.py:347` `_dispatch()` has no `else`, so a mistyped verb
  silently runs `builtin.hype` with raw args. Add an **additive `else`** that prints "unknown command" to stderr
  and exits nonzero. (Additive only — the full CLI-dispatch unification stays in m5b; this is a 1-branch guard,
  zero restructure, so it does NOT collide with pack-taxonomy.)
- **README invocation fixes (docs hygiene).** Fix README:28 (`elements inspect <kind> <element_id>`, per
  `core/element/cli.py:72-78`) and README:38 (`out/runs/`, not `runs/`). Same "clean honest repo" principle as untracking artifacts.

## Scope (IN) — hygiene & safety (original)
- **Untrack secrets & flag rotation.** `git rm --cached this.env`; confirm `.gitignore`
  covers it. Record the follow-up **in the PR body and an "Open security follow-ups" section of
  `EPIC.md`** (NOT a new root-level `SECURITY-FOLLOWUP.md` — that bypasses the repo's
  `docs/megaplan/epics/` artifact convention): the `FAL_KEY` / `FIREWORKS_API_KEY` in `this.env`
  are exposed and require **manual** key rotation + history scrub by a human. Do NOT rewrite history.
- **Repo hygiene — untrack committed artifacts:** the 26 tracked `.DS_Store` files, root
  `__pycache__/` (throwaway `.pyc`), `out/*.comfy.log` + report markdowns, generated media
  under `runs/` (`*.mp4`, `*.png`), `scorecard.png` (root + `remotion/`), `plan_revision.json`.
- **Fix `.gitignore` rules that miss the repo root:** `*/out/` does not match root `out/`; add
  `/out/`. **Audit EVERY `*/x/` rule for the same root-miss class** — at least `*/cache/` (won't
  match root `cache/`), `*/__pycache__/`, `*/runs/` — and fix each. Verify
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
- **Turn the lights on — as an ADVISORY lane, not a blocking gate.** `pyproject.toml` lint/type
  config `include` lists `scripts/reshape/**` etc. but never `astrid/`. Extend ruff + mypy to cover
  `astrid/` AND wire the CI job so it is **allow-failure / baseline-compare**, not zero-findings-required.
  **This is critical:** the chain uses `stop_chain`, so a blocking lint gate over the un-remediated
  `astrid/` backlog would turn every later milestone's CI red and halt the epic. Prefer ruff's native
  baseline (`[tool.ruff]` config) over a separate markdown file. Record the baseline + a short note in
  the PR on **why `astrid/` was excluded in the first place** (is it un-lintable due to the structural
  issues m3/m4/m5 fix, or just an oversight?) so the baseline isn't freezing an unexamined decision.
  Do NOT attempt to fix the surfaced lint/type errors in this sprint — the baselined advisory lane IS the deliverable.

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
- `ruff check astrid/` and `mypy astrid/` both RUN, the CI job is **advisory/allow-failure or baseline-compare**
  (proven by a CI config diff), and a baseline is committed. A grep/test confirms the lint job cannot fail the build.
- The PR body + an `EPIC.md` "Open security follow-ups" section name the exposed keys and the manual rotation/scrub steps. No `SECURITY-FOLLOWUP.md` at root.
- `pip install -e '.[dev]'` succeeds (a `[project]` section exists); `runpod_lifecycle` is declared; `python -m astrid doctor` exits 0 on a correctly-set-up checkout and reports missing deps/env keys otherwise.
- `python3 -m astrid boguscmd` exits nonzero with an "unknown command" message on stderr (named test or scripted check) — it does NOT run hype.
- README:28 and README:38 match the actual CLI (verified by running `elements inspect …` and checking the output path); one documented "copy `.env.example` → `.env`" onboarding step exists.
- `npm install` no longer depends on a path that exists only on the author's machine (or the dep is documented optional).

## Touchpoints
- `.gitignore`, `.gitmodules`, `.git/modules/` (submodule dereg)
- `pyproject.toml` (ruff `include`, mypy config), `pytest.ini` (cross-check, leave correct)
- `package.json:11-12`
- `this.env` (untrack), root `out/`, `runs/`, `__pycache__/`, `scorecard.png`, `remotion/scorecard.png`, `plan_revision.json`
- New: `SECURITY-FOLLOWUP.md`, lint baseline file
