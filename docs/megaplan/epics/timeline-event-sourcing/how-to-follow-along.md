# How to follow along — timeline-event-sourcing epic on cloud

This is the operator handoff. You are an agent picking up a long-running megaplan chain that someone else launched. Your job is to **observe, unblock, and report** — not to redesign anything.

Read this whole file before doing anything else. Then read the linked skills if you need depth.

## What this is, in 30 seconds

- A 10-milestone megaplan chain making Astrid timelines event-sourced with a LocalFs + Supabase dual backend.
- Driven by `megaplan chain` on Railway in a persistent container (the "shared dev box" pattern).
- Each milestone produces a PR against `megaplan/git-backed-packs-chain-setup`. **You do not auto-merge. The user reviews and merges.**
- Profiles: m1+m5+m6 are `premium` end-to-end on codex; others are `partnered/full` (claude planner + critic, deepseek mechanical); m7 is `directed/light`. Robustness mixes `thorough` (m1/m5/m6) and `full` (the rest). See `chain.yaml` for the source of truth.
- All vendor=codex via Codex subscription (NOT metered OpenAI API key — see "Auth setup" below).

## Key paths and IDs

| Thing | Value |
|---|---|
| Project root (local) | `/Users/peteromalley/Documents/reigh-workspace/Astrid` |
| Epic dir | `docs/megaplan/epics/timeline-event-sourcing/` |
| Chain spec | `docs/megaplan/epics/timeline-event-sourcing/chain.yaml` |
| Cloud spec | `docs/megaplan/epics/timeline-event-sourcing/cloud.yaml` |
| Base branch | `megaplan/git-backed-packs-chain-setup` |
| Milestone branches | `epic/timeline/m{1,2,3,3p5,4,5,6,7,8,9}-*` |
| Railway project | `reigh-megaplan-dev` |
| Railway service | `astrid-git-backed-packs` (shared with other chains) |
| Remote workspace | `/workspace/timeline-event-sourcing/astrid` |
| `chain_session` (tmux) | `timeline-event-sourcing` |
| Chain log on box | `<workspace>/.megaplan/cloud-chain-timeline-event-sourcing.log` |
| Plans dir | `<workspace>/.megaplan/plans/` |
| Chain state | `<workspace>/.megaplan/plans/.chains/chain-a41bb294a504.json` |
| GitHub repo | `peteromallet/Astrid` |
| Required local env | source `~/.hermes/.env` for `DEEPSEEK_API_KEY`, `FIREWORKS_API_KEY` |
| Python for megaplan CLI | `PYENV_VERSION=3.11.11` prefix every `megaplan` call |

## The observation loop (run on every check-in)

Always run these first. Most questions answer themselves once you've seen the output.

```bash
# 1) Chain-level status: which milestone, which plan, terminal state if any
PYENV_VERSION=3.11.11 megaplan cloud status \
  --cloud-yaml docs/megaplan/epics/timeline-event-sourcing/cloud.yaml --chain

# 2) Tail the cloud-chain log (where the chain driver writes phase transitions)
railway ssh --service astrid-git-backed-packs -- \
  "tail -50 /workspace/timeline-event-sourcing/astrid/.megaplan/cloud-chain-timeline-event-sourcing.log"

# 3) Current plan's micro state (state + iter)
railway ssh --service astrid-git-backed-packs -- \
  "jq -r '{state: .current_state, iter: .iteration}' \
    /workspace/timeline-event-sourcing/astrid/.megaplan/plans/<PLAN_NAME>/state.json"
```

`<PLAN_NAME>` comes from `chain_state.current_plan_name` in the status output.

### Side-channel (when Railway is unreachable)

Railway has had ~6h outages. When `railway` commands return `error decoding response body` or `Unauthorized`, fall back to GitHub:

```bash
# Latest PR activity for the current milestone (proxy for chain progress)
gh pr view <pr_number> --repo peteromallet/Astrid \
  --json updatedAt,additions,deletions,commits | jq '{
    updatedAt, additions, deletions,
    n_commits: (.commits | length),
    last_commit: .commits[-1].committedDate,
    last_msg: .commits[-1].messageHeadline
  }'

# List epic branches (proxy for which milestone the chain is on)
gh api repos/peteromallet/Astrid/branches --paginate | \
  jq -r '.[] | select(.name | startswith("epic/timeline/")) | .name'
```

If GitHub shows new commits since your last check, the chain *was* progressing. If only one epic branch exists, only that milestone has run.

## Reading the signals — phase progression

The auto driver loops through these states per milestone (thorough/full robustness):

```
initialized → prepped → planned → critiqued → gated → revised → critiqued → gated → finalized → execute → executed → review → review_completed → done
```

- `state=initialized..finalized` — pre-execute, all reasoning. Commits land at init only.
- `state=execute` running — codex is writing code. This is the longest phase.
- `state=executed` — execute committed work to the milestone branch. Multiple `execute` commits per milestone are normal (each batch flushes).
- `state=worker_blocked` or `state=blocked` — execute hit a quality gate it couldn't pass. **Terminal. Needs intervention.**
- `state=failed` — phase exited with `internal_error`. Read the raw output (below) to find out why.
- `state=done` — milestone complete. Chain advances to next index.

Commits-per-phase reference (use to interpret PR commit history):

| Phase | Writes commits? |
|---|---|
| init | yes (one empty/init commit) |
| prep, plan, critique, gate, revise, finalize | no |
| execute | yes (one per batch) |
| review | no |

So a milestone PR with init + N execute commits and *no commits in a while* is most likely in review (healthy) **or** stalled in a non-commit phase (check `state.json`).

## Known failure modes — cookbook

### 1. `state=worker_blocked` with `execute blocked by quality gates`

This is the most common terminal state. Read the latest `phase_result.json` for the actual gate flags:

```bash
railway ssh --service astrid-git-backed-packs -- \
  "cat /workspace/timeline-event-sourcing/astrid/.megaplan/plans/<PLAN_NAME>/phase_result.json"
```

Look at the `quality_gate` entries. **Distinguish two cases:**

- **Environment bug** (missing pip dep, missing source file the executor noticed but refused to patch as "non-milestone"): the executor is right. Fix the env on the box, then re-init.
- **Plan-quality bug** (executor produced work review can't accept): bump tier or replan.

Recovery (environment bug — most common):

```bash
# Diagnose what's missing
railway ssh --service astrid-git-backed-packs -- \
  "cd /workspace/timeline-event-sourcing/astrid && python3 -c 'import <module>'"

# If it's a pip dep, install on the box
railway ssh --service astrid-git-backed-packs -- \
  "cd /workspace/timeline-event-sourcing/astrid && \
   /root/.pyenv/versions/3.11.11/bin/python -m pip install -r requirements.txt"

# Then clear the blocked plan + re-init m_N from scratch
railway ssh --service astrid-git-backed-packs -- \
  "rm -rf /workspace/timeline-event-sourcing/astrid/.megaplan/plans/<PLAN_NAME>/"

# Reset chain_state to current milestone, no plan
railway ssh --service astrid-git-backed-packs -- \
  "echo '{\"current_milestone_index\": <N>, \"current_plan_name\": null, \"last_state\": null, \"pr_number\": <N>, \"pr_state\": \"open\", \"completed\": [<prior labels>]}' > \
   /workspace/timeline-event-sourcing/astrid/.megaplan/plans/.chains/chain-a41bb294a504.json"

# Re-launch
set -a; source ~/.hermes/.env; set +a
PYENV_VERSION=3.11.11 megaplan cloud chain \
  --cloud-yaml docs/megaplan/epics/timeline-event-sourcing/cloud.yaml \
  docs/megaplan/epics/timeline-event-sourcing/chain.yaml
```

**Do not** try `megaplan override replan` on a `blocked` plan — it requires state in `{critiqued, failed, finalized, gated}`. You will get `invalid_transition`.

### 2. `state=failed` with `internal_error` and no useful stderr

Almost always a **credit/auth error masked as internal_error** (per megaplan-cloud gotcha #6). Read the phase's raw output:

```bash
railway ssh --service astrid-git-backed-packs -- \
  "tail -40 /workspace/timeline-event-sourcing/astrid/.megaplan/plans/<PLAN_NAME>/<phase>_v<N>_raw.txt"
```

Look for `Quota exceeded`, `Credit balance is too low`, `unauthenticated`, etc.

- **OpenAI quota exceeded**: codex CLI is using API key instead of subscription. Push subscription auth (see "Auth setup → Codex" below).
- **Anthropic credit low**: only `feedback` phase uses Claude in this chain. Refresh `CLAUDE_CODE_REFRESH_TOKEN` (see megaplan-cloud skill "Claude auth" section).
- **DeepSeek/Fireworks error**: check the key on the Railway service is current.

### 3. `.gitignore` swallows real source files

Pattern: executor's quality gate complains `ModuleNotFoundError: <some module>`, the module exists locally but `gh api repos/.../contents/...?ref=<branch>` returns `Not Found`.

```bash
git check-ignore -v <path>   # shows which gitignore line matches
```

If a real source file is matched by a too-broad credential glob (like `*secret*`), add an explicit exception:

```
*secret*
!astrid/core/util/secrets.py
```

Then `git add -f <path>`, commit, push. This was already done for `astrid/core/util/secrets.py` (commit `72b0c76`). If you find another, do the same and **only commit the gitignore + the rescued file** — don't bundle unrelated WIP.

### 4. Railway CLI broken (control plane outage)

`Failed to fetch: error decoding response body` from every railway command, including `whoami`. **Wait it out.** Use GitHub side-channel for observation in the meantime. Don't try to "fix" — it's their API.

### 5. Railway CLI unauthorized

`Unauthorized. Please login with railway login`. This is **interactive** — only the user can complete the OAuth. Tell them to run `! railway login` in their prompt. No agent workaround.

### 6. Container restarted → codex back on API key

If the Railway service restarts, the entrypoint re-runs `codex login --api-key` and clobbers `/root/.codex/auth.json`. Codex calls start returning quota errors.

Fix: re-push the local subscription auth:

```bash
B64=$(base64 -i ~/.codex/auth.json)
railway ssh --service astrid-git-backed-packs -- \
  "mkdir -p /root/.codex && echo '$B64' | base64 -d > /root/.codex/auth.json && \
   chmod 600 /root/.codex/auth.json"
```

This is a known bootstrap gap. Sustainable fix would be a Codex shim parallel to the Claude refresh-token shim — not built yet.

## Auth setup — what's wired and how

| Auth | How | Persistence |
|---|---|---|
| GitHub | `GITHUB_TOKEN` on Railway service; entrypoint configures git creds | persistent |
| Claude (only `feedback` phase) | `CLAUDE_CODE_REFRESH_TOKEN` shim, refreshes on every boot | persistent across restarts |
| Anthropic API (fallback) | `ANTHROPIC_API_KEY` on Railway | persistent but metered |
| OpenAI API | `OPENAI_API_KEY` on Railway. **Has been exhausted at least once.** Entrypoint authenticates codex with this on boot. | persistent but metered |
| **Codex subscription** | `/root/.codex/auth.json` pushed manually from local `~/.codex/auth.json` | **wiped on container restart** — see #6 above |
| DeepSeek | `DEEPSEEK_API_KEY` on Railway, sourced from `~/.hermes/.env` for deploy | persistent |
| Fireworks | `FIREWORKS_API_KEY` on Railway, sourced from `~/.hermes/.env` | persistent |

**Codex subscription is the right path for this chain** because the user has limited OpenAI metered credit but a Codex subscription. Verify with a one-shot codex call when in doubt:

```bash
railway ssh --service astrid-git-backed-packs -- \
  "cd /workspace/timeline-event-sourcing/astrid && \
   codex exec --sandbox read-only 'Reply with exactly: codex-subscription-works'"
```

If you see `Quota exceeded`, the auth.json got clobbered — re-push.

## What requires the human (do not do these yourself)

1. **`railway login`** — interactive OAuth. Ask the user to run `! railway login`.
2. **Merging a milestone PR** — `merge_policy: review` is set deliberately. The user reviews each milestone's PR before m_{N+1} starts. The chain stops with `on_failure: stop_chain` until the PR merges.
3. **Architecture decisions surfaced by critique/gate** — if a milestone surfaces an "open question" the brief didn't pin, escalate to the user. Do not invent the answer.
4. **Topping up metered credits** — only the user has billing access.
5. **Killing the chain or wiping the workspace** — destructive. Confirm first.

## The check-in loop

A `/loop 2h` cron is configured (job ID `24c16af6`, every 2h at `:07`) running this exact prompt:

> Check the timeline-event-sourcing chain progress on Railway. Run: 1. `megaplan cloud status --cloud-yaml … --chain`, 2. `railway ssh … tail …cloud-chain*.log`. Report: current milestone+phase, progressing (compare to prior), blocked/escalate states (use megaplan-observe), credit/auth errors, human-action items. Completed milestones. If nothing in 2h, escalate via `megaplan introspect`. Under 300 words. Observe-only.

`CronDelete 24c16af6` to stop it. Restart with `Skill: loop` and same arguments. **The loop is session-bound** — dies with the Claude session. For durable scheduling use `/schedule` per the schedule skill.

## Hands-off principle — what to never do

- Never `git push --force` to `megaplan/git-backed-packs-chain-setup` (the base branch).
- Never stash WIP to "clean up" (see `feedback_dont_stash_local_wip` memory). Commit alongside or leave alone.
- Never adjust `chain.yaml` profiles to escape a slow phase. Slow ≠ broken.
- Never delete a milestone PR without confirming with the user — the PR carries the commits.
- Never re-run `cloud deploy` with `secrets:` populated unless you intend to overwrite the Railway secret values (gotcha #5).
- Never invent answers to a brief's open questions — they're explicit user decisions.
- Don't redesign the epic in response to a transient failure. Fix the failure.

## Reading order for depth

When something doesn't fit this guide, in order:

1. `EPIC.md` in this dir — vision + milestone table
2. `m<N>-*.md` for the current milestone — locked decisions, scope, anti-scope
3. `~/.claude/skills/megaplan-observe/SKILL.md` — introspection cookbook
4. `~/.claude/skills/megaplan-cloud/SKILL.md` — cloud verbs + gotchas (the seven listed there are real)
5. `~/.claude/skills/megaplan-decision/SKILL.md` — for any "should I change the profile" instinct
6. The actual `cloud-chain-timeline-event-sourcing.log` on the box — ground truth

If after reading you still don't know what to do, **report what you see to the user and stop**. A wrong-but-confident intervention costs more than a flat check-in.

## Summary command set

The five commands that solve 95% of operator work:

```bash
# Observe
PYENV_VERSION=3.11.11 megaplan cloud status --cloud-yaml docs/megaplan/epics/timeline-event-sourcing/cloud.yaml --chain
railway ssh --service astrid-git-backed-packs -- "tail -50 /workspace/timeline-event-sourcing/astrid/.megaplan/cloud-chain-timeline-event-sourcing.log"

# Diagnose a blocked plan
railway ssh --service astrid-git-backed-packs -- "cat /workspace/timeline-event-sourcing/astrid/.megaplan/plans/<PLAN_NAME>/phase_result.json"

# Re-launch after fixing env (no replan — see #1 above)
set -a; source ~/.hermes/.env; set +a
PYENV_VERSION=3.11.11 megaplan cloud chain --cloud-yaml docs/megaplan/epics/timeline-event-sourcing/cloud.yaml docs/megaplan/epics/timeline-event-sourcing/chain.yaml

# Confirm codex subscription is live
railway ssh --service astrid-git-backed-packs -- "cd /workspace/timeline-event-sourcing/astrid && codex exec --sandbox read-only 'Reply with exactly: codex-subscription-works'"
```

That's the job. Observe, surface, unblock with the smallest move, escalate when the choice is the user's.
