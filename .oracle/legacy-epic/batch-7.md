I'll treat this as a read-only Batch 7 checkpoint: inspect the incremental commit against the acceptance list, then verify CLI, replay, docs, and freeze claims from the code and tests.I have the commit delta. Next I’ll pull Batch 7 acceptance from the tasklist and fan out a read-only review of CLI, replay, docs, and freeze.I have the Batch 7 acceptance criteria. Next I’ll read that section in full and dispatch isolated reviewers against the CLI, replay, docs, and freeze diffs.Acceptance is clear. I’ll fan the review across CLI, replay, docs, and freeze, and independently check the implementations plus leftover artifacts.I'll inspect the Batch 7 renderer CLI and frozen error-contract code against the T7.1/T7I'll inspect.2 acceptance criteria. the Batch 7 replay-bundle and pinned-replay implementation against the frozen T7.3/I'll inspect BatchT7.4 acceptance criteria. 7 docs, freeze/audit tests, and verification evidence against the frozen acceptance criteria.Help omits `replay`, and smoke artifacts landed in the commit. I’ll inspect those plus the CLI/replay implementations while the reviewers work.Next I’ll cross-check docs coverage, generic-core backend names, freeze assertions, and git/tag evidence.Service hooks, CLI replay, and keepNext I’ll read dispatch, help, and the CLI tests to check routing, JSON shapes, and whether the contracts are actually asserted.-workdir next — those are the likely failure points.The inspect field list and replay/help gaps look like likely blockers; I’ll pull the frozen tasklist and how list/inspect/validate actually work.Docs look broad; next I’ll verify CLI accuracy, unscanned generic core, freeze gaps, and recorded CI/tag evidence.The digest mismatch and missing `inputs/` copy reproduce. I’ll run the claimed acceptance tests and pull the remaining inspect/docs gaps before writing the verdict.Checking request digest vs localized `request.json` and whether production callers emit a replay command.## T7.5 — ISSUES

**1. Replay CLI never documented (blocking).** Frozen acceptance requires author docs to cover replay and the T7.5 brief requires the `replay` verb. No doc shows `python3 -m astrid renderers replay` or `python3 -m astrid replay`. Bundles are described only as prose (`docs/contracts/render-backend-v1.md:598–616`, `873–878`; `docs/guides/debugging.md:88–101`). `docs/packs/aliases-vs-forks-vs-overrides.md:282–283` lists `create|list|inspect|validate|smoke` and omits `replay`. Gateway help matches that hole (`astrid/core/gateway/help.py:93`). Golden-path recaps (`debugging.md:137–145`, `SKILL.md:244–252`) stop at smoke.

**2. Async/remote/compositing not all deferred (blocking).** Frozen acceptance requires explicit deferral of async jobs, remote infrastructure, and layer compositing. Only locked decision 14 says “Asynchronous remote jobs are explicitly deferred beyond V1” (`render-backend-v1.md:999`). No “remote infrastructure” or “layer compositing” deferral in contracts/guides.

**3. `verify_docs_commands.sh` does not check these docs (nit).** Script extracts only `README.md` ```text``` and `docs/templates/**/STAGE.md` (`tests/verify_docs_commands.sh:22–32`). Passing it does not validate golden-path commands in `render-backend-v1.md` / skills / guides.

Covered elsewhere: golden path commands (`render-backend-v1.md:800–825##`), raw JSON + T7.3 — ISS non-Python argv (`UES

**Silent147–155-`),substitution SDK vs (`docs T7.4:** Capture does/reference/sdk.md: not substitute backends309–. Replay refuses414`), trust/permissions/ a changedselection/config/assets/ **manifestoutput/audio/attachments/** digest unless `--acknowledgediagnostics/legacy-drift` (`cli.py selectors:793 (`renderChecking how inspect could–823-backend-v1.md report aliases:16–86`). Ack/conflicts and whether smoke then runs default`, `344 the **current** registry–359`, `501 output is documented candidate (– as517 cwdnot silent). **`, `784.Request**-digest mismatch is tam–871`). `pering and cannot be acked (`astrcli.py:834–844id/packs/rendering/`).

**Bundskill/STAGE.md`les without does not exist; `exec `replay_root`:**utors/render/STAGE.md `:147–159render_request`` was updated instead always tries capture (`service.py:386.

---–

387## T7.6 —`). ISS DefaultUES dest

 is** output1 sibling `.{. `verificationname}.replay`, else `..md` is not a reastrid-replays`-run matrix (blocking (`service.py:2059–2075).**  
`). Production- Full- `RenderService()` / smoke neversuite line is ` pass `replay_root` (`cli.py7778 passed / 62:592–595 failed` (`verification`). Hooks.md:18`) — fire for whatever byte-identical to Batch last `_ 5 `.run_command` verb was in `{render,finalize,oracle/m1-gateplan}` (`service.py:.md:18`. Batch 121–122,1867 added CLI/replay/7freeze/audit tests; that–186 count cannot still9`). Support/ beregistry  failures skip7778 if capture. ** reNo- planrun/ atfinalize tests** (`test_replay_ `7b7bf153bundle.py` only fails`.  
- `make ci `render`).

**Blocking` (`**

Makefile:54`:1. **Bundle is `check editable wheel not the frozen record ci.**- `mirrorwrite`) is not_replay_bundle` writes recorded. “ `bundle.json`Full suite (CI mirror)” + `request.json` + is a filtered pytest, `inputs/<sha>` only (` not `make ci`.  
replay.py:94–112- Remotion: parity “`). Missing: support report, source18 passed” (`-pack/trust identityverification.md:15, isolated`) backend config, result with no chromium hashes, exact replay command with **absolute-denial vs real-render split. `test_renderer** request/result paths._parity.py:328 Stored `argv` is–330` / relative (`replay.py:163 `:431––179`);432 `` treat `Machresult.json` is never writtenPortRendezvousServer` as. F success andails Batch return without 7 + ` adocs video/contracts. No/render-backend-v1.md: explicit skip evidence.  
- “tags C0..C7”## T (`verification598.md–:6094`)`.

2. **Redaction is logs7.1 — ISS/metadata only.** `requestUES

** is false: packed.json` and `partial-refs have1. Not_result` are un `C0 session-unredacted (`replay.py:`/`C1`/`90bound (blocking)**  
C2-batch1-Frozen–92,105done`; loose tags end: verbs`). Secrets in at ` `backendC_config7`,-batch “6-done` (`Astr request metadata, or aremain unbound from project sessions.”id/.git/refs/ partial result survive  
`SPRINT1.

3. **Host paths_UNBOUND_ALLOWLISTtags/`). remain in_CONTRACT` has no copied inputs No Batch 7 freeze tag `("renderers",)`.** Theme.

**2. `test (`astr is copied by_freeze.py` does not lock the freezeid/core/gateway/__init__.py:149 digest (`service (blocking).**  
- All.py:1987–1989`) but timeline-170 six`). `_ “verbbuilt_is_unbound_ JSON is not rewritten (`-inallowlisted” cases` onlyreplay.py:115 use matches ` thatFakeTransport` (`test_freeze.py:88– table–144 (``). `inputs/<:410timeline--sha102413>``, still ` contains the hosttest_service.py theme: path251. Test`). `python–358 only checks3 `bundle -.jsonm` astrid render`). `optimized` / `/`requesters …` hits theaudio-reactive` only set.json` (`test_replay session gate (`:224 unused `backend_config`_bundle.py:517 (`-61302––522`)75 and exits`).

4. **`--`); transport 2 without a boundkeep writes `-fworkdir"{`verb does session.  
Tests call `renderers_cli_main` / `_dispatch_ not exist.** Service/smoke/replay all use `TemporaryDirectory` with no}:{backend}:{frames}"` bytes and ignores those flags.  
-render flagers (`service`.py: only371 (`tests Failure test–/374core/rendering/test`, never asserts ` acli replay.py bundle:596_cli.py:52 (`133–-258`) — they,846`). Success workdirs are always deleted167; retention cannot`). never Frozen go acceptance through: ` be requested.

---gateway every. backend failuremain has`. Docs a replay

## T7.4 — ISSUES

**Blocking even**

1. **Service bundle tell authors. to  
 bind- a Support session failures first are excluded from bundles capture (`service.py:121–122`, ` (`docs/contracts cannot be replayed —1861–1869`:/render-backend-v digest is1 `_.mdRE:PLAY801_-VERBS the` is `803`).

**2. wrong object.** Capturerender|finalize|plan` Help omits `replay` pins `compute_request_ only). Thedigest(request.to_dict freeze still (blocking)**  
Frozen()):` ` (createabsolute|list| parametrizes `support` (`inspect|validate|smoke| `130replaytimeline`_ appearpath`) (`–131`, `service.py153:1951`, in help.  
`astr `id–contracts/.py155core:`)./821

gateway**/3–826. Generic-`). On diskcodehelp audit.py is: scoped/93` is only `{{, `gamed (blocking).**  
create,list,inspect,request.json` has localized- Scans ninevalidate,smoke}}`. Replay `inputs files (`/<sha>` paths (`test_generic_code_ is parsedreplay.py:147–160 (`cliaudit.py:70–80.py:225-248`),`). not ` Replay hashes `request.json` and refuses mismatch`) and routed (`dispatch.pyastrid/core/rendering as tamper/*:454`. Miss,-455es `profile.py`: **including `_remotion_canvas``, plus with `--acknowledge-drift` + `rem top-level `replayotion/src/Root.** (`cli.py:831tsx::getCanvas` (`–844`). T7.4 tests only` at `:455`).

**3. ` hand-build bundlesprofile.py:110–129inspect whose digest` drops`, `263`) is already the frozen discovery — a fields (blocking)**  
Frozen localized payload (`test_replay concrete Remotion branch: source in.py: generic71 profile kind, precedence,–85 code active revision, trust eligibility/`). A real. Also missesreason, permissions, capabilities, T7.3 bundle `scaffold.py:8, **aliases, conflicts, overrides66 is dead` (`ffmpeg`, `remotion`).  
- Case**.  
`_.

2. **Localizedcmd_inspect` (`cli inputs are not used-sensitive `\bname\.py.**: Replayb403` (`-456`)25 prints `source copies only **–28files** in the bundle_kind`, eligibility, root `,required not `inputs/``, `93`) is written (`_clipermissions.py`,: `848capabilities–`.851`). Request to miss `Rem It never calls `resolve still points at `otion_`/`FFmpegevidence` / `conflicts` and `ffmpeg_specialinputs/<sha>`. `()` evenraw_command` never readsization` (`contracts though the `timeline_path`.py:98`, `service registry already has `priority_ (`backend.py:504.py:2161`).

index`, `eligibility–528**4. Debug artifacts in.active_revision`, `alias`), so tests the tree (blocking_chain`, `override` stay).** Repo (`registry.py:300 green. `- root340 has `test_corrected_bundle_input_requires_acknowledgement`).smoke- T7wave..wave.mp4`, `.lock_then_succeeds`1 tests`, `.provenance.json` ( only check only checks exit 0 +sidecar ` command/ `stoutput` is this_size > 0`ops/binaries/capabilities worktree path (`test_replay.py:/source/eligibility (`,305–309test_cli.py:73 `smoke-87`), not expected bytes-wave.wave.mp`)..



3**.4 **Frozen. `4.provenance.json:59smoke` default output is not protocol not`). Tasklist: do temporary (blocking)**  
 reused.** Replay instantiFrozen: Render not commit generated MP4s; T7.6:ates `CommandTransport` andService + ** clean of debug artifacts. `temporary output**, no project*.mp4` is git skips `RenderService` (no support/validate/ignored run (.  
Workspacepublish) (`cli.py: is a ``.gitignore:54`); `.871–882TemporarylockDirectory` /` (` `.provenance.json`).cli.py `:cwd`596` are not.

Package is the empty temp workspace-data asserts exist and-,610 not `candidate are real (`test_package.pack_root` (`); published_data.py:55service uses pack file defaults–80 to `Path.cwd()`; root at `service.py:1842 / f"smoke-{id reused}.mp4"` (`:`). `argv[0 at]` is replaced with587-591 `sys.executable` (``). That writes `test_freeze.py:246–257`). No ` intocli cwd.py (:863–865`). Planner/finalizer ids are resolvedand can dirtyCHANGELOG`; README has no epic section a project). — convention does Tests only via `renderers.get` (`cli not clearly.py:779– use require one.791 `--out` or`) — accept a cwd files `plan`/`finalize` bundle is (`test_cli.py: “147-196`). Servicenot resolvable”.

4. **Ack itself has no ledger- (passafter-fixture-correction).

List/inspect does not prove protocol do output.** Manifest stay-drift ack static: ` reload_default_registries` isuses the same timeline-ign YAML-only (`registry.py:1-7oring fixture (``, `clitest_replay.py:231.py:262-267–265`). Input-correction ack`). Validate is does not compare to `_reference_output_bytes`.

**Not `validate_pack` only (`cli.py:464-505 blocking:** Manifest`) — static-by-default; no eligible drift without `--acknowledge-drift` is refused (`-only conformance pass existscli.py:809. Unknown/bad args are–823`). Unknown renderer refused non-zero (` (`cli.py:784cli.py:–791`). Fresh53`,-bundle byte `test_cli.py: match is only216-227 vs this`).

---

## fixture’s window T7.2 — ISS/output_nameUES

**1. `, not vs localized inputs.replay` has no `--json` shape (blocking)**  
Frozen + T7.2 extras: verb-specific `--json` for create/list/inspect/validate/smoke/**replay**/support.  
`replay_parser` has no `--json` (`cli.py:225-248`). `_cmd_replay` only prints text (`:907-915`). `test_cli_contract.py:21-24` waves this off as T7.4; that does not satisfy this batch’s frozen list.

**2. Exit codes match neither frozen 2/1/130 nor Astrid 2/1 (blocking)**  
What the code does:
- Domain failures: `_EXIT_DOMAIN = 1` (`cli.py:37-38`, used at `:321`, `:398`, `:483`, `:536`, `:583`, `:704`, `:733`).
- Argparse / no subcommand: 2 (`:53`, `SystemExit` in `test_cli.py:224-227`).
- Plain `create` conflict: raise `AstridError` (`:58-65`) → `render_astrid_error` returns **2** (`errors.py:262`). JSON create conflict returns **1** (`cli.py:304-321`).
- Interrupt with attached `RendererError`: print + **return 1** (`cli.py:720-737`). Transport attaches the error and **re-raises** so exit-130 can happen (`transport.py:224-240`; contract `render-backend-v1.md:493-495`). CLI swallows that and invents exit 1.
- Bare `KeyboardInterrupt` (no `renderer_error`): re-raised (`cli.py:728-729`); gateway does not catch `BaseException` → traceback.

Frozen: expected=2, degraded=1, interrupt cleanup then 130.  
Astrid: expected=2, degraded=1 (`errors.py:262`).  
T7.2 brief: 0 vs non-zero, **no new taxonomy**.  
Actual: invented `_EXIT_DOMAIN=1`, inconsistent with gateway 2, and interrupt is 1 not 130. Tests only assert `== 0` / `!= 0` (`test_cli_contract.py:673-709`).

**3. Interrupt tests are synthetic (blocking as contract coverage)**  
`_interrupting_render` plants `renderer_error` on `KeyboardInterrupt` (`test_cli_contract.py:608-619`). They never hit transport SIGINT, cleanup-then-130, or a host interrupt without the planted error. `_handle_interrupt` without that attr re-raises (`cli.py:728-729`) — traceback dump, contrary to T7.2 extras.

**Not blocking:** create/list/inspect/validate/smoke/support JSON keys are asserted and are not a universal envelope. Env-discovered packs are ineligible; `--pack-root` extra roots are trusted (tests treat env as the “untrusted extra root”). Support-on-decline uses frozen `RendererError` keys. Cwd-independence tests exist for list/inspect JSON only. `test_astrid_error_contract.py` / `test_exec_error_contract.py` are unrelated to this CLI and are not broken by it.Subagent findings include a session-gate hole and a digest mismatch. I’ll confirm those against the gateway allowlist and a few other high-severity claims before the verdict.**ISSUES**

The claimed Batch 7 tests pass (`76` in the six new modules). The frozen Batch 7 / M2-04 / M2-05 / M2-07 contracts do not. Tests call `renderers_cli_main` / hand-built bundles and never exercise the public gateway or a service-captured bundle.

### Blocking

**1. Renderer CLI is session-gated, not unbound**  
Tasklist/plan: verbs “remain unbound from project sessions.”  
`SPRINT1_UNBOUND_ALLOWLIST_CONTRACT` has no `renderers` or `replay` (`astrid/core/gateway/__init__.py:149-170`). `python3 -m astrid renderers list` with no session prints “no session bound” and exits `2`. Docs inverted the contract (`docs/contracts/render-backend-v1.md:801-803`: “Bind a session first”). Tests never go through `gateway.main`.

**2. `inspect` omits required discovery fields**  
Required: source kind, precedence, active revision, trust eligibility/reason, permissions, capabilities, aliases, conflicts, overrides.  
`_cmd_inspect` (`cli.py:403-456`) reports manifest + eligibility + `source_kind` only. It never calls `registry.resolve_evidence` (`registry.py:300-338`), which already has `priority_index`, `active_revision`, `alias_chain`, `override`.

**3. `smoke` does not use a temporary output; debug artifacts were committed**  
Plan: “temporary output,” no project mutation. Default is `Path.cwd() / f"smoke-{id}.mp4"` (`cli.py:587-591`). That left committed `smoke-wave.wave.mp4.lock` + `smoke-wave.wave.mp4.provenance.json` and an untracked `smoke-wave.wave.mp4` at the repo root.

**4. Service-captured bundles cannot be replayed**  
Capture pins `compute_request_digest(request.to_dict())` (host `timeline_path`) (`service.py:1951`). `write_replay_bundle` writes localized `request.json` with `inputs/<sha>` (`replay.py:147-160`). Replay hashes `request.json` and treats mismatch as tampering, including with `--acknowledge-drift` (`cli.py:831-844`). Live check: original vs localized digests differ. T7.4 tests only build pre-localized payloads (`test_replay.py:71-85`).

**5. Replay never copies `inputs/`**  
`_cmd_replay` copies only files in the bundle root (`cli.py:848-851`). Localized hashed inputs stay behind. Tests stay green because `raw_command` generates media without reading `timeline_path`.

**6. `--keep-workdir` is missing**  
Successful workdirs are always deleted (`TemporaryDirectory` in service/smoke/replay). No flag exists. Frozen M2-05: delete unless `--keep-workdir` is requested.

**7. Help and author docs omit `replay`**  
`help.py:93` is `create,list,inspect,validate,smoke`. Same list in `docs/packs/aliases-vs-forks-vs-overrides.md:282-283`. No `astrid renderers replay` command is documented. Replay also has no `--json` shape (`cli.py:225-248`, `_cmd_replay` is text-only) despite “each CLI verb has a frozen `--json` shape.”

**8. Exit / interrupt contract is a new taxonomy**  
Plan: reuse AstridError (expected `2`, bugs `1`, cleanup then re-raise for `130`).  
Code invents `_EXIT_DOMAIN = 1` for domain failures; JSON create-conflict is `1` while plain create raises `AstridError` → `2`; interrupt with a planted `renderer_error` is swallowed as `1` (`cli.py:720-737`) instead of cleanup + re-raise. Tests only assert `0` vs non-zero (`test_cli_contract.py:673-709`).

**9. T7.6 freeze / audit / matrix do not lock the epic**  
- `test_freeze.py` uses `FakeTransport`; `optimized` / `audio-reactive` only set unused `backend_config`. Failure cases never assert a replay bundle.  
- `test_generic_code_audit.py` scans nine files and misses `profile.py` (`_remotion_canvas` / `remotion/src/Root.tsx::getCanvas` at `profile.py:110-129`).  
- `.oracle/verification.md` repeats Batch 5’s `7778 passed / 62 failed` (`m1-gate.md:18`). Batch 7 added these modules; that count is not a re-run at `7b7bf153`. `make ci` is not recorded.

### Not blocking (do not treat as a pass)

List/inspect stay static (YAML registries, no backend import). Support/create JSON keys are verb-specific, not a universal envelope. Manifest drift without `--acknowledge-drift` is refused. Package-data asserts exist. Golden-path *create → validate → smoke* prose exists, but it stops before replay and tells authors to bind a session.

Rework T7.1–T7.4 and T7.6 against the frozen tasklist, not the T7.2 “0/non-zero only” brief. Do not start Phase 6.
