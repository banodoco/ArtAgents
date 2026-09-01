# E0 cloud execution preflight

Recorded: `2026-08-31T12:00:51Z`

Operation: `astrid-canonical-pack-beta-20260831-a1`

## E0.3 — venue and custody

Result: **PASS**.

- Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
- tmux session: `astrid-canonical-pack-beta-20260831-a1-orchestrator`
- container hostname: `2af3818e94aa`
- branch: `megado/canonical-pack-beta`
- exact HEAD/base: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
- remote: `https://github.com/peteromallet/Astrid.git`
- North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`
- git bundle SHA-256: `ab229d03e365933ba1bd14a0a77c775e586eac261898925eaa1250d17d8aee0e`
- complete `.oracle` overlay SHA-256: `4783ee3ee2a928c76bd08e748507479104a703d8b090e4f31d658b12a31fe544`
- sorted overlay file-manifest SHA-256: `4c6a50bd68da1b1cade1495c1ab0559e6682bd20b79bbb0b2d224f30d82b6dc6`
- overlay file count: 755
- bundle size: 189,733,856 bytes
- overlay size: 11,849,840 bytes
- `git bundle verify`: PASS; complete history and exact branch ref present.
- `git diff --name-only 7ac50c12... -- . ':(exclude).oracle'`: no output. Product diff is zero.
- `git status --short --branch`: imported `.oracle` overlay only; zero non-`.oracle` paths.
- Durable AgentBox operation exists in `/workspace/ops/operation_runs.json`, is state `running`, and is updated only through `/workspace/ops/project-ledger` with optimistic lock versions.

Transfer provenance and the archive's externally stored digest are also recorded in `.oracle/evidence/cloud-custody.md`.

Protected concurrent work remains outside this workspace and was not read, mutated, stopped, restarted, reset, or reused. The deny-list is frozen in `.oracle/cloud-run.md`: seven named pre-existing containers plus `/workspace/arnold` and `/workspace/omp-replaces-hermes/Arnold`. All commands in this preflight used only the repository and operation paths above, `/tmp`, GitHub `origin` for the authorized dry-run, and installed tool locations.

## E0.4 — tooling, routes, push, dependencies, capacity, baseline

Result: **PASS**.

Toolchain:

```text
Python 3.11.11
git version 2.34.1
omp/17.4.0
pip 26.2 (Python 3.11)
```

`python3 -m pip install -e '.[dev]'` completed successfully from this exact checkout. It resolved the pinned `sisypy` revision `dfb3fa3`, rebuilt the editable Astrid package, and installed `astrid-0.1.0`. `python3 -m pip check` returned `No broken requirements found`; imports of `astrid`, `pytest`, `yaml`, and `jsonschema` succeeded. Installed validation tooling includes pytest 9.0.2 and build 1.6.0.

Exact model routes were exercised through `/root/.codex/skills/subagent-launcher/launch_hermes_agent.py` using North-Star-complete briefs:

- `codex:gpt-5.6-luna` resolved to `openai-codex/gpt-5.6-luna`, returned `LUNA_OK`, exit 0: `.oracle/receipts/e0-luna-route.txt`.
- independent `codex:gpt-5.6-sol` resolved to `openai-codex/gpt-5.6-sol`, returned `SOL_OK`, exit 0: `.oracle/receipts/e0-sol-route.txt`.

Authorized push dry-run:

```text
git push --dry-run origin HEAD:refs/heads/megado/canonical-pack-beta
To https://github.com/peteromallet/Astrid.git
 * [new branch] HEAD -> megado/canonical-pack-beta
```

Capacity:

```text
16 CPUs
30 GiB RAM total; 26 GiB available
/workspace: 601 GiB total; 233 GiB available
/tmp overlay: 601 GiB total; 233 GiB available
```

Inherited focused baseline was delegated once to exact Luna against exact HEAD. Receipt: `.oracle/receipts/e0-baseline-luna.txt`.

```text
python3 -m pytest -q \
  tests/v10/test_registry.py \
  tests/v10/test_catalog_migrations.py \
  tests/v10/test_standard_application.py \
  tests/v10/test_doctor.py \
  tests/v10/test_backup_restore.py \
  tests/v10/test_reference_repository.py \
  tests/sdk/test_references.py

179 passed, 0 failed in 14.74s pytest time; exit 0
```

Final post-install custody check again showed exact HEAD and zero product diff outside `.oracle`.
