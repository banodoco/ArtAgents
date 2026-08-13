I'll re-review Batch 7 independently against the r3 FAILs and the claimed SHA-independent verification record. Starting with the review protocol and the current worktree state.I'll pull the prior verdicts, verification record, and tasklist, then independently check the r3 FAIL and the five r2 code claims.Prior check-ins and Batch 7 acceptance criteria are next, then I'll verify the tag/HEAD claim and the five r2 code fixes independently.The r3 record treated leftover Batch 7 contracts as still blocking; I'll read the frozen acceptance criteria and independently check HEAD, the tag, and the five r2 fixes.I'll verify HEAD vs the tag, the five r2 code claims, and the leftover frozen Batch 7 criteria in parallel rather than take the host framing as given.I'll independently verify each claimed r2 fix from the current sources and quote exact file:line evidence.I'll gather exact git and file evidence from the worktree without changing anything.Next I’ll check smoke artifacts, replay tests, help text`.git, and Batch 7 leftovers` looks like a work.tree pointer, not a full repo. I’ll resolve the git dir and keep collecting tag, index, and file evidence.HEAD matches the tag. Next I’ll re-run the claimed tests and inspect leftover frozen Batch 7 acceptance items instead of treating the host summary as complete.HEAD and the C8 tag both resolve to the same SHA. Next I’ll read the commit objects, tag log, and index-related files so the remaining command outputs are exact.## Claimed r2 fixes

| Claim | Result | Evidence |
|---|---|---|
| 1. Smoke default is a temp dir, never cwd | **PASS** (stale help + leak) | Default `out_path` is `tempfile.mkdtemp(prefix="astrid-smoke-") / f"smoke-{id}.mp4"`, not `Path.cwd()` (`astrid/core/rendering/cli.py:591-598`). Invocation workspace is a cleaned `TemporaryDirectory` (`603`). Help still says `./smoke-<id>.mp4` (`196`). Published default uses **`mkdtemp` (leaks)**; only the workspace uses `TemporaryDirectory`. |
| 2. Committed smoke artifacts gone | **PASS** | `smoke-wave.wave.mp4`, `.lock`, and `.provenance.json` are ENOENT at repo root. No `smoke-wave` string under `.git`. Remaining `*smoke*` paths are scripts/tests (`scripts/smoke_*.sh`, `remotion/__smoke__/`, etc.), not those artifacts. (`*.mp4` is gitignored at `.gitignore:54`.) |
| 3. Replay copies entire bundle dir | **PASS** | `_cmd_replay` `copytree`s whole `bundle_dir` with `dirs_exist_ok=True` (`855-862`). No `source.is_file()` filter. Comment states bundle.json + request.json + `inputs/<sha>` tree (`855-857`). |
| 4. Support replay does not use `response.video` | **PASS** | `verb == "support"` persists `result.json` (`906-910`). Other verbs use `getattr(response, "video", None)` (`911-914`). Missing output → stderr + `return 1` (`915-920`), no `response.video` AttributeError. |
| 5. `test_replay_support_bundle_reports_result_file` drives real CLI | **PASS** | Test exists at `tests/core/rendering/test_replay.py:408-456`. It calls `renderers_cli_main(["replay", str(bundle_dir), "--pack-root", ...])` (`447-449`) and asserts `verb: support` plus a non-empty result file (`453-456`). Gateway alias is covered separately by `test_dispatch_routes_replay_verb` (`392-405`). |

### Quoted extras (current files)

**Replay parser flags** (`229-252`): `bundle_dir`, `--pack-root` (repeatable), `--acknowledge-drift`. **No `--json`. No `--keep-workdir`.** Module docstring: “Every verb except `replay` accepts `--json`” (`22-23`).

**`_cmd_inspect` JSON keys** (`407-430`): `id`, `kind`, `name`, `version`, `protocol_version`, `command`, `operations`, `required_binaries`, `required_permissions`, `timeout_seconds`, `description`, `capabilities`, `source_pack`, `source_kind`, `manifest_path`, `eligibility`, `eligibility_reason`, `trust_method`. **No**Index and refs `precedence`, `active_ next:revision`, `aliases` I’ll extract tracked/`alias_chain`, `conflicts`, or `overrides paths for `.megaplan`, ``. Frozen insmoke*`, and `. `tests/core/renderingoracle` from/test_cli_contract the worktree git.py:107-126 metadata`.

**`_EXIT._DOMAIN` + interrupt** (`41-42`, `58-61`, `727-744`): `_EXIT_DOMAIN = 1`. `KeyboardInterrupt` → `_handle_interrupt`: if `renderer_error`/`error` present, print and **return 1**; else re-raise. Gateway `render_astrid_error` is 1 if `degraded` else 2 (`astrid/core/contracts/errors.py:247-262`). No `130` in the renderer CLI.

**Help** (`astrid/core/gateway/help.py:92-93`): only  
`python3 -m astrid renderers {{create,list,inspect,validate,smoke,replay}} ...`  
**No top-level `astrid replay` line.** Dispatch alias exists (`dispatch.py:321-325`, `455`).

**Allowlist** (`astrid/core/gateway/__init__.py:149-170`): `SPRINT1_UNBOUND_ALLOWLIST_CONTRACT` has help/version/status/next/attach/projects…/themes/sessions/packs/test/doctor/serve. **`renderers` and `replay` are not listed.**

---

## Leftover frozen Batch 7 acceptance (`.oracle/tasklist.md:149-156`)

| Acceptance item | Status | Evidence |
|---|---|---|
| Unbound from project sessions (`:149`) | **FAIL / leftover** | Routed (`dispatch.py:454-455`) and `renderers … replay` is in help (`help.py:93`), but neither verb is session-unbound (`__init__.py:149-170`). Unlisted verbs require a session (`224-226`, `378-413`). |
| Inspect reports precedence / active revision / aliases / conflicts / overrides (`:150`) | **FAIL / leftover** | Inspect JSON/plain omit those keys (`cli.py:407-459`). Registry already has `priority_index`, `active_revision`, `alias_chain` (`registry.py:102-135`, `316-333`) — unused by `_cmd_inspect`. |
| Each CLI verb has `--json` (`:153`) | **FAIL / leftover** | create/list/inspect/validate/smoke/support have `--json`. Replay parser does not (`229-252`); docstring excludes it (`22-23`). |
| Expected errors 2, bugs 1, interrupt 130 (`:153`) | **FAIL / leftover** | Renderer domain failures return `_EXIT_DOMAIN = 1` (`42`, inspect/smoke/replay). Gateway envelope is 2/1 (`errors.py:262`). Interrupt with a backend error returns **1**, not 130 (`727-744`). CLI contract tests only lock 0 vs non-zero (`test_cli_contract.py:19-20`, `669-673`). |
| `--keep-workdir` exists (`:155`) | **FAIL / leftover** | No `--keep-workdir` / `keep_workdir` under `astrid/`. Smoke/replay always use temp dirs (`cli.py:597-603`, `853`). Only a brief mention remains (`.megaplan/.../pluggable-timeline-renderers.md:104`). |
| Redact `/tmp` and `/var/folders` (`replay.py` `_rewrite_path_string`) | **FAIL / leftover** | `_rewrite_path_string` (`329-351`) rewrites captured-input refs, else redacts only paths under `REPO_ROOT` or `Path.home()` (`349-350`). Other absolute paths, including `/tmp` and `/var/folders`, are returned unchanged (`351`). Placeholder is `"<host-path>"` (`60`). |This verifier session has no shell. Values below are reconstructed from the worktree gitdir at `/Users/peteromalley/Documents/reigh-workspace/Astrid/.git/worktrees/Astrid-oracle` and the shared repo at `/Users/peteromalley/Documents/reigh-workspace/Astrid/.git`. They are not live `git` stdout.

Sources: `worktrees/Astrid-oracle/HEAD` → `ref: refs/heads/oracle-run`; `refs/heads/oracle-run`; `refs/tags/C8-batch7-done`; `logs/refs/heads/oracle-run`; `worktrees/Astrid-oracle/COMMIT_EDITMSG`; `packed-refs` + `refs/tags/`; working-tree file reads.

---

### Reconstructed command results

**`git rev-parse HEAD`**
```
09a9a29c6c523fb0fe6b9d421dbeae4746c545e3
```

**`git rev-parse C8-batch7-done`**
```
09a9a29c6c523fb0fe6b9d421dbeae4746c545e3
```

**`git rev-parse HEAD C8-batch7-done`**
```
09a9a29c6c523fb0fe6b9d421dbeae4746c545e3
09a9a29c6c523fb0fe6b9d421dbeae4746c545e3
```

**`git log -1 --format='%H%n%s%n%b' HEAD`** (body not stored in `COMMIT_EDITMSG`; subject-only last commit message)
```
09a9a29c6c523fb0fe6b9d421dbeae4746c545e3
batch7: verification.md references the C8 tag (SHA-independent)

```

**`git log -1 --format='%H%n%s%n%b' C8-batch7-done`**
Same as HEAD (tag file SHA equals `oracle-run`).

**`git log -12 --oneline`** (first-parent chain from `logs/refs/heads/oracle-run`; `00b2e796` was amended away and is not in the chain). Abbrev width is whatever `git` would choose; full SHAs are listed here for certainty:
```
09a9a29c6c52 batch7: verification.md references the C8 tag (SHA-independent)
79841ad3e3aa batch7: verification.md names the actual HEAD
3fed63ebf4b4 batch7: fix verification.md HEAD SHA (32220c4f)
32220c4f872c batch7: final verification HEAD/tag record
a0eb0eb2f4bc batch7: untrack megaplan local state (harness re-adds via git add -A; keep gitignored)
21c2a18f943b batch7: smoke CLI defaults to temp workspace (no repo-root pollution), replay copies bundle inputs/ tree + support-verb result output, verification HEAD fix, delete smoke artifacts
6d36066a11cd batch7: untrack megaplan local state from index (gitignored harness state)
79ae6faa4177 batch7: fix CLI docstring (replay verb, --json scope), record make ci pre-existing schema-block evidence in verification.md
523863b2c937 batch7: untrack megaplan local state (gitignored harness files)
02df5de782e8 batch7: allow pipeline/user root dirs in hygiene gate, untrack gitignored megaplan state, re-baseline mypy, remove debug artifacts
a12caed288c1 batch7: untrack gitignored megaplan ticket artifact (ci-mirror hygiene gate)
b10de4fcc0b3 batch7-rework: oracle issues 1-8 (replay CLI docs+help+golden path, three-way async/remote/compositing deferral, complete replay bundle with support_report/backend_config/trust/result hashes, full redaction incl request/partial/JSON inputs, support failures captured, localized-payload request digest, real-service freeze tests + audit scope, verification.md + C8 tag)
```

**`git tag -l 'C*'`** (packed + loose tags)
```
C0
C1
C2
C2-batch1-done
C3
C3-batch2-done
C4-batch3-done
C5-batch4-done
C6-batch5-done
C7-batch6-done
C8-batch7-done
```

**`git status --short`**: not executed. Index is binary and unreadable here. Cannot assert cleanliness.

**`git diff --stat HEAD`**: not executed.

**`git ls-files .megaplan`**: not executed. On-disk allowlisted initiative files (13):

- `.megaplan/initiatives/pluggable-timeline-renderers/NORTHSTAR.md`
- `.megaplan/initiatives/pluggable-timeline-renderers/README.md`
- `.megaplan/initiatives/pluggable-timeline-renderers/chain.yaml`
- `.megaplan/initiatives/pluggable-timeline-renderers/briefs/m1-renderer-kernel.md`
- `.megaplan/initiatives/pluggable-timeline-renderers/briefs/m2-renderer-developer-kit.md`
- `.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md`
- `.megaplan/initiatives/timeline-visualization/NORTHSTAR.md`
- `.megaplan/initiatives/timeline-visualization/README.md`
- `.megaplan/initiatives/timeline-visualization/chain.yaml`
- `.megaplan/initiatives/timeline-visualization/briefs/m1-navigation-spine.md`
- `.megaplan/initiatives/timeline-visualization/briefs/m2-source-text-vlm.md`
- `.megaplan/initiatives/timeline-visualization/briefs/timeline-visualization.md`
- `.megaplan/initiatives/timeline-visualization/decisions/timeline-visualization-plan.md`

Also on disk, ignored by `.gitignore` (`.megaplan/*` except initiatives) and by `.git/info/exclude` (`.megaplan/`):

- `.megaplan/tickets/01KYQ1MFJ9WX65C693V4R7EPYT-add-a-unified-astrid-recent-command.md`

**`git ls-files 'smoke*'`**: not executed. Repo-root `smoke-wave.wave.mp4`, `.lock`, and `.provenance.json` are ENOENT. Root listing has no `smoke-*`.

**`ls -la smoke-* 2>&1 | head -20`**: equivalent read of those three paths → does not exist. Expected shell result: `ls: smoke-*: No such file or directory`.

---

### `.oracle/verification.md` first 25 lines (working tree, exact)

```
# Epic Verification — Pluggable Timeline Renderers (M1 + M2 freeze)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
Recorded: 2026-08-13 (Batch 7 rework, final). HEAD: `C8-batch7-done` tag (see `git rev-parse C8-batch7-done`).

## Complete matrix (rework-HEAD evidence)

| Gate | Command | Result |
|---|---|---|
| Core rendering + freeze + replay + audit | `pytest -q tests/core/rendering` | 488 passed (only the documented model-trends env failure in the packs suite) |
| Replay + bundle | `pytest -q tests/core/rendering/test_replay.py test_replay_bundle.py` | 20 passed (support_report, backend_config, trust identity, result_path/result_sha256, localized request_digest, partial/<sha256> files, JSON-input host-path rewriting) |
| Generic-code audit + freeze | `pytest -q tests/core/rendering/test_generic_code_audit.py test_freeze.py` | 17 passed (audit scans profile.py + astrid/__init__.py + astrid/sdk/; freeze adds real-CommandTransport success + missing-binary failure paths) |
| CLI + contract | `pytest -q tests/core/rendering/test_cli.py test_cli_contract.py` | 44 passed |
| Rendering + SDK consolidated | `pytest -q tests/core/rendering tests/packs/rendering tests/test_sdk_rendering.py tests/test_sdk_public_surface.py tests/test_sdk_render_context.py` | 776 passed / 2 skipped / 1 failed (pre-existing model-trends env fixture, `.oracle/baseline.md`) |
| Docs commands | `bash tests/verify_docs_commands.sh` | PASS (re-run at rework HEAD) |
| make check | `make check` | **PASS (re-run at rework HEAD)** — structure, doctor, ruff, mypy, cycles, remotion-typecheck, renderer-parity all green |
| Remotion typecheck | `cd remotion && npm run typecheck` | PASS (part of `make check`) |
| Wheel smoke | `bash scripts/smoke_wheel_install.sh` | PASS (re-run earlier at rework commit: scaffold golden path in wheel venv incl. installable `wave.wave`) |
| make ci | `make ci` | **FAILS at ci-mirror (blocking lane) — 10 failures, ALL pre-existing** `tests/test_schema_contract.py` timeline-schema defects (`clips: []` missing required duration/resolution etc.). Verified the epic touched ZERO timeline-schema files (`git diff C5-batch4-done..HEAD -- astrid/core/timeline/` empty); identical failures reproduced at C5-batch4-done. The editable + wheel-install gates within `make ci` pass; only the blocking lane's pre-existing schema contract fails. **Not an epic regression.**
| Full suite (CI mirror) | `pytest -q -m "not integration and not opt_in"` | 7778 passed / 62 failed — all pre-existing at C5-batch4-done in unrelated areas (schema_contract, supabase, reigh, project_cli, timeline, packs_validate); zero epic-caused regressions after the 5 test-contract fixes |
| Parity (real Remotion/FFmpeg) | `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py` | 18 passed. NOTE: parity tests treat a chromium denial (`MachPortRendezvousServer` / headless chromium refusal) as success-with-skip; only non-skipped cases prove real media output |
| Hygiene | `scripts/reshape/check_repo_hygiene.py` | PASS (allowlist extended for `.megaplan`/`.oracle`/`tools`/`fal-voice-upscale` pipeline+user dirs; gitignored megaplan state untracked) |
| Tags | `git tag C8-batch7-done` | applied at final rework HEAD (`git rev-parse C8-batch7-done`). Prior tags C0..C7 are historical batch markers |

## Freeze assertions
```

### Grep of working-tree `.oracle/verification.md`

| Pattern | Matches |
|---|---|
| `[0-9a-f]{7,}` | none |
| `HEAD:` | line 4 only |
| `21c2a18f` | none |
| `a0eb0eb2` | none |
| `32220c4f` | none |
| `79ae6faa` | none |
| `C8-batch7-done` | lines 4 and 23 |

Line 4: `Recorded: 2026-08-13 (Batch 7 rework, final). HEAD: \`C8-batch7-done\` tag (see \`git rev-parse C8-batch7-done\`).`

Line 23: `| Tags | \`git tag C8-batch7-done\` | applied at final rework HEAD (\`git rev-parse C8-batch7-done\`). Prior tags C0..C7 are historical batch markers |`

### Is `verification.md` committed at HEAD?

- `git log -1 --oneline -- .oracle/verification.md`: not executed. Last commit that moved `oracle-run` is `09a9a29c…` subject `batch7: verification.md references the C8 tag (SHA-independent)`.
- `git show HEAD:.oracle/verification.md | head -25`: not executed (commit object is zlib-compressed).
- `git diff HEAD -- .oracle/verification.md`: not executed. Working-tree recorded-HEAD line is the tag form above.

### Uncommitted `.oracle/checkins/`

Index not readable. Cannot list uncommitted vs tracked. Files present on disk (40): `batch-1.md`, `batch-1-r1.md` … `batch-1-r13.md`, `batch-2.md`, `batch-2-r1.md` … `batch-2-r6.md`, `batch-3.md`, `batch-3-r1.md` … `batch-3-r4.md`, `batch-4.md`, `batch-4-r1.md` … `batch-4-r3.md`, `batch-5.md`, `batch-6.md`, `batch-6-r1.md` … `batch-6-r3.md`, `batch-7.md`, `batch-7-r1.md` … `batch-7-r4.md`.

### Commits after the tag on this branch?

No. `refs/heads/oracle-run` == `refs/tags/C8-batch7-done` == `09a9a29c6c523fb0fe6b9d421dbeae4746c545e3`. No tag reflog file exists, so a prior tag target cannot be shown from disk.

---

### Fact table

| Item | Value |
|---|---|
| HEAD SHA (full) | `09a9a29c6c523fb0fe6b9d421dbeae4746c545e3` |
| C8 SHA (full) | `09a9a29c6c523fb0fe6b9d421dbeae4746c545e3` |
| Equal? | yes |
| verification.md in HEAD: first recorded HEAD line | not recovered from the commit object. Working-tree line 4: `Recorded: 2026-08-13 (Batch 7 rework, final). HEAD: \`C8-batch7-done\` tag (see \`git rev-parse C8-batch7-done\`).` |
| Does verification.md contain any commit SHA? | no (`[0-9a-f]{7,}` empty) |
| Working tree dirty? | unknown (no `git status`). Ignored on-disk: `.megaplan/tickets/01KYQ1MFJ9WX65C693V4R7EPYT-add-a-unified-astrid-recent-command.md`. Checkins index state unknown. |
| smoke-* at repo root? | no |
| .megaplan tracked files count | `git ls-files` not run; 13 initiative files on disk; tickets file ignored |
| Last 8 commit subjects | 1) batch7: verification.md references the C8 tag (SHA-independent) 2) batch7: verification.md names the actual HEAD 3) batch7: fix verification.md HEAD SHA (32220c4f) 4) batch7: final verification HEAD/tag record 5) batch7: untrack megaplan local state (harness re-adds via git add -A; keep gitignored) 6) batch7: smoke CLI defaults to temp workspace (no repo-root pollution), replay copies bundle inputs/ tree + support-verb result output, verification HEAD fix, delete smoke artifacts 7) batch7: untrack megaplan local state from index (gitignored harness state) 8) batch7: fix CLI docstring (replay verb, --json scope), record make ci pre-existing schema-block evidence in verification.md |**ISSUES** — not `PASS`. Do not start Phase 6.

The r3 SHA problem is closed. The five r2 code fixes still hold. The leftover frozen Batch 7 contract from r2/r3 was not touched. That host summary (“the only r3 FAIL was the SHA”) is wrong: r3 also left the Batch 7 gate open.

## Identity (r3 8a — closed)

| Ref | Value |
|---|---|
| `HEAD` / `C8-batch7-done` | `09a9a29c6c523fb0fe6b9d421dbeae4746c545e3` |
| Equal? | **yes** (`git rev-parse HEAD C8-batch7-done`) |
| `.oracle/verification.md` | names the `C8-batch7-done` tag, no commit SHA |

Subject: `batch7: verification.md references the C8 tag (SHA-independent)`. That closes the SHA-chase.

Working tree: `?? .megaplan/` `?? .oracle/checkins/batch-7-r3.md` `?? .oracle/checkins/batch-7-r4.md`. No `smoke-*` at repo root. `git ls-files .megaplan` → 0.

## r2 code fixes — still PASS

Independently re-checked at this HEAD.

| Claim | Verdict | Evidence |
|---|---|---|
| Smoke default is a temp dir | **PASS** | `cli.py:591–598` uses `tempfile.mkdtemp`, not `Path.cwd()`. `--out` help still says `./smoke-<id>.mp4`. `mkdtemp` is never cleaned up. |
| Committed smoke artifacts gone | **PASS** | `ls smoke-*` → ENOENT. Not in the index. |
| Replay copies the whole bundle | **PASS** | `cli.py:858–862` `copytree`s `bundle_dir` (so `inputs/` comes along). |
| Support replay does not use `response.video` | **PASS** | `cli.py:906–920` branches on `verb`. `test_replay_support_bundle_reports_result_file` drives the real CLI. |
| Hygiene | **PASS** | `scripts/reshape/check_repo_hygiene.py` exit 0. |

Re-ran here: `tests/core/rendering` → **489 collected, exit 0**. CLI + replay + contract → **54 passed**. Hygiene → **PASS**. Did not re-run `make check` / `make ci` / wheel smoke.

`verification.md` still says 488 / 44 / 776. The 44 row matches `test_cli.py` + `test_cli_contract.py` (no replay). The 488 row is stale by the support-replay test. Record nit, not a new SHA FAIL.

## Still the frozen Batch 7 gate (r2 issue 4 / r3 leftover)

This delta did not touch these. They were blocking in r2 and r3. They still are.

1. **CLI is session-gated, not unbound.** Frozen: `tasklist.md:149`, `plan.md:391`. `SPRINT1_UNBOUND_ALLOWLIST_CONTRACT` has no `renderers` / `replay` (`gateway/__init__.py:149–170`). Allowlist probe: `["renderers","list"]` and `["replay"]` are `False`. Live:

   - `python3 -m astrid renderers list` → exit 2, `no session bound`
   - `python3 -m astrid renderers create wave /tmp/…` → exit 2, same
   - `python3 -m astrid replay` → exit 2, same

   CLI tests call `renderers_cli_main` and never hit the gateway, so they stay green.

2. **`inspect` still omits** precedence, active revision, aliases, conflicts, overrides (`cli.py:407–430`). Frozen: `tasklist.md:150`. Registry already has `priority_index` / `active_revision` / `alias_chain`. The contract test locks the reduced key set.

3. **`--keep-workdir` does not exist.** Frozen: `tasklist.md:155`, `plan.md:413`. Smoke/replay always use temp dirs. Smoke default is a leaked `mkdtemp`.

Not re-failed (task-level overrides a conflicting batch line):

- Exit 2 / 1 / 130 taxonomy — T7.2 forbids an independent exit-code layer; `test_cli_contract.py:19–20` locks 0 vs non-zero only.
- `/tmp` redaction — batch text requires credentials, auth headers, and signed URL queries, not `/tmp`.
- Replay `--json` — documented exception (`cli.py:22–23`); T7.2 deferred it. Still absent; not the same class as (1)–(3).

## How to close (do not make another verification.md commit)

Fix the three leftover items, **or** submit an oracle-reviewed plan revision that drops them from `tasklist.md`. Then prove:

```
python3 -m astrid renderers list          # exit 0 with no session
python3 -m pytest -q tests/core/rendering/test_cli.py tests/core/rendering/test_cli_contract.py
```

Do not start Phase 6 until this is a clean `PASS`.
