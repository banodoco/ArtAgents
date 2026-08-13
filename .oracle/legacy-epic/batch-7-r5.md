I'll verify the six frozen Batch 7 contract items against the incremental diff and the current tree, then give a binary verdict.Collecting the checkpoint artifacts, HEAD/tag state, and the incremental diff so I can verify each frozen contract item independently.HEAD matches `C8-batch7-done`. Next I’ll read the r4 leftovers and the incremental code, then verify each of the six contract items.The r4 leftovers are the six items claimed fixed. I’ll read the frozen criteria and current handlers, then independently check each one.I'll verify both Batch 7 contract items againstI'll verify the frozen claims the three Batch 7 claims, starting against the CLI with the allowlist, inspect, contract evidenceI'll verify tests, and tasklist, the Batch 7 host, and the matching then-path redaction contract by tests. reading the rewrite run the specified pytest commands/redact helpers and their tests, then run. the targeted pytest filter.I'll read the critical handlers and contract tests while the verifiers run, so the verdict is based on the code, not the host summary.Next I’ll read the replay/smoke handlers, interrupt path, and the frozen contract tests.The allowlist includes `renderers`/`replay`, but the Sprint 1 gate test still omits them — I'll read the matcher and run the live CLI next.The `file://` lookbehind and log vs metadata paths look like the likely holes; I'll read `write_replay_bundle` and probe those cases next.Running isolated live CLI commands and checking whether inspect ever surfaces real registry conflicts.Conflicts are hardcoded empty, and `list` stays ids-only. I'll run the live unbound gate and the contract tests next.**PASS** (with residual nits, not a contract fail)

Item 6 holds for the stated helpers: whole-string abs paths in `_rewrite_path_string`, and in-text abs paths in `_redact_metadata`. Captured-input rewrite is still first. `file://` / logs / spaces are leftover holes, not a broken rewrite.

### 1. Logic (quoted)

`/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/replay.py`

```60:60:astrid/core/rendering/replay.py
_HOST_PATH_PLACEHOLDER = "<host-path>"
```

`_rewrite_path_string` (329–353): non-abs unchanged; **captured role first** → `inputs/<sha256>`; self/cycle → placeholder; then **any remaining abs path** → `<host-path>` (the repo/home branch is now dead code before the same return).

`_redact_metadata` (451–472): `_redact_log` first, then

`(?<![A-Za-z0-9+.-:/])/[\w./~-]+(?:/[\w./~-]+)*` → `<host-path>`.

Lookbehind is the URL carve-out (`:` / `/` / alnum so `https://host/path` is not eaten).

`_redact_log` (`transport.py` 614–631) only secrets/auth/query — **not** host paths. Bundle logs (141–144) use `_redact_log` only.

`_rewrite_host_paths` docstring (284–285) still says other abs paths are “left as-is”; **code disagrees**. Nit only.

### 2. Tests

`test_absolute_host_paths_including_tmp_are_redacted` at `tests/core/rendering/test_replay_bundle.py:751–774` writes metadata `/private/var/folders/.../tmpXXXX/...` and `/tmp/scratch/theme.json`, asserts those tokens gone and `host-path` present; `"not a path"` kept. Related: `:369`, `:410`, `:518`, `:592`.

**Pytest was not executed** (this verifier has no shell). Statically the new test would pass the regex.

### 3–5. Adversarial

| Input | `_redact_metadata` | `_rewrite_path_string` |
|---|---|---|
| `/tmp/foo`, `/var/folders/...`, `/private/var/folders/...` | redacted | redacted (`isabs`) |
| `wrote /tmp/foo then done` | `wrote <host-path> then done` | **unchanged** (not whole-string abs) |
| `https://example.com/path?token=SECRET` | scheme+host+path kept; token → `[redacted]` via `_redact_log` | unchanged (`isabs` false) |
| `file:///tmp/secret.mp4` | **leaks** (`/` after `:`/`/`) | `isabs` false → **leaks** |
| `inputs/abc` | kept | kept |
| `/tmp` | redacted | redacted |
| `/tmp/foo bar` | only `/tmp/foo` | whole string if `isabs` |

**Rewrite vs localize:** `role_by_resolved` runs first (341–344). “Always redact abs” does **not** break captured-input refs.

### Residual nits (not contract FAIL)

The claim itself keeps URL scheme+host. That leaves:

- `file:///tmp/...` and `cwd:/tmp/...` (colon lookbehind)
- logs never host-redacted
- spaces / `~` not `/`
- JSON **in-prose** paths only hit `_redact_metadata`, not input rewrite
- new test does not cover `_rewrite_path_string` + `/tmp` or `file://`## Item 1 — renderers + replay unbound
**PASS** (implementation). **T7.6 hole:** allowlist lock test is stale.

**Allowlist has the tuples** (`/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/gateway/__init__.py:149-172`):

```149:172:astrid/core/gateway/__init__.py
SPRINT1_UNBOUND_ALLOWLIST_CONTRACT: tuple[tuple[str, ...], ...] = (
    ...
    ("packs",),
    ("renderers",),
    ("replay",),
    ("test",),
```

**Prefix match unbinds every subverb.** One-token prefixes match `raw[:1]`:

```412:415:astrid/core/gateway/__init__.py
    for allowed in _SPRINT1_UNBOUND_ALLOWLIST:
        if tuple(raw[: len(allowed)]) == allowed:
            return True
    return False
```

So `("renderers",)` covers `create|list|inspect|validate|smoke|support|replay` (and bare `renderers`). `("replay",)` covers top-level `astrid replay …`. Dispatch: `dispatch.py:454-455`, `_dispatch_replay` prepends `"replay"` (`321-325`).

Bare `astrid renderers` is help + exit 2, not a session gate (`cli.py:58-61`). Bare `astrid replay` is argparse usage (required `bundle_dir`, `cli.py:237-240`), not `"no session bound"`.

Gated verbs still fail the session check (`gateway/__init__.py:266-304`; `tests/session/test_cli_gate.py:92-118` — `executors list`, `elements list`, `runs ls`).

**Tests:**
- Session-independence in `test_cli_contract.py:345-384` only proves cwd-identical JSON, **not** the gateway session gate.
- Lock table **omits** `renderers`/`replay` (`test_cli_gate.py:29-50`) and asserts equality (`172-173`). Full `pytest` **will fail** here. That is a T7.6 blocker, not a nit.

**Live CLI:** this verifier has no shell. Expected (from code): no `"no session bound"` for `renderers *` / `replay`; usage/help for missing args; built-in inspect id is `rendering.ffmpeg`, not `wave.wave`.

---

## Item 2 — inspect precedence / revision / aliases / override / conflicts
**FAIL** vs frozen Batch 7 line 150 (“report … aliases, **conflicts**, and **overrides**”).

`_resolve_inspect_evidence` / `_cmd_inspect`: `cli.py:390-541`.

`resolve_evidence` keys (`registry.py:321-340`): `requested_id`, `canonical_id`, `resolved_id`, `source_kind`, `pack_id`, `pack_root`, `manifest_path`, `manifest_digest`, `alias_chain`, `override`, `priority`, `priority_index`, `eligible`, `execution_eligible`, `eligibility_reason`, `trust_method`, `eligibility`, `resolution_error`. **No `conflicts`.** Real conflicts live on `CapabilityRegistry.conflicts()` (`registry/base.py:168-185`; proven in `test_registry.py:235-257`, `test_registry_matrix.py:282-325`). Inspect never calls it.

JSON hardcodes a stub (`cli.py:486`): `"conflicts": []`. That **hides** shadowed candidates.

**Frozen JSON key set** (`test_cli_contract.py:106-131`):  
`id, kind, name, version, protocol_version, command, operations, required_binaries, required_permissions, timeout_seconds, description, capabilities, source_pack, source_kind, manifest_path, precedence, active_revision, alias_chain, override, conflicts, overrides, eligibility, eligibility_reason, trust_method`.

**`alias_chain` vs “aliases”:** not a FAIL. JSON is locked as `alias_chain`; plain prints `aliases:` (`cli.py:535`).

**Plain does not emit `conflicts` or `overrides`** (stops after `override` / eligibility, `cli## Item.py:536-541`). Claim “both JSON 3 — replay `--json` — **PASS** and plain” is false (static;.

**`resolve pytest unrun_evidence` throw)

**Parser is / emit a hole.** `cli.py.** `replay`:409-412` has `--json` at [` `except Exceptionastrid: return None` →/core/rendering/cli.py:261- `alias_chain=[]`,265`](/Users/peteromalley/ `override=None`, `Documents/reigh-workspaceoverrides=[]` (`478/Astrid-oracle/-491`). Onlyastrid/core/rendering `execution_ineligible`/cli.py). Success is recovered path dumps one object via inside `resolve_evidence` `_emit_json` → (`306 stdout (`1022-103-3196`). Doc`); other registrystring: “exactly ONE errors are JSON swallowed object by… never inspect.

` a universal envelope” (`22list` only emits-25`).

**Frozen keys `ids**` (`test_replay_json_shape (`cli.py:357-_is_stable`, `365`) — also misses782 frozen list-792+`):

`verbinspect reporting,`, `renderer_id`, but outside `manifest_digest`, ` this inspectmanifest_digest_match`,-key claim `request_digest`, `.

---

## Oracle blockersrequest_digest_verified`, `replay_verb`, `
1. `drift`, `output`

Notest_unbound_gate_ `usesok_`the/`_statusfrozen`/`data`/`result`_allowlist_table`/`success`/`error` vs updated (`_assert_no contract_envelope`, `50 (T7.6).-51`,
2. Inspect `conflicts `793`).

: []` stub**Other verbs still vs frozen have `--json`:** “report conflicts” create `113`, (registry already list `132`, inspect `156`, validate `171`, has real conflicts smoke `202`, support `).
3. Silent drop226`.

**Adversarial:** of alias/override when ` replay *resolve_evidence` raises.

failures* (`859Live inspect `---934`, `978json` keys: not-1003`) print executed here; text on stderr and emit locked **no** JSON set even with `--json`. Success is ` shape is tighttest_cli_contract.py; error `--json`:106-131`. is not.

**Live test:** no shell in this verifier — **not executed**:
`python3 -m pytest -q tests/core/rendering/test_cli_contract.py::test_replay_json_shape_is_stable -q`

---

## Item 4 — exit 2 / 1 / 130 — **FAIL**

Constants `44-46`. `main()` `55-73`: no-handler `return 2` (`61`); `KeyboardInterrupt` → `_handle_interrupt` (`64-65`). Only other `sys.exit` is `SystemExit(main())` (`1049-1050`).

**KeyboardInterrupt.** `_handle_interrupt` `808-827`: if no `renderer_error`/`error`, **re-raises** (`816-817`). Bare Ctrl-C does **not** exit 130. Backend-attached interrupt prints one object/line and returns `_EXIT_INTERRUPT` (`825-827`). Matches “with a backend error”; T7.2/plan M2-04 still said re-raise.

**Domain → 2:** create JSON conflict `339`; inspect unknown `442`; validate missing/invalid `568/581/587`; smoke unknown/ineligible `621/668`; replay missing bundle / unresolvable id / drift / missing request / tamper `860/881/913/920/934`.

**Bug → 1:** support `RendererException` `792`; replay transport fail `987`; no output `1003`.

### Remaining return-1 domain paths (**critical**)

`_cmd_support` maps **every** `RendererException` to `_EXIT_BUG` (`789-792`), including:

- **unknown id** (`test_support_on_unknown_backend_emits_frozen_renderer_error`)
- **declining/unsupported** (`test_support_on_declining_backend_emits_frozen_renderer_error`)

SDK maps unknown ids to `unsupported` ([`sdk/rendering.py:619-634`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/sdk/rendering.py)). `RendererException.degraded` is only `kind == "internal"` ([`errors.py:28`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/errors.py)). **Plain** support re-raises → `render_astrid_error` → **2** ([`errors.py:262`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/contracts/errors.py)). **JSON** support unknown/decline → **1**. Same domain error, two codes.

No other `return 1`. Smoke backend errors are uncaught in `cli.main` (not forced to 1).

**T7.2 vs batch 153.** Batch [`tasklist.md:153`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/tasklist.md) is the governing 2/1/130 contract. T7.2 (“no universal envelope or independent exit-code layer”) is **not** a new module/envelope; three aliases live in `cli.py`. Stale leftover: contract file still says “no independent exit-code taxonomy” (`19-20`) and `test_exit_code_contract_is_only_zero_vs_nonzero` only checks 0 vs ≠0 (`684-720`).

**Live test unrun:**
`python3 -m pytest -q tests/core/rendering/test_cli_contract.py -k "130 or domain or exit or interrupt or replay_json" -q`

---

## Item 5 — `--keep-workdir` — **PASS** (impl) / **no tests**

Flag `256-260`. On flag, copies to `bundle_dir.parent / f"{bundle_dir.name}.replay-workdir"` (`1016-1020`) **inside** `TemporaryDirectory` (`936-1020`) so default still deletes. No Thread/TTL/daemon in this module.

**No tests** under `tests/` for `keep-workdir` / `replay-workdir`.

**Smoke `mkdtemp`:** default out parent `678-679` is leaked. **Out of this item.** Frozen `:155` is generic “disposable workdirs,” but `--keep-workdir` is replay-only; smoke workspace is already `TemporaryDirectory` (`684`).The allowlist lock test is a new red. I'll confirm the support exit-code mismatch before writing the verdict.**ISSUES** — not `PASS`. Do not start Phase 6.

HEAD is `a0ed75df` / `C8-batch7-done`. The six leftover surfaces are present. Three holes remain.

## What holds

Live, no session: `python3 -m astrid renderers list` → exit 0 (`rendering.ffmpeg` …). `astrid replay` → argparse usage, not `no session bound`. `timelines ls` still exits 2 with `no session bound`.

Inspect `--json` emits `precedence`, `active_revision`, `alias_chain`, `override`, `conflicts`, `overrides`. Replay `--json` success shape is locked and the contract test passed. Unknown inspect / missing replay bundle exit 2. Interrupt test exits 130. `--keep-workdir` copies to `<bundle>.replay-workdir`. `/tmp` and `/var/folders` in metadata are redacted.

`tests/core/rendering` CLI + contract + replay + the new redaction test: 57 passed.

## Issues

**1. New CI red: Sprint 1 allowlist lock was not updated.**

`SPRINT1_UNBOUND_ALLOWLIST_CONTRACT` gained `("renderers",)` and `("replay",)` (`astrid/core/gateway/__init__.py:167-168`). The lock was not:

```29:50:tests/session/test_cli_gate.py
EXPECTED_SPRINT1_UNBOUND_ALLOWLIST = (
    ...
    ("packs",),
    ("test",),
    ("doctor",),
    ("serve",),
)
```

Reproduced here:

`pytest tests/session/test_cli_gate.py::test_unbound_gate_uses_the_frozen_allowlist_table` → **FAILED** (`('renderers',) != ('test',)`). This is from this delta. `make ci` is no longer “schema_contract only.”

**2. Inspect does not report conflicts.**

`resolve_evidence` has no `conflicts` key (`registry.py:321-340`). Real conflicts are `registry.conflicts()`. Inspect hardcodes `"conflicts": []` (`cli.py:486`). Plain mode never prints `conflicts` or `overrides`. Frozen: inspect reports aliases, conflicts, and overrides (`tasklist.md:150`).

**3. `support --json` maps expected errors to exit 1.**

Unknown renderer, live:

| Mode | Exit |
|---|---|
| `support no.such.renderer --json` | **1** |
| `support no.such.renderer` (plain) | **2** |

Cause: `_cmd_support` returns `_EXIT_BUG` for every `RendererException` (`cli.py:789-792`). Frozen: expected errors exit 2 (`tasklist.md:153`).

## How to close

1. Add `("renderers",)` and `("replay",)` to `EXPECTED_SPRINT1_UNBOUND_ALLOWLIST`.
2. Wire inspect `conflicts` from `registry.conflicts()` (and print them in plain).
3. Map non-`internal` support failures to `_EXIT_DOMAIN` (2), not 1.

Then re-run `test_cli_gate.py::test_unbound_gate_uses_the_frozen_allowlist_table` plus the CLI contract suite. Do not open Phase 6 on another verification.md-only commit.
