I'll re-review Batch 7 against the eight host-fixed issues and the incremental `7b7bf153..b10de4fc` diff. First I'm loading the megado review process and the prior verdict so the check stays evidence-based.Next I’ll pull the prior Batch 7 verdict, the tasklist acceptance criteria, and the incremental rework diff so each claimed fix can be checked against the code.The first verdict had more blockers than the eight claimed fixes. I’ll inspect the rework diff and independently check both those eight items and the leftover original issues.The rework is scoped to eight issues; I’ll verify those in code and tests, and also re-check leftover original blockers against the frozen acceptance list.I'll read the replay capture/CLI code and the relatedI'll verify the claimed Batch 7 host tests first, then verify each fixes against the listed claimed fix against the actual implementation files and leftover.I’ll issues, starting with the contract inspect the CLI/docs and targeted greps. replay path, session gating, inspect fields, and the audit suite while the isolated reviews run.Next I’ll inspect the service capture path and how `_cmd_replay` actually stages bundle files.Next I’ll inspect the CLI allowlist, inspect/smoke/exit handling, and leftover artifacts against the frozen contract.I have the leftover artifact list; now I’ll read inspect/smoke/exit implementation and the frozen T7.6 acceptance notes.Replay still looks like it skips `inputs/`. I’m checking dispatch, support capture, and a few leftover contract points next.## Claimed 1/2/7/8

**1. Replay CLI undocumented — PASS**

Replay is now in the listed docs/help surfaces:

- Verb list + top-level alias: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/packs/aliases-vs-forks-vs-overrides.md:282-292`
- Gateway help: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/gateway/help.py:92-93` (`renderers {create,list,inspect,validate,smoke,replay}`)
- Golden-path recaps: `docs/guides/debugging.md:169`, `astrid/packs/rendering/skill/SKILL.md:253`
- Worked example + golden path: `docs/contracts/render-backend-v1.md:626-667`, `:880-881`
- SDK: `docs/reference/sdk.md:375-390`
- Top-level route exists: `astrid/core/gateway/dispatch.py:321-326`, `:455`

Nits (do not overturn the docs claim): `help.py` never prints `python3 -m astrid replay`; `astrid/core/rendering/cli.py:7-21` still documents create/list/inspect/validate/smoke/support only and still says “Every verb accepts `--json`”, while `replay_parser` has no `--json` (`cli.py:225-248`).

**2. Async/remote/compositing not all deferred — PASS**

Explicit three-way deferral is in all claimed places:

- V1 scope: `docs/contracts/render-backend-v1.md:184-190`
- Decision 14: `docs/contracts/render-backend-v1.md:1053-1058`
- Replay worked-example closer: `:669-670`
- `docs/guides/debugging.md:121-125`
- `astrid/packs/rendering/skill/SKILL.md:256-258`
- `docs/reference/sdk.md:392-394`

**7. `test_freeze` FakeTransport-only + audit scope — PASS (against the rework brief)**

- Real FFmpeg via real `CommandTransport`: `tests/core/rendering/test_freeze.py:195-224`
- Real missing-binary / no sidecar / temps cleaned + replay bundle: `:260-291`
- Audit now scans `profile.py`, `astrid/__init__.py`, and `astrid/sdk/*.py`: `tests/core/rendering/test_generic_code_audit.py:72-92`; `profile.py:113` allowlisted as a remotion compat shim (`:69`)

Caveat: the six built-in-path params still use `FakeTransport` (`test_freeze.py:100-118`). That is narrower than the original freeze complaint, but it matches the rework ask (“at least one real success + one real failure”).

**8. `verification.md` + tags — FAIL**

- Some numbers were rewritten (`488`, `20`, `17`, `748/2/34`, docs PASS): `.oracle/verification.md:10-14`
- Chromium-denial skip is noted: `:19`
- `make ci` is *mentioned*, but as **not re-run**: `:17`
- HEAD is recorded as `` `7b7bf153` + rework `` (`verification.md:4`), not actual branch HEAD `b10de4fc` (`/Users/peteromalley/Documents/reigh-workspace/Astrid/.git/refs/heads/oracle-run`)
- Tag `C8-batch7-done` exists, but it points at **pre-rework** `7b7bf153d80791206ce8daa6c7cf66665deb94ab`, not rework HEAD `b10de4fcc0b3b82a5a2ea7dc13809f71d63185a1` (`Astrid/.git/refs/tags/C8-batch7-done`)
- Frozen T7.6 still wants the complete matrix (`tasklist.md:167`, `briefs/batch-7-t7.6.md:28-36`). The record still marks `make check`, wheel smoke, `make ci`, full suite, and parity as **not re-run** (`verification.md:15-19`). `cd remotion && npm run typecheck` is absent from the table.

---

## Leftover CLI/docs/freeze issues

All six leftovers are **still present**.

**Session-gated CLI — still present (docs now encode the inversion)**

Frozen: verbs “remain unbound from project sessions” (`tasklist.md:149`, `plan.md:391`).

- `SPRINT1_UNBOUND_ALLOWLIST_CONTRACT` still has no `renderers` / `replay` (`astrid/core/gateway/__init__.py:149-170`)
- Gate is exact-prefix only (`__init__.py:410-413`)
- Rework docs tell authors to bind a session first: `render-backend-v1.md:855-857` (golden path), `:658-659` (replay worked example: “bind a session first, like the other renderer-authoring verbs”)

**`inspect` omits required discovery fields — still present**

Frozen (`tasklist.md:150`, `plan.md:399`): source kind, **precedence**, **active revision**, trust eligibility/reason, permissions, capabilities, **aliases, conflicts, overrides**.

`_cmd_inspect` (`cli.py:403-456`) emits manifest + `source_pack` / `source_kind` / eligibility / `trust_method` only. No precedence, active revision, aliases, conflicts, or overrides. `_cmd_list` (`:339-347`) is ids-only.

**`smoke` default output is cwd, not temp — still present**

Frozen: “temporary output” (`tasklist.md:151`, `plan.md:401`).

```587:591:astrid/core/rendering/cli.py
    out_path = (
        Path(args.out)
        if args.out is not None
        else Path.cwd() / f"smoke-{args.renderer_id}.mp4"
    )
```

Workspace for the *timeline* is temp (`:596`); the published video is not.

**Debug artifacts at repo root — still present**

On disk:

- `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/smoke-## Claimed 3/4/5/6

### 3wave..wave Replay. bundlemp incomplete4 —`
- `smoke- **PASS**

`write_replay_bundle` writeswave.wave.mp4 the extra fields.lock`
- `smoke- into `bundle.json`:wave.wave.mp4

```134:166:/.provenance.json` (`outputUsers/peteromalley/` is thisDocuments/reigh-workspace work/Astrid-oracle/astrid/core/renderingtree path at line/replay.py
    payload 59)

`*.mp = {
        "bundle_4` is gitignored (schema_version": BUNDLE`.gitignore:54`); `._SCHEMA_VERSION,
        ...
        "result_lock` / `.provenance.jsonsha256": (
` are not. T            partial_descriptor["sha7.6 freeze: “256"] if partial_descriptorgit is not None else None
 tree is clean of debug artifacts        ),
        "result” (`briefs_path": (
            partial_descriptor["path"] if/batch-7-t partial_descriptor is not None7.6.md:37 else None
        ),
-38`).

**Exit        "backend_config":/interrupt contract _redact_metadata(... — still present**

Frozen),
        "support_ (`report": (...tasklist.md:152`,),
        "metadata": `plan.md:403`): {...},
 expected 2, degraded    }
```

Partial files 1, cleanup land under then re-raise for `partial/<sha256>`:

```407:411 130; “:/Users/peteromalleyno independent exit-code layer/Documents/reigh-”. Contract itselfworkspace/Astrid-oracle says SIGINT is/astrid/core/ re-raised for exitrendering/replay.py
    130 (` digest = hashlib.sha256(text.encode("utf-render-backend-v18")).hexdigest()
.md:501-503`).    partial_dir = dest

- Invented `__path / PARTIAL_EXIT_DOMAIN = 1DIRNAME
    ...
` (`cli.py:37    return {"sha-38`),256": digest, "path used for unknown": f"{PARTIAL_DIRNAME-}/{digest}"}
id / ineligible```

Capture fills them from the live / validate / smoke / invocation:

```193 support / interrupt4:198
0:/Users- `_handle/peteromalley/Documents_interrupt` returns `_EXIT/reigh-workspace/_DOMAIN` whenAstrid-oracle/astrid/core/rendering/ a `rendererservice.py
            "source_error` is attached (`_pack": invocation.candidatecli.py:720-737.pack_id,
           `) — "source_kind": invocation swallowed.candidate.source_kind,
 as 1, not             "eligibility": eligibility.to130
- Bare `Keyboard_dict(),
            "Interrupt` is retrust_method": eligibility.-raised (`:728trust_method,
        ...-729`); gateway `
            support_report=main` doessupport_report.to_dict() if support_report is not catch `BaseException` (`gateway/ not None else None,
           __init__.py:178 backend_config=dict(-189`)

**`payload_dict.get("backendverification.md` matrix not re_config") or {}),
-run — still present**            result_path=str

See claim(invocation.result_path), 8. Frozen T7
```

`source.6 is not satisfied_pack` / `source by annot_kind` / `eligibilityating “not` / `trust_method re-run in` live under ` rework.”

**metadata`, not as topOther first-review leftovers the-level `bundle.json` keys. Tests host also assert that did not claim (still broken layout (`test_replay)**

- `--keep-workdir` does_bundle.py`  not exist;336 replay–354,/smoke 323–329 always `TemporaryDirectory` (`).

###cli.py:596 4. Redaction gaps`, `:846`; — **FAIL** (incomplete frozen `task vs the claimlist.md:156`)
)

What- Replay has actually happens no `--json` (`cli:

| Artifact |.py:225-248`, Host `:907-path rewrite (`-915`; frozen_rewrite_host_paths `tasklist.md:152`) | Secret`)
- Replay still/URL redaction (` copies only **_redact_metadata`files** in / `_redact_log the bundle root, not ``) |
|---|---|---|inputs/` (`cli.py:
| Copied JSON inputs | Yes848-850`)

---

## New | defects from the rework

 No1. **` |
| `request.json`C8-batch7-done | No` ( is ononly `timeline the wrong commit.** Tag_path` / `assets = `7b7bf153_registry_path` rem`; rework HEADapped) | Yes |
 = `b10de4| Partial result | No | Yesfc`. ` |

-verification.md:4, JSON20` claims the tag is inputs: `_copy “_inputs` →applied at rework HEAD.” `_localize_json_input
2. **Session` → `_rewrite inversion_host_paths`. Capt was writtenured inputs become ` into the goldeninputs/<sha256>`; path / uncaptured abs paths ** replay example**under `REPO_ROOT (`render-backend-v` or `Path.home1.md:855-859()`** become `<host-`, `:658-660path>`; other strings are untouched (``) instead of unbinding the verbsreplay.py` 279–351)..
3. **Module contract Tested in `test_ drift aftercopied_input the docs pass_redacts_absolute:** `cli.py:7_host_paths_not-21` still omits_an_input` ( `replay` and falsely592–639 claims every verb has `--json) and ``.
4. **Helptest_localized_inputs_ documentscopied_hashed_without_ the `host_paths` (565renderers` subverb–589 but not the advertised).
- `request.json top-level alias** (``: `_localizehelp.py:93` vs_payload` only re `dispatch.py:321-writes the two wire326`).
5. ** path keysT7.6 ` (`replay.py` 414npm run type–427check` never, `_ appears** in `.PAYLOAD_PATH_ROLESoracle/verification.md`.
` 53–566. **Repo-root smoke artifacts), then secret-redacts. No remain after deep host a-path walk.
- Partial rework that was results: `_write_partial supposed to freeze_result` only secret a-redacts (`replay clean tree**; provenance still names this.py` 395–403). A host path in a partial JSON would worktree (`smoke-wave. bewave.mp4.provenance stored as.json:59`).-is. Test `test_partial_result_redacted_and_written_as_hashed_file` (642–667) only checks tokens/URLs.

Residual host-path leak: `_rewrite_path_string` leaves abs paths that are not captured and not under repo/home unchanged (`replay.py` 349–351: “any other absolute path is left as-is”). `/tmp`, `/var/folders`, etc. still leak.

### 5. Support failures excluded — **PASS**

```121:124:/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py
#: ``support`` is included because a support probe can itself fail with a
#: backend bug and must be replayable like any other invocation.
_REPLAY_VERBS = frozenset({"render", "finalize", "plan", "support"})
```

`_run_command` records `_last_invocation` before `transport.run` (1838–1845), so a throwing support probe is captured. `test_support_failure_captures_replay_bundle` (669–713) asserts `metadata["verb"] == "support"` and `support_report is None`.

### 6. Request digest pinned wrong object — **PASS** (write path + tests)

```119:128:/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/replay.py
    localized_request = _localize_payload(bundle.payload, input_descriptors)
    if localized_request is not None:
        localized_request = _redact_metadata(...)
        write_json_atomic(dest_path / REQUEST_FILENAME, localized_request)
        request_digest = compute_request_digest(localized_request)
    else:
        request_digest = bundle.request_digest
```

`test_failure_captures_complete_bundle` (296–303) asserts equality with `compute_request_digest(localized)` and inequality vs `request.to_dict()`.

Hand-built bundles still work: `_make_bundle` (`test_replay.py` 59–99) already puts bundle-relative `timeline_path` in `payload`, so re-localization is a no-op and the written digest still matches `request.json`. Fresh-replay / tamper tests still pin that on-disk digest.

Caveat (not a test failure): `_build_replay_bundle` still stores the **absolute-path** digest on the in-memory object (`service.py` 1970). `_capture_failure_bundle` / `_capture_success_bundle` name the dest dir from that stale field (`1887–1891`, `1913–2099`) while `bundle.json` pins the localized digest.

---

## Leftover replay issues

All four are **still present**.

**Replay CLI never copies `inputs/`.** Only regular files in the bundle root are staged:

```846:851:/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/cli.py
    with _TemporaryDirectory(...) as tmp_text:
        workspace = Path(tmp_text)
        for source in bundle_dir.iterdir():
            if source.is_file():
                _shutil.copy2(source, workspace / source.name)
        _shutil.copy2(request_path, workspace / "request.json")
```

`inputs/` and `partial/` are directories, so they are skipped. Tests stay green because `raw_command` `_render` never reads `timeline_path` — only `output_name` / `window` / `profile` (`backend.py` 504–528).

**`--keep-workdir` still missing.** Replay parser is only `bundle_dir`, `--pack-root`, `--acknowledge-drift` (`cli.py` 225–248). Workdir is an unconditional `TemporaryDirectory`.

**Replay has no `--json` shape.** Same parser: no `--json`. Handler always prints text (`907–915`). The module docstring still says every verb accepts `--json` (`cli.py` 19–20); that is now false for `replay`.

**Replay CLI still does not use localized inputs when re-running.** It points the transport at the copied `request.json` (`877–879`) whose `timeline_path` is `inputs/<sha256>`, but never materializes `inputs/` in the temp workspace and never remaps those paths. Drift checks read inputs from `bundle_dir` (`798–806`); the re-run does not.

---

## New defects introduced by the rework

1. **Support bundles are now captured but cannot be replayed.** `_cmd_replay` always does `response.video.path` (`893–901`). `CommandTransport.run("support", ...)` returns a `SupportReport`. Replaying a `verb: support` bundle will `AttributeError` after a successful support probe (or fail earlier if the original crash reproduces). Capture test does not exercise the CLI.

2. **Bundle directory name vs pinned digest.** Dest uses `bundle.request_digest` from the pre-localization request (`service.py` 1970, 1888–1890, 2099). Operators matching a folder suffix to `bundle.json["request_digest"]` will miss.

3. **Docs/comments overclaim the leftover CLI behavior.** `_cmd_replay` docstring says it re-runs “from the bundle-local inputs” (`cli.py` 750–752); the V1 contract says the same (`docs/contracts/render-backend-v1.md` 627–630). Implementation still only copies root files.The freeze tag looks like it landed on the pre-rework commit. I’ll confirm that, run the claimed suites, and finish the leftover contract checks.I independently checked the eight claimed fixes against `7b7bf153..b10de4fc` and the frozen Batch 7 acceptance list. Targeted suites match the host numbers: 81 passed across replay, bundle, freeze, audit, CLI, and contract.

Docs items 1 and 2, bundle field capture, support-failure capture, localized digest write-path, and the added freeze/audit coverage are real. The batch still does not meet the freeze.

## ISSUES

### 1. Replay still cannot replay a captured bundle

The digest write-path is fixed (`write_replay_bundle` now pins `compute_request_digest(localized)`). The run path is not.

`_cmd_replay` only copies regular files in the bundle root:

```846:851:astrid/core/rendering/cli.py
        for source in bundle_dir.iterdir():
            if source.is_file():
                _shutil.copy2(source, workspace / source.name)
        _shutil.copy2(request_path, workspace / "request.json")
```

`inputs/` and `partial/` are directories, so they are skipped. The localized `request.json` still says `timeline_path: "inputs/<sha256>"`. A service-captured FFmpeg/Remotion bundle now passes the digest check and then fails because the hashed inputs are not in the temp workspace.

`test_replay.py` stays green because `raw_command` never opens `timeline_path` (`backend.py:504-528` only uses `output_name` / `window` / `profile`).

Adding `"support"` to `_REPLAY_VERBS` made this worse: `_cmd_replay` always does `response.video.path` (`cli.py:893-901`). A successful support replay returns a `SupportReport` and will `AttributeError`. Capture is tested; CLI replay of `verb: support` is not.

Destination folders are still named from the *absolute-path* digest (`service.py:1970`, `1888-1890`, `2099`) while `bundle.json` pins the localized digest.

### 2. Redaction is still incomplete

Copied JSON inputs rewrite captured-input refs and paths under `REPO_ROOT` / `Path.home()`. Everything else is left as-is:

```349:351:astrid/core/rendering/replay.py
    if _under_root(resolved, REPO_ROOT) or _under_root(resolved, Path.home()):
        return _HOST_PATH_PLACEHOLDER
    return value
```

`/tmp` and `/var/folders` (invocation staging, pytest tmp) leak. `request.json` only remaps `timeline_path` / `assets_registry_path` plus secret redaction — no host-path walk. Partial results get secret/URL redaction only.

### 3. `C8-batch7-done` is on the wrong commit

| Ref | SHA | Subject |
|---|---|---|
| HEAD | `b10de4fc` | batch7-rework |
| `C8-batch7-done` | `7b7bf153` | batch7 (pre-rework) |

`.oracle/verification.md:4,20` says the tag is on rework HEAD. It is not. `make check`, `make ci`, wheel smoke, full suite, parity, and Remotion typecheck are recorded as **not re-run**. Frozen T7.6 requires the matrix, not an annotation that it was skipped.

### 4. First-review frozen-acceptance blockers are still open

The rework did not touch these, and one of them was written into the docs as intended behavior:

- **Session-gated, not unbound.** `SPRINT1_UNBOUND_ALLOWLIST_CONTRACT` still has no `renderers` / `replay` (`gateway/__init__.py:149-170`). The golden path now says “Bind a session first — renderer-authoring verbs are session-gated” (`render-backend-v1.md:855-857`, `:658-659`). Frozen acceptance: remain unbound.
- **`inspect` still omits** precedence, active revision, aliases, conflicts, overrides (`cli.py:403-456`). Frozen list is explicit.
- **`smoke` default output is cwd** (`cli.py:587-591`), not a temporary output. `smoke-wave.wave.mp4.lock` and `.provenance.json` are still tracked; the rework mutated the sidecar. `*.mp4` is gitignored, so the video sits untracked at the repo root.
- **`--keep-workdir` does not exist.** Replay/smoke always use `TemporaryDirectory`.
- **`replay` has no `--json` shape** (`cli.py:225-248`, `:907-915`) even though the module docstring says every verb does (`cli.py:19-20`).
- **Exit/interrupt taxonomy is unchanged:** invented `_EXIT_DOMAIN = 1`; interrupt with an attached `renderer_error` is swallowed as 1, not cleanup-then-130.

### Claimed items that did land

Replay is documented (help, aliases doc, debugging/SKILL golden paths, contract worked example, SDK). The three-way V1 deferral is explicit. `bundle.json` now carries `support_report`, `backend_config`, source/trust identity, and `partial/<sha256>` descriptors. Support failures are captured. The write-path digest is the localized request. Freeze gained a real-FFmpeg success and a real missing-binary failure; the audit now scans `profile.py`, `astrid/__init__.py`, and `astrid/sdk/` (`profile.py:113` is allowlisted, not removed).

Do not start Phase 6. Fix 1–3 for sure; 4 is still the frozen Batch 7 gate.
