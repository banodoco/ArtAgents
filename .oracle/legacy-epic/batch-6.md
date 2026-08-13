I'll review Batch 6 as a Megado checkpoint: first the megado skill and the incremental diff, then I'll judge whether the claimed work actually landed.I'll pull Batch 6 acceptance criteria and the incremental diff, then fan the review across isolated subagents so only findings come back here.There's already a Batch 6 check-in file. I'll read prior oracle style and the diff, then dispatch reviewers against the acceptance criteria.The check-in file is leftover chatter. I'll pull the Batch 6 contracts from the plan and launch isolated reviewers for each task.Subagents are reviewing the four slices. I'll read the SDK, scaffold, and conformance code in parallel so I can judge the same contracts independently.I'll review T6.3 against the listed RenderContext capabilities, starting withI'll review T the implementation,6.2 against the acceptanceI'll review T6.5 tests, and the batch commit criteria by reading the SDK and T6.6 against range., the scaffold contract, CLI routing tests, and the raw renderer wire path in, and wheel parallel.-smoke requirements byI'll review reading the listed T6.4 by files first. reading the conformance harness and comparing raw vs SDK fixtures for whether they actually assert identical wire fields.Next I’ll read the SDK/raw fixture backends and the request JSON so I can judge whether the harness compares real wire output.The RenderContext implementation was truncated mid-class; next I’ll read the rest plus the helpers it wraps.Next I’ll verify dispatch/help wiring, line budgets, packaged fixtures, and whether the smoke path actually asserts the golden sequence.`renderer_main` looks like a host dispatcher, not an author hook — I’ll check the fixture wiring for recursion and whether the plan’s `render(request, context)` contract is actually implemented.The SDK path looks like it may re-dispatch into the same raw backend. I’ll check the T6.4 ticket and schema validation next.Next I’ll compare wire serialization, `_json_safe` sources, the raw-command fixture path, and the batch diff.The SDK fixture may just re-dispatch into the raw command. I'll read the scaffold and how `renderer_main` is supposed to call author `render(request, context)` hooks.The documented `python -m` entrypoint looks missing. I’ll confirm that against the batch spec and inspect the actual diff.T6.3 ISSUES

Reviewed `astrid/sdk/rendering.py`, `tests/test_sdk_render_context.py`, and the core helpers `RenderContext` wraps (`build_child_subprocess_env`, transport `_redact_log` / `_secret_environment_values`, `ffprobe_metadata_strict`, `sha256_file`, `RenderService.complete_audio`, `Attachment`). HEAD is `c7a09430` (`batch6: … RenderContext …`). No shell in this read-only pass, so this is file-level review at that commit, not a hunk-by-hunk `git diff`.

---

## Blocking defects

**1. `complete_audio` does not apply core semantics on the public `audio_completer` path**

```1077:1094:astrid/sdk/rendering.py
        Delegates to the bound :class:`RenderService` (``service``) or the
        injected ``audio_completer`` callable exactly like
        :class:`~astrid.core.rendering.service.RenderService.complete_audio`
        does, so the frozen audio/attachment preservation contract applies.
        ...
        if self._audio_completer is not None:
            return self._audio_completer(
                result,
                request=request,
                plan=plan,
                workspace=selected_workspace,
            )
```

That call never goes through `RenderService.complete_audio` (`astrid/core/rendering/service.py:1469-1610`). It skips:

- `RENDERED` short-circuit
- visual-only requirement for `passthrough`/`none`
- `none` vs requested audio profile
- completer must return `RenderResult`
- `passthrough` must become `RENDERED`
- attachment preservation
- video profile/duration freeze
- post-complete `validate_render_result`

If both `service` and `audio_completer` are set, the bypass wins. Tests only exercise the `service=` path (`tests/test_sdk_render_context.py:433-498`). The documented contract is false for a constructor argument the class advertises.

`plan` defaults to `None` (`rendering.py:1072`). The service path then does `plan.profile.has_audio` (`service.py:1509`) and raises `AttributeError` for `audio_ownership='none'` instead of a frozen renderer error.

**2. “Sanitized” runner is not the hardened transport runner — timeout/interrupt can hang and leave descendants**

`CommandTransport` uses `start_new_session=True` and `_terminate_process_group` (`transport.py:177-247`). `RenderContext.run` does not:

```904:933:astrid/sdk/rendering.py
            process = subprocess.Popen(
                command,
                shell=False,
                ...
            )
        ...
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            ...
            process.kill()
            process.communicate()
```

- No process group. `kill()` is the direct child only.
- Second `communicate()` has **no timeout**. A grandchild that inherited the pipes (typical ffmpeg pattern) keeps stdout/stderr open → **indefinite hang** on the timeout and `KeyboardInterrupt` paths.
- `cleanup()` / `__exit__` do not track or reap this `Popen` (`rendering.py:1166-1219`). A crash after spawn, or `__exit__` during `communicate`, can leave orphans.

This is not a sandbox complaint. It is a correctness hole versus the core runner this facade claims to wrap.

**3. Redaction is incomplete on the path that actually returns/raises logs**

Timeout/interrupt redacts with `overlay=env` (`rendering.py:934, 947`). Success and `check=True` failure do not:

```959:972:astrid/sdk/rendering.py
        result = SubprocessResult(
            returncode=process.returncode,
            stdout=self.redact(stdout),
            stderr=self.redact(stderr),
        )
        if check and process.returncode != 0:
            raise_internal_error(
                ...
                details={..., "stdout": result.stdout, "stderr": result.stderr},
            )
```

`redact()` without overlay only scrubs host secret-named env + `secret_values` (`rendering.py:998-1014`). Renderer-supplied `env=` values (the test’s own `MY_FFMPEG_TOKEN`, `tests/test_sdk_render_context.py:315-324`) are printed back and, on failure, copied into frozen error details. Those details are the thing that gets persisted.

`_redact_log` does scrub `?token=` / `?sig=` / `?signature=` (`transport.py:54-57`). It does **not** match `X-Amz-Signature`, `X-Amz-Credential`, or `X-Goog-Signature`. Tests never pass a signed URL through `ctx.redact` / `ctx.log`.

---

## Per-capability checklist

| Capability | Verdict |
|---|---|
| Allocated paths | **PRESENT (WEAK)** — `workspace_path` / `output_path` / `temp_dir` / `outputs_dir` at `rendering.py:699-762`. Rejects `..`, absolute, backslash, empty parts. **After `Path.resolve()`, no re-containment check.** A symlink already inside the workspace (`frames → /tmp`) makes `workspace_path("frames/x")` return an outside path. Tests only cover lexical rejects (`test_sdk_render_context.py:208-224`). |
| Asset descriptor path/URL | **PRESENT** — `asset_path` `813-818`, `asset_url` `820-837`, `resolved_registry` `839-842`. Local staged file + loopback URL tested (`test_sdk_render_context.py:248-277`). Remote URL is returned raw (`827-828`) — access, not a log, but it is a signed-URL carrier. `asset_path` does not `check_path`; staging lives outside the workspace by design (`assets.py:200-205`). |
| Permission checks | **PRESENT (theater-honest, enforcement incomplete)** — `check_path` `768-784` + `_contained` `786-792`. Docstring correctly says convention, not sandbox (`773`). Real for `run(..., cwd=)` (`895`). **Not used by** `probe_media`, `sha256`, `asset_path`, or post-resolve `workspace_path`. `run()` can still exec `/bin/sh -c …`. That matches “not a sandbox”; it does not match “permission-aware subprocess execution” in the M2 brief. |
| Sanitized subprocesses | **PRESENT (WEAK / broken under load)** — `shell=False` `906`, argv-only `880-893`, `cwd` via `check_path` `895`, env via `build_child_subprocess_env` `896-902`. Secret-named **host** vars are dropped (`subprocess_env.py:121-128`, tested `304-312`). **Missing vs transport:** process group, bounded terminate, overlay redaction on all exits, no hang-safe reap. `explicit_env` is an unfiltered inject (`subprocess_env.py:127-128`) — intentional, but then those values must be treated as secrets in logs (they are not). |
| Redacted logs/progress | **PRESENT (WEAK)** — `redact`/`log`/`progress` `1010-1022` delegate to transport `_redact_log`. Host tokens + `secret_values` + Bearer/`sk-` tested `358-375`. `progress` is just `log`. Overlay hole and cloud signed-URL gap above. Success `SubprocessResult` is not passed through `_bounded_logs`. |
| Interruption state | **PRESENT** — `interrupt_requested` / `raise_if_interrupted` `1028-1047` raise frozen `interrupted` (`test_sdk_render_context.py:383-397`). Cooperative only. `run()` does **not** poll the flag during `communicate`; cancel is ignored until the child exits or the timeout fires. |
| Probing | **PRESENT (WEAK)** — `probe_media` `1053-1061` → `ffprobe_metadata_strict`. **No `check_path`.** Core `_ffprobe_metadata` uses `subprocess.run` with the **full host env**, not `build_child_subprocess_env` (`media.py:248-262`). Wrapper tests only a monkeypatched return (`449-466`). |
| Hashing | **PRESENT** — `sha256` `1063-1065` → `sha256_file` (`hash.py:9-16`, 1 MiB chunks). Tested `468-470`. No containment check (fine if not a sandbox). |
| Audio completion | **MISSING/WEAK on the advertised API** — service path is real; `audio_completer` path is a contract-free trampoline (blocking #1). Unsupported-without-completer is correct (`1104-1112`, test `500-509`). |
| Attachments | **PRESENT** — basename regex `1134-1138`, `attachments/<name>`, `Attachment.from_file` `1147-1155` (workspace-relative + sha256). Traversal names rejected (`481-482`). **No size cap; overwrite of same name is silent; not removed by `cleanup`.** Containment of the stored file is real because the name cannot contain `/`. |
| Cleanup | **PRESENT for tracked temp dirs; WEAK for crash-safety** — `temp_dir` recorded `731-746`; `cleanup` `rmtree`s them and `rmdir`s `.astrid-tmp` if empty `1166-1192`. `__exit__` always calls cleanup `1217-1219`. Exception-in-body tested `532-543`. **`__exit__` swallows cleanup errors** (`suppress(Exception)`). `_temp_files` is never populated (`690`, `1184`). `_closed` is only enforced on `temp_dir` / `__enter__` — `run` / `workspace_path` / `add_attachment` still work after close. No process reap. Not using the context manager leaks temps. |
| Docstring: NOT an OS sandbox | **PRESENT** — module `29-30`, class `634-635`, `check_path` `773`, plus “introduces no new security boundary” `645`. That part is honest. Other sentences overclaim: “exactly like `RenderService.complete_audio`” `1079-1082`; “Captured stdout/stderr are … scrubbed of secret values” `865` (not for `env=` on the success/fail path). |

---

## Confirmed OK

- Public surface exists and is exported (`astrid/sdk/__init__.py`, `astrid/__init__.py`).
- Not-a-sandbox disclaimer is explicit and repeated. No fake seccomp/jail story.
- Path allocator rejects the lexical escape set the tests care about (`../`, `/etc/passwd`, `\`, `a/../b`, `//`, nested output names).
- `check_path` uses `relative_to` after `resolve`, so `/workspace-evil` is not treated as `/workspace`.
- Child env policy is the real core helper: safe-base allowlist, secret-name drop, `ASTRID_*` invariants, passthrough must be declared and non-secret (`subprocess_env.py:97-136`).
- `shell=False`, `stdin=DEVNULL`, argv NUL/empty rejected.
- Timeout and non-zero exit map to frozen `timeout` / `internal` kinds (`test_sdk_render_context.py:331-350`).
- Host `*_TOKEN` does not appear in the child (`304-312`).
- Log redactor is the transport scrubber (Bearer, `Authorization:`, `sk-`/`ghp_`/`hf_`/`AIza`, secret-named host values).
- Interrupt flag raises `RendererInterruptedError` with `kind=="interrupted"`.
- `sha256` is the core 1 MiB hasher.
- Attachment names are portable basenames; `Attachment` validates kind/path/sha256.
- Temp dirs under `.astrid-tmp` are removed on both normal exit and body exception.
- Owned materializer/server close hooks exist (currently vestigial: context never constructs them itself; `_owns_*` is True only when they are `None`).
- Asset server `local_url` is loopback and staging-contained (`assets.py:666-673`).

---

**Bottom line:** T6.3 shipped the facade and the happy-path tests. It did not lock the three things this ticket is supposed to be honest about: core audio-completion semantics, a subprocess runner that cannot hang or orphan, and redaction of credentials that actually appear in child output / error JSON. Permission checks are conveniences with documented non-sandbox status; do not treat them as a boundary.T6.4 ISSUES

The harness does run both entrypoints and compares parsed result JSON, but the “SDK implementation” is not a second renderer. It is a host wrapper that re-invokes the same raw `render.py`. Wire parity is therefore almost tautological, and the comparison still has a hole that can hide SDK-only error keys.

## Blocking defects

**1. There is only one renderer. The SDK half re-dispatches into the raw half.**

```116:120:tests/fixtures/renderer_packs/sdk/sdk_render.py
def main(argv: list[str]) -> int:
    _bootstrap()
    from astrid.sdk.rendering import renderer_main

    return renderer_main(argv)
```

`renderer.yaml` command is `[python3, render.py]`. `renderer_main` then does this:

```266:282:astrid/sdk/rendering.py
    projected = request.for_backend(candidate.id)
    request_path = workspace / "render-request.json"
    result_path = workspace / "render-result.json"
    write_json_atomic(request_path, projected.to_dict())
    ...
    response = selected_transport.run(
        "render",
        candidate.manifest.command,  # python3 render.py
```

So the two paths are:

- raw: harness `CommandTransport` → `render.py` → `_shared.py`
- SDK: harness `CommandTransport` → `sdk_render.py` → `renderer_main` → **another** `CommandTransport` → **the same** `render.py` / `_shared.py` → DTO `to_dict()` rewrite

T6.3’s author-facing `RenderContext` is never imported. `sdk_render.py` also bootstraps with core internals (`astrid.core.pack.store.InstalledPackStore`, `InstallRecord`, `extract_trust_summary`, `sha256_file` at `sdk_render.py:54-55`) and `renderer_main` calls private `RenderService._support` (`astrid/sdk/rendering.py:487`). That is a host/core cheat, not an SDK renderer.

M2’s bar is “raw command and Python-SDK fixture renderers.” This pack has one renderer and two launchers. Any extra key both sides emit (they share `_shared.py`) still passes. Independent SDK-vs-raw wire drift cannot appear except in the thin DTO/error rewrite.

**2. Comparison silently drops SDK-only error keys.**

```128:133:tests/core/rendering/test_conformance.py
        for key, item in value.items():
            if key in ("stdout", "stderr") and item == "":
                continue
            normalized[key] = _normalize(item, workspace)
```

The comment admits the SDK/service path may enrich `details` with empty log captures. `_assert_parity` then treats that as identical to raw. The failure case only asserts the **raw** details map (`test_conformance.py:375`); SDK extras disappear in `_normalize`. That is exactly an SDK-only wire field passing the “frozen protocol / no SDK-only fields” check.

**3. The T6.2-pending skip aborts the whole test, including raw.**

```89:93:tests/core/rendering/test_conformance.py
    if entrypoint == SDK_ENTRYPOINT and not SDK_AVAILABLE:
        pytest.skip(
            "astrid.sdk.rendering is not available yet (T6.2 pending); ..."
        )
```

`_run_both` runs raw first, then skip raises. None of the post-`_run_both` assertions run. The module docstring (`test_conformance.py:26-28`) is false. Latent at this checkpoint because `astrid.sdk.rendering` exists, but the harness can still go green without any parity if that spec disappears.

## Per-case checklist

| Case | Fixture | Driven on both? | Wire compared? | Verdict |
|---|---|---|---|---|
| 1. Minimal render | `requests/minimal-render.json` | Yes, `render.py` + `sdk_render.py` | Full normalized dict + sha256 + second raw invoke | **Partial.** Both run; hashes compared. Video file existence/`sha256_file` not checked. SDK is a re-invoke of raw. Determinism not rechecked on SDK. |
| 2. Request-sensitive support | `support-supported.json` (`[0,48)`) + `support-window.json` (`[0,96)`) | Yes | Full normalized dict; supported vs unsupported polarity | **Partial.** Window sensitivity is real. Audio-mode mismatch is implemented in `_shared.support_report` but has no committed fixture. `alternatives` is always `[]`. `schema_version` / full report shape only via parity. |
| 3. Passthrough | `passthrough-render.json` | Yes | Full dict + `audio_mode` fragment | **Partial.** Ownership/`profile.audio_*` are `passthrough` / nulls. Media is the same visual-only MP4 as no-audio (no host mux). Same single implementation. |
| 4. No-audio | `no-audio-render.json` | Yes | Full dict + `audio_mode` | **Partial.** Same as (3) except `audio_ownership="none"`. No independent artifact probe. |
| 5. Attachment | `attachment-render.json` | Yes | Full dict + name/kind/path + real attachment digest | **Strongest case.** Attachment bytes are hashed on disk. Video digest still not checked against the MP4. Attachment only appears if `backend_config["sdk.renderer"]["attachment"]=="manifest"` — both sides see that because they share `_shared.py`. |
| 6. Intentional failure | `failure-render.json` (`output_name: "broken..mp4"`) | Yes | Normalized error JSON + `kind`/`backend`/`message` | **Weak.** Schema-valid name (`[A-Za-z0-9._-]*` allows `..`); backend `validate_request` rejects it (`_shared.py:503-506`). Message only substring-checked. `details` asserted on raw only; empty `stdout`/`stderr` stripped. `schema_version` not asserted. |

Static extra: `test_fixture_pack_static_surface` validates the pack/manifest, not request/result schemas, and only records `command: [python3, render.py]`. `sdk_render.py` is not a pack command.

## How comparison works, and whether it is enough

1. Copy a committed request into a per-side workspace (`request.json`) plus `timeline.json`.
2. Run `CommandTransport` with `[sys.executable, render.py|sdk_render.py]`.
3. Read `result.json` (the file, not the transport-enriched exception).
4. `_normalize`: strip a workspace-absolute prefix from strings; drop empty `stdout`/`stderr`; recurse.
5. `assert raw_normalized == sdk_normalized` (dict equality: extra keys fail, key order does not, list order does).
6. Spot-check a subset of fields (`_assert_clean_render_payload` / support / error).

That is **not** sufficient for “semantically identical wire, no SDK-only fields”:

- Enough to catch *different* keys/values after normalize.
- Not enough to catch *shared* extra-schema keys (one implementation).
- Not enough to catch empty `stdout`/`stderr` on the SDK result file.
- Does not validate requests or results against `astrid/core/rendering/schemas/v1/{request,result,support}.json`.
- Does not compare workspace file sets (SDK writes `render-request.json` / `render-result.json`).
- Does not compare `raw_command/` at all. That T2.2 pack is render-only (`audio=rendered`, no attachment/failure/passthrough/none). `tests/core/rendering/test_conformance.py` never loads it. Cross-pack wire cannot match without remapping `backend` / `backend_fragments`.

Request fixtures are `schema_version: 1` and, by inspection, valid against `request.json` (required fields, profile/audio pairing, qualified `backend_config`, string `metadata`). `broken..mp4` is schema-legal and only fails renderer-side. The harness never asserts that. `timeline.json` is copied and unused by `_shared.render_result`.

**Bottom line:** six cases exist in one harness and both commands are invoked. They do **not** prove two implementations emit the same frozen wire. They prove that wrapping `_shared.py` in `renderer_main` and re-serializing DTOs still looks equal after path-stripping and dropping empty log keys.The only failure looks like a missing local schema package. I'll confirm it's pre-existing and that every new Batch 6 test actually passed.T6.5/T6.6 ISSUES

## Blocking defects

**1. T6.6 wheel (and the “golden path” test) never do a trusted install**

Required sequence: create → static validate → generated test → **trusted install** → smoke &lt;2s.

[`scripts/smoke_wheel_install.sh:218-231`](scripts/smoke_wheel_install.sh) only `copytree`s into `ASTRID_PACKS_PATH` and discovers `source_kind == "env"`. There is no `ASTRID_HOME` install record, no trust acknowledgement, no `execution_eligible` check. `ASTRID_HOME` is exported earlier (`:74-75`) and then ignored.

[`tests/core/rendering/test_scaffold_install.py:230-289`](tests/core/rendering/test_scaffold_install.py) repeats that env-root copy. Trusted install lives only in a **separate** unit test (`:292-320`) that is not what the wheel script runs.

Comment at [`scripts/smoke_wheel_install.sh:161-165`](scripts/smoke_wheel_install.sh) also claims “installed fixture templates”; `create_renderer_scaffold` never loads package-data fixtures.

**2. Generated dest is not an installable / loadable pack root**

[`astrid/core/rendering/scaffold.py:237-241`](astrid/core/rendering/scaffold.py) always writes `pack.yaml` `id` = first segment of the renderer id (`rendering` by default) **into whatever dest the caller passed**. CLI dest defaults to `.` ([`cli.py:51-54`](astrid/core/rendering/cli.py)).

Real install/load refuse that:

```150:156:astrid/core/pack/install_local.py
    if not skip_name_check and source.name != pack_id:
        print(
            f"install: source directory name {source.name!r} must match "
            f"pack id {pack_id!r} declared in pack manifest.",
```

```117:118:astrid/core/pack/loader.py
    if root.name != pack_id:
        raise PackValidationError(f"pack id {pack_id!r} must match folder name {root.name!r}")
```

T6.6 only works because tests/smoke **rename** via `copytree(dest, packs_path / "rendering")` ([`test_scaffold_install.py:252-254`](tests/core/rendering/test_scaffold_install.py), [`smoke_wheel_install.sh:219-221`](scripts/smoke_wheel_install.sh)). `validate_pack` does **not** enforce `root.name == id`, so static validate is a false green on `…/wave` or `…/scaffold-wave`.

A user cannot `astrid packs install` the directory `astrid renderers create` just printed.

**3. Ownership/collision: default pack id is the first-party `rendering` pack**

Default id is `rendering.<name>` ([`scaffold.py:201`](astridChecking/ onecore transport/-log detail and whether `sdk/__all__` name sets match.rendering/scaffold.py), [`cli.py:50`](astrid/core/rendering/cli.py)). `validate_content_id_in_pack` then **requires** pack id `rendering` ([`_common.py:78-83`](astrid/core/pack/_common.py)).

A real trusted install therefore targets `ASTRID_HOME/packs/rendering` and hits [`install_local.py:161-167`](astrid/core/pack/install_local.py) against the official pack (or `--force` overwrites it). File-level collision inside dest is handled; **pack-id ownership is not**.

---

## Confirmed OK checklist

| Check | Result |
|---|---|
| Exactly four dest files (`pack.yaml`, `renderer.yaml`, `render.py`, `test_renderer.py`) | **OK.** Only those names are written ([`scaffold.py:21-26,267-278`](astrid/core/rendering/scaffold.py)). Tests lock dest file list. No 5th dest file; templates are string constants in `scaffold.py`, not extra dest output. |
| Glue ≤50 nonblank/non-comment lines | **OK.** Generated `render.py` is 49 lines under the test’s `#`-only comment rule (shebang excluded). All four files asserted in [`test_scaffold.py:55-68`](tests/core/rendering/test_scaffold.py). |
| No TODO/FIXME/YourName/`pass` placeholders | **OK** in generated text. Tokens `__PACK_ID__` / `__RENDERER_ID__` / `__DISPLAY_NAME__` are substituted. Tests cover TODO/FIXME/XXX/lorem/example.com, not leftover `__…__`. |
| File-level collision | **OK.** Existing dest **file** refused ([`scaffold.py:242-245`](astrid/core/rendering/scaffold.py)); existing scaffold filenames refused unless `--force` ([`:248-260T6.`](astrid/core2 ISSUES

**Blocking/rendering/scaffold.py)). defects**
- ** TestsSuccess result cover both is not the raw. |
| Ownership ( backend wireuid/gid).** `renderer | **OK** at_main` render re-serializes the in write time: `Path-memory D.write_text` only;TO from `Command no sudo/chownTransport.run`, which ([ appends captured`: stdout/stderr onto frozen277- `logs` (`astr278`](astrid/id/core/rendering/core/rendering/scaffold.pytransport.py:750-762)). |
| Write containment inside`). `_write_result dest | **OK.** Fil` then dumps that mutatedenames are constants; writes ` are `target / filename`.to_dict()` (`astr Commandid/sdk/rendering.py is relative `[:164,python3, render.py]186-190`. `output_name` regex rejects `/`.,274-292 Dest itself is not`). The raw backend writes sandboxed to cwd ( `"logs": []`normal (`tests/fixtures/renderer for a dest arg_packs/raw_command). |
| `/backend.py:564-astrid renderers create`567`). Errors already dispatch | strip transport ` **OK** forstdout`/`stderr` to table match the raw result wiring: [` file (`astrdispatch.py:id/sdk/rendering.py315-318,447:204-213`](astrid/core`); the success path/gateway/dispatch.py), does not. Any backend [`cli.py:18 stderr (or a Python warning) makes `--result` differ from the-80`]( raw fixture fileastrid/core/rendering. The fixture/cli.py), help [` test only stayshelp.py:92-93 green while the`](astrid/core child is silent (`/gateway/help.py).tests/test_sdk_ Tests call `rendering.py:323-325cli.main` and `_`).
- **`supportdispatch_renderers` ([` does not use the` raw-testcommand_ workspacescaffold.**.py: Render181-190`](tests uses/ `coreworkspace/ =rendering request/_testpath.parent` (`astr_scaffold.py)). **Caveid/sdk/rendering.pyat:** `renderers`:146-163 is **not** on ``). Support calls `_support_report` withSPRINT1_UNBOUND_ALLOWLIST_CONTRACT` no workspace (`astrid/sdk/rendering ([`gateway/__init__.py:149-170.py:147-154`),`](astrid/core which invents a `TemporaryDirectory`/gateway/__init__.py)), so `python3 and runs the backend there -m astrid renderers (`astrid/sdk/ create` failsrendering.py:485-491 without a session.`). Raw backends Neither golden treat the request file’s parent as the path exercises invocation workspace (` `tests/fixtures/renderer_gateway.main`. |
|packs/raw_command/backend.py:519-521 Wheel smoke is real`). Relative `timeline code, not a_path` / sibling comment | **OK as assets from an env the caller’s request dir-install smoke are not present.** [`. Thatsmoke_wheel_install.sh is a protocol semantic:172 change, not just-289`](scripts/ ansmoke_wheel_install.sh internal helper.
- **Document) actually:ed CLI create → ` never runs `validate_pack` → envrenderer_main`.** The copy → `candidates module advertises `` → `python -m astrid.CommandTransport` smoke ×sdk.rendering render|support2 with ` --request … --result …elapsed <`  (`2astr.id0/sdk` →/ pytestrendering on.py:7-10`). There is no `test_renderer.py`. `if __name__ == Asserts wheel "__main__"` and no `__ import viamain__.py`. `python `site-packages`. -m astrid.sdk Does **.rendering` onlynot** call `astr defines functionsid renderers create` or and exits 0 — trusted install. no `-- |
| Deterministic &request/--result`lt;2s smoke asserted read, | **OK** in no result file.

 [`**Confirmed OK**test_scaffold_install.py
- Public:50 names exist,274-288: `renderer_main`, `render`,,319 `support`, `RenderContext,334` (`astrid/-351sdk/rendering.py:71`](tests/core/,83-176rendering/test_scaffold_,300-375install.py) and [`smoke,383-442`).
_wheel_install.sh:- `renderer_main`200,262, argparse is `verb` plus271`](scripts/smoke required_wheel_install.sh). `--request` / `--result Media is `b` (`astrid/sdk"astrid-scaffold-"/rendering.py:120- + output_name`; no127`), timestamps. same flags Byte-stable result as the raw fixture JSON asserted. (`tests/fixtures/renderer |
_packs|/ pyrawproject_ packagecommand-/backend.py:588-data | **N590`).
- Request parse/A for scaffold is `Render.** Templates live inRequest.from_dict` (` `scaffold.py` (astrid/sdk/renderingshipped as.py:178-183`). Written code). No success payloads  are core DTO `5th packageto_dict()` only-data template file (`astrid/sdk;/rendering.py:186- [`190`;pyproject.toml:60 `RenderResult.to_dict` at-65`](pyproject.toml) only `astr schemas /id/core/rendering/ renderer_paritycontracts.py:1573- / pack1584`; `SupportReport y.to_dict`amls. |

**T at `946-9576.5** is`). No extra close on keys on the four-file those DT writeOs.
- ` + CLIrender()` / table + line `support()` build `Render budget. **Request` with the frozenT6.6** is field set (`astr not closed: wheelid/sdk/rendering.py/golden:344-358,414 path substitute-428`; an env-root rename asserted for trusted install, and at the dest the `tests/test_sdk_rendering.py:61- scaffold73,467-478 actually writes cannot`).
- Lazy be installed `import astr or discovered withoutid` order that rename plus is exact a colliding first: `_SDK_EXPORTS-party pack id` ==. `EXPECTED_PUBLIC_NAMES` (`astrid/__init__.py:7-40`; `tests/_sdk_contract.py:3-36`). Collision test still requires no shadow of top-level `astrid.*` modules (`tests/test_sdk_public_surface.py:112-117`); there is no `astrid/render.py` / `support` / `renderer_main` / `RenderContext`.
- Heavy rendering machinery is function-local: `RenderService`, `CommandTransport`, `load_default_registries`, `validate_render_result`, `write_json_atomic`, transport redaction, `ffprobe_metadata_strict` (`astrid/sdk/rendering.py:118,188-196,251-255,334,469,526,873-878,999-1013,1059`). Module-level imports are DTOs + `sha256_file` + SDK `_json_safe` (`58-69`). `import astrid.sdk.rendering` is asserted not to load service/transport/registry/artifacts (`tests/test_sdk_rendering.py:555-580`). `astrid/core/rendering/__init__.py` only re-exports contracts, so the contracts import does not pull the service.
- Happy-path fixture field sets match the frozen result/support schemas (`tests/test_sdk_rendering.py:326-334,366-374`). Failures use `RendererError.to_dict()` (`astrid/sdk/rendering.py:193-227`; field set locked at `tests/test_sdk_rendering.py:399-408`).

**SDK-only fields / protocol changes**
- No new wire keys on `RenderRequest` / `RenderResult` / `SupportReport` / `RendererError`.
- SDK-only *semantics* on frozen fields: transport-injected `logs` on success (above); support runs in a throwaway workspace (above); pre-dispatch errors use `backend="astrid.core"` (`astrid/sdk/rendering.py:219`) vs raw `raw_command.renderer` (`tests/fixtures/renderer_packs/raw_command/backend.py:409-418`) — correct for a host, wrong if this is treated as a backend twin.
- `render()` / `support()` sanitize with `astrid.sdk.results._json_safe` (`astrid/sdk/rendering.py:69,356-357,426-427`), not `contracts._json_safe` (`astrid/core/rendering/contracts.py:141-166`). The SDK helper keeps NaN/unknown types and does not unwrap `str` Enums. `RenderRequest.__post_init__` still re-validates, so this is not a new wire field, but it is not “reuse core `_json_safe`” for those args.
- Could not exec `git diff C6-batch5-done..c7a09430` (no shell). Current `astrid/core/rendering/schemas/v1/*.json` still look like frozen v1 (`additionalProperties: false` on result success). The commit message also includes M1 / scaffold / conformance work; this review does not certify that range left schemas untouched.

**Heavy imports actually function-local?**
Yes for the rendering stack (service, transport, registry, artifacts, publication, media). Not for core DTOs / `sha256_file` / `sdk.results` (intentional). `import astrid.sdk` still eagerly imports `rendering.py` (`astrid/sdk/__init__.py:127-133`); that file itself stays light.

**Public export lists complete and ordered?**
- Complete for T6.2: `render`, `renderer_main`, `support`, `RenderContext` are in `_SDK_EXPORTS`, `sdk/__all__`, and `EXPECTED_PUBLIC_NAMES`.
- Lazy order is correct and is what `test_import_astrid_exposes_exact_curated_sdk_names` checks (`astrid/__init__.py:7-16` vs `tests/_sdk_contract.py:3-12`).
- `astrid/sdk/__init__.py::__all__` (`150-186`) is a different, category-sorted order and also exports pre-existing `run_executor` / `run_orchestrator` (not in `_SDK_EXPORTS`). That mismatch predates T6.2 and is not what the lazy-import contract tests.Subagent findings need a second look. I'll verify the ones that would actually block Batch 6: session binding, pack-id collision, transport log mutation, and the support workspace.**ISSUES** — do not start Batch 7.

Batch 6 shipped the named files and the acceptance suites are green, but the user-facing golden path and two wire/lifecycle contracts are not met. Frozen protocol files were not touched.

### Blocking

**1. T6.5 / T6.6 — `create` output is not installable; default pack id is the first-party `rendering` pack**

`create_renderer_scaffold("wave", dest)` writes `pack.yaml` `id: rendering` into whatever folder the caller passed (`astrid/core/rendering/scaffold.py:201,238`). `load_pack_manifest` and `astrid packs install` both require `root.name == pack_id` (`astrid/core/pack/loader.py:117-118`, `install_local.py:150-156`). A dest named `wave` (or `.`) therefore cannot be loaded or installed.

The first-party pack is also `id: rendering` (`astrid/packs/rendering/pack.yaml:2`). Even a correctly named dest would collide with Remotion/FFmpeg/hybrid on trusted install (`install_local.py:161-167`).

T6.6 papers over this: pytest and `scripts/smoke_wheel_install.sh` `copytree` the dest into a folder named `rendering` and write an `InstallRecord` by hand (`test_scaffold_install.py:252-254,93-128`; `smoke_wheel_install.sh:218-231`). They never install the directory `create` just wrote. `validate_pack` does not check folder name, so static validate is a false green.

The specified path — create → static validate → generated test → **trusted install** → &lt;2s smoke — does not work on the scaffold a user actually gets.

**2. T6.2 — `support` does not use the request workspace**

Render uses `workspace = request_path.parent` (`astrid/sdk/rendering.py:146-163`). Support invents a `TemporaryDirectory` (`astrid/sdk/rendering.py:147-154,485-491`). Raw backends treat the request file’s parent as the invocation workspace. Relative `timeline_path` / sibling assets are absent. That is a protocol semantic change, hidden because the fixture’s support only reads window/audio out of the JSON.

**3. T6.2 — success result is not the raw result file**

`CommandTransport` appends captured stdout/stderr onto `RenderResult.logs` when the child is noisy (`transport.py:750-762`). `renderer_main` then writes that mutated `to_dict()` (`rendering.py:164,186-190,274-292`). Raw backends write `"logs": []`. The error path already strips transport `stdout`/`stderr` to match the raw file (`rendering.py:204-213`); the success path does not. Silent fixtures keep the equality tests green.

**4. T6.3 — `RenderContext.run` timeout/interrupt can hang**

Unlike `CommandTransport` (`start_new_session` + process-group teardown), `run()` uses bare `Popen` and then `process.kill(); process.communicate()` with no timeout (`rendering.py:904-933`). A grandchild that keeps the pipes open (typical FFmpeg pattern) hangs the specified timeout/interrupt path. `__exit__` does not reap the child.

### Confirmed OK (do not rework)

- M1 handoff: no protocol/schema/service/transport/backend edits in `C6-batch5-done..c7a09430`. `.oracle/m1-handoff.md` matches that.
- Public SDK names: `render`, `renderer_main`, `support`, `RenderContext` are on `_SDK_EXPORTS`, `sdk/__init__.py::__all__`, and `EXPECTED_PUBLIC_NAMES`. Heavy service/transport/registry imports are function-local.
- `RenderContext` exists with the listed conveniences and an explicit “not an OS sandbox” docstring. Path/asset/env-scrub/redact/interrupt/probe/hash/attachment/cleanup tests cover the happy path.
- Four files only; glue ≤50 lines; no TODO/FIXME placeholders; file-level collision/`--force`; command is `[python3, render.py]`; `astrid renderers` is on `_TOP_LEVEL_HANDLERS`.
- Targeted Batch 6 suites: only `test_sdk_public_surface.py::test_gateway_run_passes_bound_project_via_request_metadata` failed here (`banodoco_timeline_schema` missing) — pre-existing env, not this batch.

### Note (not a rewrite trigger)

T6.4 drives `sdk_render.py` → `renderer_main` → the same `render.py` / `_shared.py`. That matches the T6.2 brief (host dispatcher), so it is not a separate fail, but it does not prove an SDK-authored renderer. Do not treat it as two implementations in Batch 7 docs.

Rework only this batch. Recommit and resubmit `C6-batch5-done..HEAD`. Minimum bar: `create` dest is a loadable pack with a non-colliding pack id; support uses the request workspace; success result file matches the raw backend file (no transport-injected logs); `RenderContext.run` cannot hang on timeout.
