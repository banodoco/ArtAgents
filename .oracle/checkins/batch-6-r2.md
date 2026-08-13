I'll review the Batch 6 rework as a read-only checkpoint: prior verdict, incremental diff, and whether both host-fixed issues actually hold.I'll load the prior verdict, Batch 6 acceptance criteria, and the incremental rework so I can judge the two host-fixed issues against the actual diff.Prior verdict is two remaining issues. Next I’ll read the incremental rework and verify each fix against the current source, not the commit message.The rework is small. I’ll verify dest-id rules, the smoke path, and the log-strip against current source and tests.Next I’ll read the tests and the transport/install paths to confirm the two claimed fixes actually hold.Dest-id and log-strip look right in the diff. I’ll confirm install layout, leftover `rendering.<name>` docs, and whether dest/log tests actually lock the new contracts.Pack-id regexes may not match. Checking the loader’s actual identifier rule against the scaffold.The scaffold regex is looser than the pack schema. I’ll confirm `acme-wave` actually fails validate/install, and that the log-strip still matches transport.**ISSUES** — do not start Batch 7.

Issue 2 (T6.2 log strip) is closed. Issue 1 is not: dest is still not a guaranteed installable pack id.

### Remaining

**1. T6.5 / T6.6 — dest-derived pack id still uses the wrong alphabet; the documented dest is not installable**

Case-folding is gone, `rendering` is rejected, cwd default is validated, wheel smoke uses dest `wave/`, and trusted-install tests call real `install_pack`. That is not enough.

`_pack_id_from_dest` accepts `^[a-z0-9][a-z0-9_-]*$` (`scaffold.py:32,212-220`). A real pack id is `^[a-z][a-z0-9_]*$` — letter start, no hyphens — in the schema (`astrid/core/pack/schemas/v1/_defs.json`), loader (`_common.py:61,144-146`), and `packs new` (`cli_basic.py:31-32`). Live check on this commit:

| dest | create | `validate_pack` | `load_pack_manifest` |
|---|---|---|---|
| `wave` | ok | ok | ok |
| `acme_wave` | ok | ok | ok |
| `Acme-Wave` | rejected | — | — |
| `rendering` | rejected | — | — |
| **`acme-wave`** | **ok** | **`id` does not match required pattern** | **`pack.id` must match `^[a-z][a-z0-9_]*$`** |
| `1wave` | ok | fail | fail |
| `cli-wave` | ok | fail | fail |

CLI help and the rejection message still teach `create wave acme-wave` (`cli.py:56-58`, `scaffold.py:217-219`). That dest writes `id: acme-wave` into folder `acme-wave`, then static validate and `astrid packs install` both fail. The host “probe” that accepted `acme-wave` only checked create, not installability.

Golden-path tests stay green because they use dest `wave`. The CLI route test writes `cli-wave` / `dispatch-wave` and only asserts files exist (`test_scaffold.py:181-188`). There is still no test that dest is a *pack* id.

`create_renderer_scaffold` still documents default `rendering.<name>` (`scaffold.py:257`).

### Closed (do not rework)

- **T6.2 success rewrite.** Transport appends `stdout:\n…` / `stderr:\n…` (`transport.py:751-761`). `_backend_render` pops only that trailing suffix (`rendering.py:305-313`) and writes the DTO (`rendering.py:165,187-191`). Backend-authored logs survive. No new test locks a noisy child plus authored logs; that is not this defect.

Rework only this batch. Minimum bar: dest must already be a valid pack id per `^[a-z][a-z0-9_]*$` (reuse the pack-system pattern, do not invent a third one); help/examples use a legal dest such as `acme_wave`; `validate_pack` and `install_pack` succeed on the directory `create` just wrote.
