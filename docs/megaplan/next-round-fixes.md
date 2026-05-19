# Astrid CLI legibility round — next-round fixes brief

**Profile:** `solo/light +prep` (tier 1 DeepSeek end-to-end, light robustness, prep phase enabled for investigation).

## Outcome

Close the **system-says vs system-means gap** at four specific decision points the v7 dogfood surfaced. Each fix moves an implicit constraint (currently hoped for via brief text, or silently fail-closed) into an explicit signal at the moment of decision — either via runner-side enforcement (deliverable contracts) or via informative CLI behavior (in-system contracts). After the fixes land, a targeted retest of 3–5 affected scenarios validates each — no full v8 dogfood until those targeted runs are clean.

## Scope (~1 sprint, ≤2 weeks)

**IN:**
- Investigation: read 3 specific v7 reports and root-cause why brief tightening worked for some scenarios but not others.
- Fix A — `tests/agentic/runner.py` post-actor enforcement:
  - Detect reports <30 non-blank lines → re-prompt the actor for one revision turn.
  - Detect canonical-bypass invocations in stderr (`python -m astrid.packs.*` patterns, direct `run.py` execution) → reject and re-prompt with canonical syntax.
- Fix B — `astrid/core/task/lifecycle.py:_most_recent_session_slug`: when `len(candidates) > 1`, print an enumerated, actionable refusal to stderr before returning None.
- Fix C — `astrid author patch` (or whatever the verb is named locally; investigate file location in prep): emit a stderr nudge on success that points to `astrid author check <id>`.
- Fix D — `wrap_comfy_workflow` rc=7 + 0-line report: investigate root cause, fix in place (one of: brief, scenario priming, actor harness handling, or runner failure-surfacing).
- Targeted retest: 3–5 scenarios re-run via `tests/agentic/runner.py` (NOT a full --all dogfood). Specifically: `cross_pack_composition`, `search_before_authoring`, `concurrent_disambiguation`, `modify_existing_orchestrator`, `wrap_comfy_workflow`. Plus any regressed scenario discovered in prep.

**OUT (explicit anti-scope):**
- No empty `STAGE.md` content fills — separate sprint.
- No new rubric questions, no new scenarios, no changes to `assessor.py` / `universal_checks.py` / `pattern_finder.py` / `meta_test.py`.
- No full v8 dogfood — that's the user's separate kickoff.
- No fixing the `generate_image/executor.yaml` float-type bug (separately ticketed).
- No commits, no stashing, no cleaning up the 149+ uncommitted working-tree files.
- No edits to `astrid/core/session/binding.py` — already settled by prior sprint's Fix #1.
- No "while we're here" brief rewrites — brief text proved low-leverage; we're moving leverage into the runner and CLI.

## Locked decisions

1. **Enforcement layer**: runner-side for deliverable contracts (Fix A), CLI-side for in-system contracts (Fixes B + C). Briefs are *informational only* going forward — they don't carry mechanical weight.
2. **Response mechanism per fix**:
   - **Fix A.1 (short report)**: **reprompt** — accept the actor's attempt, dispatch ONE follow-up turn asking "expand each section with at least 2 substantive sentences. Aim for ≥30 non-blank lines total." Cap re-prompts at 1 per scenario per dogfood; if still short after the re-prompt, the scenario is marked `report_shape: fail` in summary.json.
   - **Fix A.2 (canonical bypass)**: **reject + reprompt** — when stderr shows a bypass invocation pattern, dispatch ONE follow-up turn with: "you invoked `<verb> <pattern>`; the canonical CLI is `astrid <kind> run <id> [...]`. Retry using the canonical form, then continue with the report." Cap at 1 per scenario; if the agent bypasses again, mark `canonical_bypass: rejected` in summary.json. Don't kill the scenario — let the actor finish; the auditor will catch repeat bypass.
   - **Fix B (concurrent disambiguation)**: **reject with info** — stderr nudge listing candidate slugs + the exact `--project <slug>` flag the agent needs to use next. Then return None as today (no behavioral change to the failure semantics).
   - **Fix C (author check nudge)**: **guide** — stderr-only suggestion at the success edge of `author patch`. No enforcement, no blocking.
3. **Re-prompt mechanism for Fix A**: use the same `launch_hermes_agent.py` path, with `--session-id <prior-session-id>` if the launcher supports resuming the actor's session; otherwise dispatch a fresh call with the original brief + the original report.md + the explicit re-prompt instruction in the user message. Verify the launcher's session-resume capability in prep.
4. **Investigation findings drive Fix D**: don't pre-design Fix D in this brief beyond "make the failure legible." Prep determines the root cause; plan picks the right fix shape.
5. **Targeted retest only**: don't run the full 13-scenario dogfood. The 5 named scenarios above are the ones with new findings or expected fixes. Each individual scenario takes ~5–15 min; the targeted retest is ~30–60 min wall-clock total.

## Open questions (for prep phase to resolve)

These are the unknowns the prep phase MUST disambiguate before plan commits:

1. **Why did brief tightening land for `cross_pack_composition` (FAIL → PASS) but not `search_before_authoring` (still FAIL on canonical_bypass)?** Read both v7 reports + stderr at:
   - `tests/agentic/reports/20260518-172010-cross_pack_composition/agentic-cross-pack-composition-ds-1.{report.md,stderr.log}`
   - `tests/agentic/reports/20260518-172010-search_before_authoring/agentic-search-before-authoring-ds-1.{report.md,stderr.log}`

   Specifically: what canonical-bypass form did each agent use? Is the bypass pattern different (e.g., `python -m astrid.packs.builtin.hype.run` vs `python -c 'import astrid.packs...'` vs running the pack's `run.py` directly by path)? The detector in Fix A must cover *all* observed patterns.

2. **Why did `new_orchestrator_from_dsl` regress (PASS in v6 → FAIL in v7 on `contradiction_in_report`)?** The contradiction was "DSL-compiled orchestrators run via `astrid start`" claim vs no `astrid start` in stderr. Was the agent confused by added brief instructions? Did Fix #3's post-completion handoff change behavior in a way that broke this scenario's path? Read:
   - `tests/agentic/reports/20260518-172010-new_orchestrator_from_dsl/agentic-new-orchestrator-from-dsl-ds-1.{report.md,stderr.log}`
   - v6 counterpart at `tests/agentic/reports/v6-20260518-152457-new_orchestrator_from_dsl/` for comparison.

3. **What caused `wrap_comfy_workflow` to exit rc=7 with 0-line report?** Read:
   - `tests/agentic/reports/20260518-172010-wrap_comfy_workflow/agentic-wrap-comfy-workflow-ds-1.stderr.log`
   - `tests/agentic/scenarios/wrap_comfy_workflow.yaml` (the scenario spec — possibly the brief is unsatisfiable)
   - `tests/agentic/briefs/wrap_comfy_workflow.md`

   Four possible root causes to discriminate between:
   - Brief asks for ComfyUI-related work that requires a running ComfyUI server (not available on this machine).
   - Actor harness timed out and was killed mid-run, never wrote the report.
   - API rate limit during the actor call.
   - Scenario priming bug (e.g., missing fixture file the agent needed).

4. **Does the hermes-agentic launcher support session resume via `--session-id`?** Read `~/.claude/skills/subagent-launcher/launch_hermes_agent.py` to confirm. If yes, Fix A's re-prompt path is cheaper (one extra turn on the existing session). If no, Fix A must construct a fresh call with the original brief + prior report as context.

5. **Where does `astrid author patch` print its success message?** Likely in `astrid/core/author/cli.py` or similar — find the success-edge for Fix C's nudge to live next to.

## Constraints

- **Working tree is preserved.** ~149 files modified, load-bearing. Do NOT stash, reset, checkout, or otherwise touch the user's git state. Past sub-agent attempts violated this; do not.
- **No commits.** The user owns the staging decision after the sprint lands.
- **The parallel-runner-sprint (`parallel-runner-sprint`) is in flight.** It touches `astrid/core/task/lifecycle.py`, `tests/agentic/runner.py`, and `tests/agentic/auditor.py`. Verify before edits to those files: `python3 -c "import json; print(json.load(open('.megaplan/plans/parallel-runner-sprint/state.json'))['current_state'])"` — must return `done` or `executed` before this sprint touches those files. Poll every 60s until clear.
- **Same DeepSeek API account as the rest of this session.** The user topped it up; subsequent calls should succeed. If a 402 (insufficient balance) error returns mid-sprint, pause via `megaplan override add-note --note "balance exhausted, awaiting top-up"` and report back; do NOT escalate the profile.
- **The narrative-fallback widening in `tests/agentic/auditor.py` `_eval_tool_used` remains in place.** Don't tighten it back up in this sprint — the assessor + universal_checks layer compensates, and rolling it back now would regress the v6+ test suite.
- **Targeted retest, NOT a full dogfood.** The user runs the full v8 themselves after the sprint lands.

## Done criteria

1. **Investigation report**: a short markdown summary in the megaplan plan dir documenting findings for the 5 prep questions above. Specific (cites file paths, quotes evidence), not hand-wavy.
2. **Fix A landed in `tests/agentic/runner.py`**:
   - `_run_one` calls a new `_check_report_shape(report_path) -> bool` after actor completion; if it returns False, dispatches one re-prompt turn.
   - `_run_one` calls a new `_check_canonical_bypass(stderr_path, scenario_cfg) -> str | None` after actor completion; if it returns a bypass-pattern string, dispatches one re-prompt turn.
   - Re-prompt cap is enforced (1 per check per scenario).
   - Both checks respect `assessment.bypass_exempt: true` in scenario YAMLs (the authoring scenarios that legitimately author new pack code).
3. **Fix B landed in `astrid/core/task/lifecycle.py`**: `_most_recent_session_slug` (or its caller) prints an enumerated stderr message before returning None on >1 candidates. The message includes:
   - The count of candidates.
   - The slug of each candidate (one per line).
   - The exact `--project <slug>` flag syntax to use.
4. **Fix C landed wherever `astrid author patch` lives** (resolved in prep): after the verb prints its success message, also print `recommended next: astrid author check <id>` (where `<id>` is substituted from the patched orchestrator's id).
5. **Fix D landed**: the root cause from prep is addressed. At minimum, the actor's rc != 0 case in the runner writes an explicit `<slug>.actor_failed.txt` marker with stderr capture, and the auditor's `_audit_one_agent` recognizes this marker and surfaces a hard fail (not a silent skip).
6. **Targeted retest**: each of the 5 named scenarios produces a `summary.json` with the relevant rubric questions now passing (or, for `wrap_comfy_workflow`, a non-silent failure with a clear reason in `agents[].error` or `agents[].universal`).
7. **Unit tests**: `pytest tests/ --ignore=tests/agentic/ -k "session or lifecycle or author"` is green. The new re-prompt path in runner.py has a small smoke test exercising the short-report case (mock the actor; verify exactly one re-prompt fires).

## Touchpoints

- `tests/agentic/runner.py` — Fix A
- `astrid/core/task/lifecycle.py` — Fix B
- `astrid/core/author/cli.py` (or wherever `author patch` lives — resolved in prep) — Fix C
- One of `astrid/packs/wrap_comfy_workflow/...`, `tests/agentic/scenarios/wrap_comfy_workflow.yaml`, `tests/agentic/briefs/wrap_comfy_workflow.md`, or `tests/agentic/runner.py` (rc!=0 surfacing) — Fix D, depending on root cause
- `tests/agentic/reports/20260518-172010-*/` — read-only; prep reads, no writes
- `.megaplan/plans/parallel-runner-sprint/state.json` — read-only; poll for completion

## Anti-scope

- Do NOT add new rubric questions to scenarios.
- Do NOT change the assessor or universal_checks modules.
- Do NOT touch `astrid/core/session/binding.py` — settled.
- Do NOT add more brief text. The v7 data shows brief-text leverage is saturated.
- Do NOT run the full v8 dogfood — targeted retest only.
- Do NOT commit, push, or otherwise alter git state.
- Do NOT tighten the narrative-fallback in `auditor._eval_tool_used`.
- Do NOT introduce parallel scenario execution — that's the parallel-runner sprint's job.

## Meta-rationale (why these specific fixes, not others)

These four fixes are all instances of one move: **closing the system-says vs system-means gap.** The system already knows the rules (reports should be substantive, canonical CLI is the right path, concurrent ambiguity must be resolved, patches should be validated). What's been missing is the system *saying* those rules at the moment of decision, in the channel the agent is already watching.

- **Fix A** moves "reports should be ≥30 lines" and "no `python -m astrid.packs.*`" from brief text (proven low-reach by v7) to runner-side enforcement (mechanical, can re-prompt).
- **Fix B** moves "if ambiguous, you need `--project`" from silent fail-closed to enumerated stderr nudge — the agent's only signal becomes informative.
- **Fix C** moves "after patch, validate with check" from implicit workflow knowledge to explicit CLI suggestion at the success edge.
- **Fix D** moves silent rc=7 from invisible to legible — pipeline credibility requires that failures are loud.

We're not adding capability. We're surfacing constraints the system already enforces, at the point where surfacing them is useful. The brief-text lever has been demonstrated saturated; this round shifts to the leverage that actually moves behavior.

## Why `solo/light +prep`

- **`solo`** (tier 1, DeepSeek end-to-end): no novel architecture, no production-critical surfaces, no design that benefits from premium reasoning. Each fix is mechanical pattern-matching against existing CLI conventions or runner conventions.
- **`light`** robustness: one critique pass earns its cost given that v7 surfaced a regression (we want a sense-check that the planner accounts for unknown root causes), but `full` would add `gate`+`review` overhead the work doesn't need.
- **`+prep`**: the 5 open questions are research-bounded — the prep phase resolves them by reading specific files, then the plan phase commits to fix shapes based on findings. Without prep, the plan would have to invent answers.
- **No depth bump**: tier 1 has no premium phases; depth is moot.
- **No vendor / critic / feedback flags**: irrelevant at tier 1.

Shorthand: `solo/light +prep`.
