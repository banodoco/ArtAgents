# Custody baseline — megado run 2026-08-28 (ffmpeg text extension)

## Source ref (immutable)
- Repo: Astrid (origin: https://github.com/peteromallet/Astrid.git)
- Base ref: branch `megado/oracle-run-storyboard`
- Pinned base SHA: `c6c505af9429ca20d0adae9534f4a303343307b9` (verified commit; HEAD of Astrid-megado at run start)
- Seed plan doc: `docs/ffmpeg-text-extension.md`, introduced at `46f1aff0`, clean/tracked at base SHA

## Run worktree
- Path: `/Users/peteromalley/Documents/reigh-workspace/Astrid-ffmpeg-oracle`
- Branch: `megado/oracle-run-ffmpeg-text` (created at pinned SHA; never merges itself to main)
- `.oracle/` created per skill: briefs, findings, checkins, rework, receipts, evidence

## Source checkout state (observed, NOT touched by this run)
- Working source: `~/Documents/reigh-workspace/Astrid-megado` on `megado/oracle-run-storyboard`
- Dirty: 538 status entries — modified `remotion/package.json`, `remotion/package-lock.json`, `remotion/src/fonts.ts`; deleted `.oracle/briefs/*` and other prior-run `.oracle` tracked files; untracked `.oracle/briefs/{ffmpeg-shots,reigh-app}/`, `.oracle/findings/{ffmpeg-shots,reigh-app-shot-structures.md}`, `remotion/public/`
- All of the above is user's active work; this run works exclusively in the new worktree at the pinned SHA.

## Environment identity
- macOS darwin 24.4.0, arm64, Apple M2
- grok CLI 1.0.5 (x.ai auth via ~/.grok/auth.json)
- launch_hermes_agent.py / fan.py at ~/.claude/skills/subagent-launcher/ (PYENV_VERSION=3.11.11)
- GLM selector verified live: `openrouter:z-ai/glm-5.3-flash`; Grok verified live: `grok-4.6`

## Worktrees at run start (all protected; never mutate)
Astrid (codex/live-ux-pre-phase-b-20260824) · /tmp/astrid-* probes · ~/Documents/Astrid-oracle (oracle-run) · Astrid-editor-bridge-integration · Astrid-live-main (main) · Astrid-main-mypy-audit · Astrid-megado (base) · Astrid-packification-oracle · Astrid-unified-oracle · Astrid-ffmpeg-oracle (this run)

## Policy
- Never touch `main` or any other worktree/branch.
- Push authorization at finish: explicit refspec `HEAD:megado/oracle-run-ffmpeg-text` to origin only.
