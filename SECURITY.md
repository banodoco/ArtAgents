# Security Model — v1 (Disclosure-Only)

This document describes Astrid v1's security posture for third-party and
installed packs. It is a disclosure-and-trust model, not a sandbox or
enforcement model. If you are evaluating whether a pack you found online
is safe to install, start here.

> **Platform contract**: The disclosure-only trust block (sandbox: none,
> runs_with_user_process_permissions: true, permission_enforcement:
> disclosure_only) is a first-class part of the normative v1 platform
> contract defined in [docs/contracts/platform-contract.md](docs/contracts/platform-contract.md).
> That document is the source of truth for the v1 trust invariants,
> pack-level permission contract, trust-on-install rules, and the
> SemVer/deprecation guarantees that protect these security boundaries.
> When this document and the platform contract differ, the platform
> contract wins.

## v1 No-Sandbox Promise

Astrid v1 does **not** sandbox installed packs. Every pack runs with your
user's full process permissions — same filesystem access, same network
access, same environment variables. There is no container, no virtual
machine, no seccomp filter, and no capability drop.

The v1 trust block is fixed:

```
sandbox:                            none
runs_with_user_process_permissions: true
permission_enforcement:             disclosure_only
```

This is a v1 invariant. It will not change in a v1.x release. When Astrid
adds sandboxing in a future major version, the trust block will be the
first thing to change.

## Permission Declarations Are Disclosure Metadata

Pack manifests may declare a `permissions` array. Each permission object
requires an `id` (one of six approved values) and a human-written `reason`.
Optional `access` and `services` fields add context.

The six permission IDs are:

| Permission | Meaning |
|---|---|
| `project_files` | Reads or writes files in the project directory |
| `network` | Makes outbound network connections (HTTP, TCP, etc.) |
| `subprocess` | Spawns child processes |
| `environment` | Reads environment variables (including secrets) |
| `accelerator` | Uses GPU or specialized hardware |
| `external_services` | Calls paid or third-party cloud services |

A `reason` is required and must be non-blank. It should explain **why**
the pack needs the permission in terms a user can evaluate. For example:

```yaml
permissions:
  - id: network
    reason: Calls OpenAI and fal.ai APIs for AI generation
    services:
      - api.openai.com
      - api.fal.ai
  - id: environment
    reason: Reads OPENAI_API_KEY and FAL_KEY from environment
  - id: subprocess
    reason: Runs ffmpeg for video processing
```

These declarations are **not enforced**. Astrid v1 does not:

- Block network access for packs that did not declare `network`
- Restrict filesystem access for packs that did not declare `project_files`
- Hide environment variables from packs that did not declare `environment`
- Prevent subprocess spawning for packs that did not declare `subprocess`

The declarations exist so you can make an informed trust decision before
executing a source pack. They appear in pack inspection and discovery output.

## Secrets Are Not Permissions

Secrets (API keys, tokens, passwords) are declared through a separate
`secrets` block on executor and orchestrator manifests. The pack-level
`permissions` array declares **capability domains** (network access, file
access, subprocess spawning). The executor-level `secrets` declaration
lists **specific environment variable names** the executor reads.

A pack that reads `OPENAI_API_KEY` should declare both:

1. `permissions: [{id: environment, reason: "Reads OPENAI_API_KEY for API calls"}]`
2. `secrets: [{name: OPENAI_API_KEY, required: true}]` on the relevant executor

The `environment` permission says "this pack reads your environment." The
`secrets` block says "specifically, it reads this variable." Both are
disclosure-only in v1 — Astrid does not intercept, filter, or audit
environment reads at runtime.

## Third-Party Pack Threat Model

When you execute a third-party source pack (from a Git checkout or a local
directory), you are giving its code the same privileges as your user account.
The threat model is:

- **The pack can read any file you can read**, including configuration,
  SSH keys, browser data, and project files outside the current project.
- **The pack can make any network connection you can make**, to any host,
  on any port.
- **The pack can spawn any process you can spawn**, including shell
  commands, installers, and other programs.
- **The pack can read any environment variable in your process tree**,
  including secrets the pack did not declare.
- **The pack can modify or delete files you own**, including `.git`
  history, installed packages, and system configuration files writable
  by your user.

This is the standard threat model for any `pip install`, `npm install`, or
`git clone` followed by `python run.py`. Astrid's permission declarations
make this explicit but do not reduce it.

### What Astrid v1 Does

- **Shows permission declarations** during source-pack inspection so you can
  evaluate what the pack claims to do.
- **Validates permission syntax** — unknown permission IDs, missing reasons,
  and malformed fields are rejected at validation time.
- **Runs executable capabilities through the generic host subprocess boundary.**

### What Astrid v1 Does NOT Do

- Sandbox, isolate, or jail pack processes.
- Enforce permission declarations at runtime.
- Audit actual filesystem, network, or subprocess access against declared
  permissions.
- Intercept or filter environment variable reads.
- Restrict GPU or hardware access.
- Validate that declared services (e.g., `api.openai.com`) are the only
  hosts contacted.

## Safe-Use Guidance

### Before Executing a Pack

1. **Inspect the source pack.** Review its declared permissions, entrypoints,
   secrets, and dependencies.
2. **Check the `reason` fields.** A pack that says `network` with reason
   `"Calls OpenAI API"` is specific. `"Needed for functionality"` is not.
3. **Prefer packs from sources you recognize.** Review a pinned Git checkout
   before executing it.
4. **Run packs in isolated environments** if you are evaluating untrusted
   code. A disposable VM, a dedicated user account, or a container are
   appropriate for packs from unknown sources.

## Anti-Scope Boundaries

The following are **not** what v1 permissions mean:

- **Permissions are not capability restrictions.** Declaring `network`
  does not mean "only network." A pack that declares `network` may also
  read files, spawn subprocesses, and read environment variables.
- **Permissions are not per-executor.** They are pack-level only in v1.
  Every executor and orchestrator in the pack shares the same declared
  permission set.
- **Permissions are not a sandbox configuration.** They are not consumed
  by `IsolationMetadata`, do not derive sandbox profiles, and do not
  configure executor isolation behavior.
- **Permissions are not a diff against baseline.** Declaring
  `project_files` does not mean "more file access than before." It is a
  positive declaration that the pack reads or writes project files.
- **Permissions are not validated at runtime.** A pack that declares no
  permissions runs with the same full user privileges as a pack that
  declares all six.

## SDK Discovery Contract

The `astrid.discover()` SDK surface exposes pack-level permissions through
two channels:

1. **Pack records in `discover().to_dict()["packs"]`** include full
   structured permission objects (`permissions`), compact permission id
   strings (`permission_ids`), and the v1 trust block (`trust`).
2. **Capability safety declarations** mirror pack permission IDs into
   `SafetyDeclaration.permissions` as `tuple[str, ...]` — string IDs
   only, not structured objects. This lets an agent or tool check whether
   a capability's owning pack declares, for example, `network` without
   parsing the full permission object.

```python
import astrid

inventory = astrid.discover()

# Pack-level: full structured permission objects
for pack_id, pack_data in inventory.to_dict()["packs"].items():
    print(pack_id, pack_data["permissions"], pack_data["trust"])

# Capability-level: string permission IDs only
for cap in inventory.capabilities:
    print(cap.id, cap.handle.safety.permissions)
```

`SafetyDeclaration.permissions` is always `tuple[str, ...]`. It contains
only permission ID strings, never structured objects. This is a stable
type contract — callers can safely iterate without type-narrowing on
individual permission fields.

## Reporting Security Issues

If you discover a vulnerability in an Astrid-shipped pack or in the Astrid
CLI/SDK itself, please report it privately. For third-party packs you
installed, contact the pack maintainer — Astrid's permission model is
disclosure-only, so unexpected behavior in a third-party pack is a trust
decision issue, not an Astrid vulnerability.

---

*Last updated: v1 permission system (disclosure-only trust model)*
