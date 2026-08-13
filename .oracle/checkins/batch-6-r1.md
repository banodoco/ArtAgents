I'll review Batch 6 as a read-only checkpoint: first load the megado review process, then inspect the incremental rework against the four previously raised issues.I'll pull the prior verdict, Batch 6 acceptance criteria, and the incremental rework so the review is against the claimed fixes, not the whole batch.Prior verdict is four host-fixed issues. Next I’ll inspect the incremental rework and verify each one against the code, not the commit message.The rework is small and targeted. I’ll verify each of the four claimed fixes in the current source, including whether tests and the wheel smoke path actually install the scaffold.While those reviews run, I’ll read the current implementations and the install/smoke tests myself so the verdict isn’t just secondhand.I'll verify the support-workspace claim against the current code and the incremental diff.I'll inspect `_backend_render`, transport log appends, the error-path strip, and the success-result tests.I'll verify the claimed scaffold/installability fix against the incremental diff and the files you listed.I'll verify the claimed process-group teardown by reading `RenderContext`, the transport mirror, and the tests.Next I’ll compare the success wipe with the error-path strip and see who consumes `_backend_render`.The smoke script still looks stale. Next I’ll read the scaffold/create path and the T6.6 install tests in full.Need the smoke script’s scaffold/install path and whether dest default / `--id` rejection are actually tested.The wheel smoke script still assumes pack id `rendering`. I’ll read how it names the dest and whether that path can still succeed.Cleanup still looks like a single-process kill. I'll check `_child_process` lifetime, tests, and the transport interrupt path.1. VERDICT: PARTIALLY FIXED

2. Evidence

Transport still **appends** captured streams; it does not replace backend logs:

```750:761:astrid/core/rendering/transport.py
    if isinstance(parsed, RenderResult):
        captured = [
            f"{stream}:\n{text}"
            for stream, text in logs.items()
            if text.strip()
        ]
        parsed = replace(
            parsed,
            logs=[
                _redact_log(log, secret_values=()) for log in parsed.logs
            ]
            + captured,
        )
```

Success path wipes **all** logs, not the suffix:

```298:306:astrid/sdk/rendering.py
    # ... strip the injected portion before serialization ...
    if isinstance(validated, RenderResult) and validated.logs:
        validated = replace(validated, logs=[])
```

Error path only removes transport `stdout`/`stderr` keys:

```205:214:astrid/sdk/rendering.py
        if isinstance(details.get("stdout"), str) and isinstance(
            details.get("stderr"), str
        ):
            details.pop("stdout", None)
            details.pop("stderr", None)
```

`_backend_render` is only called from `renderer_main` (`astrid/sdk/rendering.py:157`). Public `render()` still goes through `RenderService` and keeps transport-appended logs in-memory.

Success test is raw-fixture wire equality (`tests/test_sdk_rendering.py:321–325`). Raw fixture already has `"logs": []`; there is no noisy-stdout or backend-authored-log case.

3. Remaining holes

- Comment says “injected portion”; code is `logs=[]`.
- Transport injection is distinguishable (`parsed.logs + captured` as `"stdout:\n…"` / `"stderr:\n…"`). The fix does not use that.
- Protocol allows authored logs (`docs/contracts/render-backend-v1.md:758` `"logs": ["video-tool render completed"]`). A backend that writes logs through this entrypoint loses them.
- No test that a noisy child still writes `"logs": []` **and** that authored logs survive.

4. New defects

Wiping `validated.logs` is a protocol semantic change on the SDK rewrite path: transport diagnostics are gone (good for raw-command parity), but legitimate backend `logs` are also dropped (bad vs contract). In-process host results are unchanged.Checking** dest default handling and whether any new tests cover the collision/`--id` guards1. VERDICT: PART.IALLY FIXED**

Timeout/KeyboardInterrupt in `run()` no longer unbounded-hang on POSIX. They are not a transport mirror, and `__exit__` still does not kill the process group.

**2. Evidence**

- `start_new_session=True`: `astrid/sdk/rendering.py:939`
- Timeout / `KeyboardInterrupt` call `_kill_process_group`: `959`, `971`
- `_kill_process_group`: `os.killpg(..., SIGKILL)` then `communicate(timeout=5)`: `1002–1028`
- `cleanup()` / `__exit__` reaps *something*: `1232–1239`, `1281–1283`

Transport (`astrid/core/rendering/transport.py:207–253`, `433–548`) is not mirrored: SIGTERM + grace, leftover-group wait, KI-safe drain, generic post-spawn `except` that still terminates the group.

Tests (`tests/test_sdk_render_context.py:331–337`, `383–396`): timeout is a lone `sleep(**130). VERDICT: PARTI`; interrupt is the cooperativeALLY FIXED**

Core create flag only. No grandchild/ path now derivesFFmpeg tree, no SIGINT- pack idduring-`run()`, no from dest and refuses cleanup reap. first- Contrast `party `rendering`. Claimed T6.6 “tests/core/rendering/no Installtest_transport.py:163Record / wheel–213`.

** golden path installs3. Remaining holes ( dest” issame defect class not true.

)**

- `**2. Evidence**cleanup()` uses

- Pack id from dest folder; `child.kill()` not `rendering` rejected: `killpg` (`123 [5scaffold.py:209`).-222](astr A liveid/core/rendering/ tree withscaffold.py)
- `--id` pack a pipe-holding prefix must equal grandchild (the dest name: [scaffold original F.py:272-279Fmpeg case) is not](astrid/core group/rendering/scaffold.py)
-killed on- `create `__ wave acexit__me`.- `wave` → `idcommunicate(timeout=5)`: acme-wave`, bounds renderer `acme-wave the hang;.wave` (default the grandchild can `{pack still orphan}.{name}`.
- Other exceptions): [scaffold.py:233 after `Popen` (`](astrid/core924/rendering/scaffold.py),–999 [cli.py:51-56`](astrid/core has no generic/ `renderingfinally/cli.py)
- Installability invariant` still `root.name == pack/`except`) never call `__id`: [loader.pykill_process_group`;:117-118] they fall(astrid/core/ through to that `pack/loader.py), [kill()`.
- `_killinstall_local.py:150-156_process_group` swallow](astrid/cores `communicate/pack/install_local` timeout.py)
- T6. (`10275/T6.6–1028`) with no now scaffold `wait()`. `tmp_path / " Unwave"` with `id: wavereaped child possible` / `wave; `_child.wave`: [test__process` is never clearedscaffold.py:47 (`706`,-48 `948`).
- Windows,102: no `kill-110](tests/core/pg` → `process.kill()` only (`rendering/test_scaffold.py), [test_scaffold_1022install.py:46-48,240](tests/–1026`).
- `timeoutcore/rendering/test_=None` `scaffold_install.py)
-communicate` Env “ still unbounded —install” is still ` expectedcopy.

tree**`4 into `.packs New defects-path**

/-wave Doc`string (not `rendering`): [ “Mtest_scaffold_install.pyirrors transport” (`:251-254](1008tests/core/rendering/`) is false.
- Cooperativetest_scaffold_install.py `interrupt_check` never)
- Trusted path still hand stops-writes `InstallRecord`: a [test_scaffold_install.py:93-128 running child.,299-301](tests/core/rendering/test_scaffold_install.py)
- Dest default is still `"."`: [cli.py:52-56](astrid/core/rendering/cli.py)
- Wheel smoke unchanged / old contract: [smoke_wheel_install.sh:197-221](scripts/smoke_wheel_install.sh)

**3. Remaining T6.5/T6.6 holes**

- `astrid renderers create wave` (`dest=.`) uses cwd name as pack id. Mixed-case cwd (e.g. `Astrid-oracle`) is not installable (see §4).
- T6.6 still does not call `install_local` / `astrid packs install`.
- Trusted eligibility is still a fabricated `InstallRecord`, not a real trusted install.
- Wheel T6.6 still scaffolds `scaffold-wave`, asserts `id == "rendering"` / `rendering.wave`, then `copytree` into `packs-path/rendering`. That now **fails** (dest id is `scaffold-wave`) and still never trusted-installs.
- No tests for dest=`rendering` or `--id` prefix mismatch.

**4. New defects**

- `_pack_id_from_dest` lowercases dest (`dest.name.strip().lower()` [scaffold.py:209](astrid/core/rendering/scaffold.py)) while loader/install compare case-sensitively. Dest `Wave` writes `id: wave` into folder `Wave` → not installable.
- Stale help/docs: `--id` still “default: `rendering.<name>`” [cli.py:62](astrid/core/rendering/cli.py); scaffold docstring still `rendering.<name>` [scaffold.py:253](astrid/core/rendering/scaffold.py); T6.6 module docstring still `rendering.<name>` [test_scaffold_install.py:9](tests/core/rendering/test_scaffold_install.py).
- Collision error suggests `--id` as a workaround [scaffold.py:220](astrid/core/rendering/scaffold.py), but `--id rendering.wave` is then rejected by the prefix check.**VERDICT: PARTIALLY FIXED**

The TemporaryDirectory support workspace is gone. `renderer_main` matches raw backends. Public `support()` still does not use “request file parent,” and nothing asserts that.

### Evidence
- `renderer_main` sets `workspace = request_path.parent` and passes it to both verbs (`astrid/sdk/rendering.py:146-154`).
- Public `support()` uses `Path(parsed.timeline_path).resolve().parent` (`astrid/sdk/rendering.py:446-460`).
- `_support_report` no longer invents a dir; `workspace is None` raises (`astrid/sdk/rendering.py:504-505`). Only callers: `renderer_main` and `support()`.
- No `TemporaryDirectory` / `tempfile.` use in `astrid/sdk/rendering.py` (stale `import tempfile` at line 50).
- Raw/ffmpeg/remotion: workspace = request parent; relatives via `workspace / path` (`tests/fixtures/renderer_packs/raw_command/backend.py:519-521`; `astrid/packs/rendering/backends/ffmpeg/run.py:67-71`, `704-707`; remotion `817-818`, `1223-1226`).
- Service writes `{token}-support-request.json` into that workspace (`astrid/core/rendering/service.py:1775-1777`).

### Protocol-semantic holes
Request-parent ≠ timeline-parent when:
- `timeline_path` is relative (`"timeline.json"`): `resolve().parent` is **CWD**, not the staged request dir. Fixture `support.json` is relative (`tests/fixtures/renderer_packs/raw_command/requests/support.json:3`).
- Absolute timeline lives outside the staged invocation dir.

`renderer_main` is correct. Public `support()` only matches raw backends after the service drops a request next to the timeline.

### New defects / test gaps
- Unused `import tempfile` leftover.
- Public `support()` now writes protocol request/result files into the user’s timeline directory.
- Tests do not lock workspace: `test_renderer_main_support_round_trips_raw_fixture_request` (`tests/test_sdk_rendering.py:347`) and conformance support (`tests/core/rendering/test_conformance.py:231`) only compare report JSON. Raw `_support` never opens the timeline (`backend.py:443-501`). A TemporaryDirectory would still pass. Public `support()` tests (`486`, `520`) never check `request_path.parent`.The wheel smoke script still expects pack id `rendering`. I’ll confirm that against the new dest-derived ids and wait on the four issue reviews.**ISSUES** — do not start Batch 7.

Issues 2 and 4 are closed enough. Issues 1 and 3 are not. The wheel golden path the host called green is broken on this commit.

### Remaining

**1. T6.5 / T6.6 — dest-derived pack id still does not guarantee an installable `create` dest; wheel smoke is stale and fails**

The claimed path works when the dest folder is already a lowercase pack id: `create wave acme-wave` writes `id: acme-wave` / `acme-wave.wave`, and dest `rendering` is rejected (`scaffold.py:209-222`, `272-279`).

That invariant is not actually held:

- `_pack_id_from_dest` does `dest.name.strip().lower()` (`scaffold.py:209`). Loader and install compare case-sensitively (`loader.py:117-118`, `install_local.py:150-156`). Dest `Acme-Wave` writes `id: acme-wave` into folder `Acme-Wave` — not loadable, not installable. Confirmed: `mixed_folder Acme-Wave pack_id acme-wave name_eq False`.
- CLI dest still defaults to `.` (`cli.py:52-56`). In this worktree that is `Astrid-oracle` → `id: astrid-oracle` in folder `Astrid-oracle`. Same failure. `--id` cannot fix it (prefix must match dest).
- Collision error says “or pass `--id <pack>.<name>`” (`scaffold.py:220`). That path is then rejected by the prefix check. `--id` help still says `default: rendering.<name>` (`cli.py:62`).

T6.6 wheel acceptance is still the old contract and is now wrong:

```197:221:scripts/smoke_wheel_install.sh
RENDERER_ID = "rendering.wave"
PACK_ID = "rendering"
...
dest = create_renderer_scaffold("wave", work / "scaffold-wave")
...
assert pack["id"] == PACK_ID
...
installed_copy = packs_path / PACK_ID
shutil.copytree(dest, installed_copy)
```

Live create into `scaffold-wave` writes `pack_id=scaffold-wave`, `renderer_id=scaffold-wave.wave`. The `id == "rendering"` assert fails. The script still copytrees into a folder named `rendering`. It was not in the incremental diff. Host claim that the wheel golden path was green is false on `4df08da2`.

Pytest dest is now `wave/` (good). Trusted eligibility is still a hand-written `InstallRecord` (`test_scaffold_install.py:93-128`), not `install_local` / `astrid packs install`.

**2. T6.2 — success rewrite still does not preserve the backend result file**

Transport **appends** captured streams onto `parsed.logs` (`transport.py:750-761`). `_backend_render` then does `replace(validated, logs=[])` (`rendering.py:304-305`). The comment says “strip the injected portion”; the code wipes every log.

Raw backends may emit authored `logs` (contract allows it). Those survive on the raw file and disappear on the SDK `--result` file. Fixture backends happen to write `[]`, so current tests stay green. That is the same class of wire mismatch as before, inverted.

### Closed (do not rework)

- **Support workspace.** `renderer_main` passes `request_path.parent` (`rendering.py:146-154`). `TemporaryDirectory` fallback is gone; `_support_report` requires a workspace (`504-505`). Public `support()` uses the timeline parent because there is no request file — acceptable for that API.
- **`RenderContext.run` timeout/interrupt hang.** `start_new_session=True` + `_kill_process_group` (SIGKILL + 5s communicate) on timeout and `KeyboardInterrupt` (`939`, `959`, `971`, `1002-1028`). That was the hang. `cleanup()` still `kill()`s only the direct child (`1235`); leftover grandchildren can orphan, but communicate is bounded. Not the original defect.

Rework only this batch. Minimum bar: dest name is used as pack id **without case-folding** (reject dest names that are not already a valid pack id); `scripts/smoke_wheel_install.sh` scaffolds/installs that dest (not `rendering`); success rewrite strips only the transport-appended suffix, not backend-authored `logs`.
