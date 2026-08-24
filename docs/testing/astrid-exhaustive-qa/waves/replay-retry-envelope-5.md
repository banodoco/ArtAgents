# Replay retry envelope 5

**Date:** 2026-08-23  
**Verdict:** PASS  
**Mode:** Fresh black-box LIVE UX replay; public Astrid CLI/SDK only. No source, test, git, or prior-QA inspection.

## Scenario

- Disposable projects root: `/tmp/astrid-replay5.MxGWJX` (removed after the replay).
- Project: `replay5` (`f5759ba4-e178-5ca0-a5b8-ec2c7abdff52`).
- Capability: `media.clip_extract` (`kind=executor`).
- Input path: `/tmp/astrid-replay5.MxGWJX/source.mp4`.
- The first SDK invocation used the absent path and deterministically failed with executor return code 2. It admitted run `3585ac4fde32162c0956b9ac88`, task `2d255bc1b6d56f5cf882782363`, and attempt 1 `01m0qz6j888yetajzq2yh51gc7`.
- A valid one-second MP4 was then created at the exact same path.

## Retry mutation envelope

Command: `python3 -m astrid tasks retry 2d255bc1b6d56f5cf882782363 --project replay5 --idempotency-key replay5-retry-key --json`

The successful response had attempt 2 `01m0qz6x0wfg2jjg8f2zcye8br`, with `attempt_no=2`, `status=succeeded`, and `finished_at=2026-08-23T18:47:59.813606Z`. The task kept the same ID and run ID, was `succeeded`, and had the same `finished_at`. The parent run kept ID `3585ac4fde32162c0956b9ac88`, was `succeeded`, and had the same `finished_at`. The populated `progress` and `result` objects both reported `succeeded` with `total_children=1`, `succeeded=1`, and `failed=cancelled=0`.

The receipt result repeated the same terminal attempt/task/run/progress/result state and did not contradict the mutation data. The mutation’s task `event_head_seq` was 11.

## Idempotency and attempt count

- Repeating the exact idempotency key produced byte-identical JSON responses: same receipt ID `222655fadc204450b93239d56f825a4c`, event ID `7426e844a0be4a85aa27406c2f808f65`, project sequence `[7, 7]`, and logical result.
- No new dispatch occurred. The public task event stream remained seven events: created, claimed, started, failed, retried, started, completed.
- The stream contained exactly two attempt IDs: `01m0qz6j888yetajzq2yh51gc7` and `01m0qz6x0wfg2jjg8f2zcye8br`; there was no attempt 3.

## Public artifact verification

Public `media list`, `media show`, and `media verify --realm managed_local` confirmed the retry output:

- Media ID: `01m0qz6xj8014k0s2s1embp9j4`.
- `media_kind=video`, `mime_type=video/mp4`, `byte_size=261`, and probe `is_empty=false`.
- Exactly two managed-local media rows existed (the clip plus its result manifest).
- The clip’s managed locator was under `.astrid/media/sha256/...`; verification returned `ok=true` with content hash `a555701da6bea5183cac40ea6f1b45d6fe182db4efc0cfca10ebab60fcdce498`.

**Result:** PASS — retry recovery, terminal response truth, exact-key idempotency, no extra attempt, and managed artifact verification all held in a fresh live replay.
