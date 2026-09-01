# Cloud execution custody — canonical pack beta

The user moved execution from the laptop to the Hetzner Megaplan Cloud
agentbox on 2026-08-31. Product scope, source base, model routing, acceptance
criteria, branch, and push authorization remain unchanged.

## Venue

- Host: `root@159.69.51.216` (`arnold-agentbox-01`)
- Host workspace root: `/opt/megaplan-cloud/workspace`
- Container workspace root: `/workspace`
- Container: `astrid-canonical-pack-beta-exec-20260831-a1`
- Workspace: `/workspace/astrid-canonical-pack-beta-20260831-a1`
- Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
- Branch: `megado/canonical-pack-beta`
- Base SHA: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
- Orchestrator tmux session:
  `astrid-canonical-pack-beta-20260831-a1-orchestrator`
- Orchestrator state: repository `.oracle/status.md`
- Run log:
  `/workspace/astrid-canonical-pack-beta-20260831-a1/orchestrator-run.log`

## OMP Codex authentication

- Private Docker network: `agentbox-control`.
- Credential service: `agentbox-omp-auth-broker` at
  `http://agentbox-omp-auth-broker:9000`, pinned to OMP `17.4.0`, persistent
  under `/opt/megaplan-cloud/workspace/ops/omp-auth-broker`, restart policy
  `unless-stopped`, with no published host port.
- A credential-free canary container reached the broker and returned exact
  `BROKER_LUNA_OK` and `BROKER_SOL_OK` responses through
  `openai-codex/gpt-5.6-luna` and `openai-codex/gpt-5.6-sol`; the broker also
  survived a restart before Astrid was configured against it.
- This project container is attached to `agentbox-control` and its OMP config
  points to the broker. The Sol process already alive at cutover retains its
  startup configuration; subsequent OMP processes use the broker.
- Broker tokens and OAuth material never enter this repository, the project
  ledger, receipts, or logs. New project containers receive broker URL/token
  configuration rather than copied Codex auth or OMP credential databases.

## Shared project ledger

- Authority: existing AgentBox durable operations store at
  `/opt/megaplan-cloud/workspace/ops/operation_runs.json` (container
  `/workspace/ops/operation_runs.json`).
- Operation ID: `astrid-canonical-pack-beta-20260831-a1`.
- Updates use `FileBackedDurableOpsStore` through `agentbox.operations`, with
  `expected_lock_version` optimistic concurrency. Operation events and typed
  resources remain in the same store.
- Operation-specific evidence remains under
  `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/`.
- A human-readable machine project view may be generated from this store, but
  it is a report-only projection and never a second authority.
- Arbitrary metadata records source SHA/ref, transfer digests, workspace,
  container/session, North Star digest, model routing, batch/checkpoint,
  receipts/evidence, next action, and validation state. Secrets are prohibited.

## Protected concurrent work

Never mutate, stop, restart, reset, or reuse these existing containers:

- `vibecomfy-100leg-luna-20260831-a1`
- `reigh-phase-a-exec`
- `goalmd-exec`
- `vibecomfy-exec-spine`
- `megaplan-cloud-agent-resident-only`
- `omp-migration-run`
- `megaplan-cloud-agent-critique-ledger-v3`

Never mutate shared `/workspace/arnold` or
`/workspace/omp-replaces-hermes/Arnold`.

## Launch policy

Use the canonical Megado agentbox recipe in
`/opt/megaplan-cloud/workspace/AGENTBOX-LAUNCH.md`: isolated container,
receipt-producing subagent wrapper, smoke-tested Luna and Sol routes,
cloud-resident Sol owner that dispatches bounded normal work to Luna,
repository-side checkpoint state, and a
supervisor that relaunches only incomplete work. This is deliberately not a
Megaplan chain; the frozen Megado B1–B5 state machine and oracle gates remain
the execution authority.
