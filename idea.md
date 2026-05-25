# Astrid: Project / Timeline / Session / Plan Reshape

A working plan to take Astrid from where it is today to a model where:

- Every tab is a session bound to a project + timeline.
- Every meaningful action is a step in a living, editable plan.
- Every artifact, every cost, every actor is auditable after the fact.
- Execution can happen anywhere — local, remote, RunPod, an agent's head.

Sprint 0 + five reshape sprints, **~11–13 weeks honest budget for one developer**, strictly serial.

---

## Foundation

### The mental model

```
Session  (per-tab, ULID, ephemeral, resumable, never auto-expires)
  └── bound to ──▶ Project
                     ├── timelines/<ulid>/
                     │    ├── assembly.json    (the timeline = a TimelineConfig document)
                     │    ├── manifest.json    (which runs feed me, final outputs)
                     │    └── display.json     (slug, name, default flag)
                     └── runs/<ulid>/
                          ├── run.json         (timeline_id, consumes, status)
                          ├── plan.json        (cached projection of the genesis event)
                          ├── events.jsonl     (hash-chained log; genesis plan + all mutations)
                          └── steps/<step-id>/
                               ├── produces/
                               ├── iterations/NNN/
                               └── items/<id>/
```

Containers, each with one job:

- **Project** — top-level workspace.
- **Timeline** — a named, persistent target inside a project. Multiple per project. Has a list of final outputs. It *is* a `TimelineConfig` document — the same shape reigh-app renders — maintained as an edit-event log; "timeline" means exactly this one thing.
- **Run** — one execution of a plan. Belongs to a project, tagged to a timeline.
- **Step** — the unit of work inside a run. One type, with `requires_ack`, `assignee`, `produces`, optional `command` (leaf) or `children` (group).
- **Session** — per-tab binding to (project, timeline, run). Ephemeral, resumable. Multiple agents can share via read-only attach + explicit takeover.

### Current state in one paragraph

Project, run, and the step kernel (`plan.json`, `events.jsonl`, `produces/`) all exist. Timeline is **not** a container — it's just a per-run output artifact. Sessions don't exist; `<project>/active_run.json` is project-global on disk and races between tabs. The thread system competes with `active_run.json` and the implicit cwd-derived project — three "active" pointers, none canonical. SKILL.md / AGENTS.md predate the task framework and don't teach `astrid status` / `next` / `ack`. Canonical orchestrators (`builtin.hype` etc.) don't emit `plan.json`. The step model is overcomplicated (`code` vs `attested`, `AckRule` `agent` vs `actor`, separate `nested` kind, separate executor/orchestrator abstraction).

### Load-bearing decisions (apply across all sprints)

- **ULIDs are identity, slugs are aliases** for every entity (project, timeline, run, session, step). Slugs are mutable display; ULIDs never change. Old references stay valid forever.
- **Sessions are per-tab, resumable, never auto-expire.** A session lives until the user detaches. Multiple agents can attach to the same run — second one in is read-only; takeover is an explicit verb.
- **Defaults exist but never auto-attach.** Per-user default project, per-project default timeline. Both feed the suggestion in `status`. Every new tab makes an explicit choice, every time, even if there's only one option.
- **Plans are mutable, but append-only once a step is dispatched.** Steps can be added, edited, or removed by the agent or human. **Undispatched steps** can be removed (tombstone-and-skip) or edited freely. **Dispatched steps are immutable** — "editing" a dispatched step means writing a new step *version* that supersedes it for any not-yet-dispatched work; the original stays in place for audit. Each mutation is a hash-chained event in `events.jsonl`. **The initial plan is itself the genesis event of `events.jsonl`** (a `plan_initialized` event carrying the full plan), so the hash chain — and `astrid events verify` — covers the plan from byte zero, not just its later mutations. `plan.json` is a cached *projection* of that genesis event for cheap reads, never an independent authority; if it disagrees with the log, the log wins. The *effective* plan is the genesis event + replayed mutations. The cursor stores `(step_id, step_version, dispatch_event_hash)` — not an index into a replayed plan — so a mutation can never silently move the cursor onto different work.
- **Run lease epoch fences all writes — inside a real critical section.** Every run carries a `writer_epoch: int` in `runs/<ulid>/lease.json`. The fence is only valid if **epoch check + last-hash compare + event append happen atomically**. The append path takes a `flock` on `events.jsonl`, re-reads the tail to confirm the previous-hash matches what the writer started from, re-reads the lease epoch, then writes — all under the same lock. A stale writer that passes its initial epoch check but loses the race to a takeover gets rejected at append time, not silently committed. Takeover atomically increments the epoch in the same locked write that swaps `attached_session.json`. The takeover *event* is observability; the lock + CAS is the actual fence.
- **One step type at runtime.** `requires_ack: bool`, `assignee`, `produces`, `repeat`, optional `command` (leaf) or `children` (group). Collapses `code` / `attested` / `nested`; the `AckRule` `agent` / `actor` split becomes `agent` / `human` (see assignee taxonomy below).
- **At authoring time, two template kinds.** Leaf-templates (the reusable building blocks — what we used to call executors) and **plan-templates** (reusable composition units — the role the orchestrator concept used to fill). Runtime is uniform; authoring keeps the composition primitive so hype-style work doesn't degenerate into ad-hoc plan-mutation soup. The pack layout on disk stays — only the conceptual frame changes.
- **Elements are render-layer primitives, not a third work-capability kind.** `core/element/` (effects / animations / transitions — each a `component.tsx` + `element.yaml`) are the building blocks a `TimelineConfig` *references* at render time; they sit on the same axis as the timeline itself, not as a sibling of leaf-templates / plan-templates on the work axis. The executor/orchestrator → leaf/plan-template reframe is about *how work runs*; elements are about *what a timeline is made of*. They stay where they are, owned by the timeline/`TimelineConfig` domain (S2), and are migrated only insofar as the timeline format unifies. Stated explicitly so "elements" isn't mistaken for an un-migrated third capability kind — it's a deliberate scoping, not an oversight.
- **Execution is location-agnostic via three explicit adapters: `local`, `manual`, `remote-artifact`.** Each step declares its adapter; the framework never assumes local execution. The schema is uniform; the adapters are not. **`local` and `manual` ship in Sprint 3; `remote-artifact` ships in Sprint 5a alongside the hype port** — hype's RunPod renders are the actual first client, so building the adapter against a real consumer keeps it honest.
  - `local` — subprocess runs in the project root; outputs land directly in `produces/`.
  - `manual` — agent (or human) runs the work somewhere out-of-band, then either `astrid ack` (sync) or writes a completion file to inbox (async). The agent is responsible for getting outputs into `produces/`.
  - `remote-artifact` — framework knows about a remote run (RunPod, ssh job, etc.). The adapter owns dispatch / status polling / artifact fetch / checksum / failure semantics. Completion is "remote done AND artifacts pulled AND checksums match." Half-completed remote work (job succeeded, fetch failed) is an explicit retry-able state, not a silent loss. This adapter is its own small job system; treating it as equal-weight with `local`/`manual` understates its complexity.
- **Async is the default, not a special case.** Any step can be slow. The agent dispatches, optionally closes the tab, returns later, calls `astrid next` which consumes inbox and advances.
- **Anything that produces an audit-worthy artifact must be a step.** Including ad-hoc python, scripts written on the fly, one-off tool runs. Friction is `astrid plan add-step --command '...' --produces '...'` + `astrid next`. Truly ephemeral commands (ls, grep, reading a file) don't need it.
- **Final outputs are first-class and integrity-checked.** Timeline manifest has `final_outputs: [{ulid, path, kind, size, sha256, check_status, check_at, recorded_at, recorded_by, from_run}]`. The path is a pointer to wherever the file actually lives; `size` and `sha256` are captured at finalize time so the audit record stands even if the file later moves or rots. `check_status` is `ok` / `missing` / `mismatch` (recomputed on `astrid timeline show` if you ask). `kind` is free text — mp4, transcript, training-set, process-doc, anything. Multiple allowed per timeline.
- **One timeline format end-to-end: `TimelineConfig` — the exact schema reigh-app renders.** A timeline *is* a `TimelineConfig` document (`banodoco_timeline_schema` — clips, assets, tracks, transitions, themes); the event log is the *edit history* of that document, and its projection target **is** `TimelineConfig`, not a parallel shape. The thing the agent edits, the thing `assembly.json` holds, and the thing hype renders are all the *same* format — one document, transformations applied on top via the event stream. Today `core/timeline` projects into a separate `{kind, asset_id, start, duration}` clip shape that nothing converts back to `TimelineConfig` and nothing renders; that shape is **deleted**, not renamed-around. This is the single timeline decision that touches the deferred Banodoco boundary — see out-of-scope for why pulling it forward is honest, not new coupling.
- **There are three append-only logs today, not two — name the relationship before V1 ships.** Task `events.jsonl` (run/step lifecycle), timeline `assembly.jsonl` (timeline edits), and — found in verification — `audit/ledger.jsonl`, a separate `astrid/audit/` subsystem logging `asset.created`/`node.created` *artifact provenance*. The reshape's north star is "events are truth; one hash-chained log per concern." `audit/ledger.jsonl` has zero vocabulary overlap with `events.jsonl` (provenance graph vs. task lifecycle), so it is plausibly a legitimately separate concern — but the plan must say so explicitly rather than leave a third log undocumented. Decision for V1: keep the audit ledger as its own concern (artifact lineage is orthogonal to run/step state), but (a) migrate it like the others — no silent drop — and (b) put it through the same transport discipline S1 builds (atomic append, and a hash chain if it's audit-grade). Revisit folding asset/node events into the main log only if a real query wants them joined. This closes the "is it a third parallel store?" hole as a *choice*, matching how the timeline `assembly.jsonl` relationship is already handled.
- **Cost is a first-class but optional field on a step.** Code that knows the cost (LLM SDK response, RunPod billing) declares it on completion. No automatic tracking. Aggregable up to run, timeline, project.
- **Assignee taxonomy collapsed to four forms:** `system | agent:<id> | human:<name> | any-human`. **`any-agent` is deleted** — it was validated but never branched on, and in a single-user tool "any agent can claim this" is identical to `system`. **The `actor` ack-kind is renamed to `human`** (the `human:` prefix mapped to a kind literally called `actor` for no reason); the `AckRule.kind` becomes `Literal["agent", "human"]`. **`any-human` stays** — it's the one genuinely-used "escalate to whoever's around" form (the exhaust-override path). Set per-step in the plan, never inferred from session identity. Explicit `astrid claim` verb; agent can claim for itself or on behalf of a human.
- **Stable agent identity in `~/.astrid/identity.json`.** Carries `agent_id: <slug>` (e.g. `claude-1`, `codex-research`) — the canonical id used in `agent:<id>` assignees and ack `--agent` flags. Sessions inherit it; a session may override per-tab via `astrid attach --as agent:<id>` for occasional multi-agent setups. Without an identity file, `astrid` errors on first run and prompts the user to create one. Single-user doesn't remove the need for stable agent ids.
- **Migrate everything, no shims.** Single user; no compat burden. One-shot rewrites for `active_run.json`, threads, per-project/per-run `timeline.json`, existing `plan.json` files.
- **Project slugs are unique under the same root.** `astrid projects create` blocks duplicates. Across different roots is fine.
- **`astrid status` is the agent's mandated anchor.** SKILL.md's first instruction is "run status before any other verb; if unbound, ask the user which project and timeline." The stop-hook re-injects this when context decays. CLI gates every other verb behind a session binding.

### State machines (authoritative)

These are the only valid transitions. Any verb or adapter that wants to push state through one of these objects must emit the corresponding event; any state not reachable by these arrows is a bug.

**Run:**
```
created → in-flight → completed
                    → aborted
in-flight ↔ in-flight   (plan_mutated, claim, unclaim, takeover bumps writer_epoch)
```

**Step:**
```
declared → dispatched → completed
                      → awaiting-fetch → completed       (remote-artifact)
                                       → failed-fetch    (terminal until retry-fetch)
                      → ack-pending   → completed        (requires_ack: ack approve)
                                      → retrying         (ack retry → re-dispatch)
                                      → failed           (ack abort scopes to step)
declared → tombstoned                                    (undispatched only)
dispatched → superseded-by-vN                            (immutable; new version takes over for unstarted iterations/items only)
```

**Iteration / item (inside a repeat step):**
```
pending → started → completed
                  → failed → started     (next iteration / item attempt)
                           → exhausted   (terminal; pins the step as failed)
```

Anything not in these tables — "edited mid-flight", "rewound to before dispatch", "split across two writers" — is rejected by the kernel.

### How this gets executed

The reshape is itself executed via Astrid's task system (megaplan). Per-sprint planning, decision logging, sprint-entry context loading, exit rituals, risk tracking, and acceptance gating all live in megaplan as runs and steps. This doc captures *what* to build and *in what order* — the engineering substance. It deliberately does not specify a parallel paperwork track. The only process-shaped artifacts inside individual sprints are **stop-lines** (engineering halt-conditions that override "push through"), which are listed in each sprint's Decisions block.

The empirical backing for this plan — the multi-agent codebase review, the load-bearing-assumption spikes (flock-on-APFS, env inheritance, the timeline-format contract, hype expressibility), and the running decision backlog — lives in `docs/reshape/review-findings.md`. Where this doc states current code state or a "this already exists / this is a hard prerequisite" fact, that file is the provenance. Re-baseline against the tree at each sprint entry; verified facts decay.

### Explicitly out of scope for V1

- Fan-out / fan-in across sibling steps — sequential cursor only. `depends_on` is a reserved field for later.
- Automatic cost tracking — only what code declares.
- Multi-user identity proof — `--actor bob` is taken at face value.
- CAS layer (the Phase 7 stub stays a stub).
- Bundle import — export exists, round-trip is later.
- Orchestrator versioning / project-pinning to a specific orchestrator version.
- Banodoco/reigh extraction from `core/`. `core/reigh/`, `core/worker/banodoco_worker.py`, `astrid/timeline.py`, and the ~320 in-kernel banodoco/reigh references stay put for V1. Astrid is single-user and single-consumer today; drawing a framework/product boundary now is speculative abstraction against a second domain that doesn't exist. The Sprint 4 RunPod lift establishes the peer-capability *pattern*; revisit Banodoco extraction the day a real second domain consumer (a non-Banodoco `domains/*`) shows up. Deferred on purpose, not overlooked. **One carved-out exception:** the timeline *format* unifies on `TimelineConfig` in S2 (the event-log projection commits to it). That's not new coupling — `core/timeline`'s projection is *already* used only for Banodoco video work — it's deleting the pretense that the projection is product-neutral. Keeping a fake-generic clip shape to preserve a decoupling that serves no second consumer is the exact kind of speculative abstraction this plan refuses elsewhere.

---

## Sprint 0 — Prerequisites (~3 days)

**Goal:** stand up the scaffolding the reshape sprints assume but don't own. Nothing here ships user-visible behavior; everything here makes the next eight weeks survivable.

### Decisions

- **Long-lived `reshape/` branch off main.** One feature branch per sprint, merged into `reshape/`. `reshape/` only merges to main after Sprint 5a soak. Half-migrated state on disk + half-shipped code on main is the worst case; this branch strategy avoids it.
- **Snapshot before everything.** `astrid-projects/` tarball stored outside the repo, dated. Re-snapshot at every sprint entry. This is the data-rollback for every migration.
- **Pinned regression workload.** Pick one specific past hype run (transcript + brief + final mp4). Re-run it end-to-end as the regression gate at every sprint exit. If a sprint breaks it, the sprint isn't shipped.
- **Two spikes are pre-Sprint-1, not in Sprint 1.** Env inheritance and macOS APFS flock semantics. Both are ~20–60 lines of test code; both are load-bearing for Sprint 1's design. If either spike's result invalidates an assumption, Sprint 1 redesigns *before* coding rather than mid-sprint.
- **CI exists before the reshape touches everything.** There is currently no `.github/workflows/`; later sprints (e.g. Sprint 4's RunPod smoke) already reference CI as if it's there. Stand up a pipeline now — pytest + ruff + mypy on every push, the pinned regression workload wired as a gated job — so an eight-week rewrite has an automated floor under it instead of a manual one. The test suite is large but ungated today; gating it is the difference between catching a migration regression in CI and catching it in a soak.
- **Pack code-execution trust boundary is a decision, not a default.** Registry load runs pack-supplied Python via `runpy.run_path` / `importlib` — by design for packs you author (packs *are* code), an unguarded RCE for anything pulled through the `external/` dir or the catalog `git clone` path. Decide the boundary explicitly: V1 trusts only first-party, author-written packs; external/catalog pack *install* is out of scope until a sandbox or signing story exists. Write the decision down so "we run arbitrary pack code on load" is a choice, not an accident.

### Deliverables

- `reshape/` long-lived branch off main
- Initial dated snapshot tarball of `astrid-projects/` outside the repo
- **Inventory script** (read-only): walks every project, lists every `active_run.json`, every per-run `timeline.json`, every `plan.json`, every thread state file. Outputs CSV. Re-runnable later to detect on-disk drift. **Three state kinds no migration step currently covers — fold these into the migration scope or they're silently dropped:** (1) `runs/<ulid>/audit/ledger.jsonl` — a *separate* `astrid/audit/` subsystem writing `asset.created`/`node.created` provenance events, distinct from task `events.jsonl` (see the third-log decision below); (2) `runs/<ulid>/hype.plan.json` — hype's own capability-intent/step-selection artifact, distinct from task `plan.json`, carrying provenance on what hype actually attempted; (3) `runs/<ulid>/_llm_debug/` — LLM request/response capture (lower-grade, but on-disk state the code writes).
- **Two-tab adversarial test harness**: script that opens two shells and races the same verb against the same run. Used to validate Sprint 1's lease epoch + locked append, and re-used for every later concurrency-touching change.
- **Spike: env inheritance audit** — confirm `ASTRID_SESSION_ID` survives every existing subprocess path (executor runner, orchestrator dispatch, anything else).
- **Spike: flock-on-APFS** — confirm `flock` honors exclusive locks across processes on macOS APFS for `events.jsonl`-shaped writes.
- Pinned regression workload checked into a fixtures location, with documented "how to re-run" steps.
- **CI pipeline** (`.github/workflows/`): pytest + ruff + mypy on push; the pinned regression workload wired as a gated job; the two-tab adversarial harness runnable in CI. Replaces today's no-automated-gate state. While here: register the unregistered pytest marks (`slow` is used at `test_text_card_render.py` but never registered; `performance_smoke` is registered only in a nested `tests/timeline/conftest.py`, not project-wide) and delete or fix the few tests that can't fail (the renderer-parity all-skip; the `assert code in (0, 1)` smoke; the allowlist test that asserts only one stderr string is *absent*; the remotion-registry test that mocks `subprocess`/`server`/`port` and asserts on the mocks). Consolidate the copy-pasted `_mint_session`/`_setup_project` scaffolding (≥5 session test files) onto the existing `conftest.py` fixture. So a green run actually means something.
- **Repo-hygiene + pack-validation pass** (read-then-act, low-risk, none of it reshape work): drop the generated artifacts littering the repo root (`agentic-*.report.md`, `dry_run_map.json`, `plan_v1.revised.md`, et al.), gitignore `.desloppify/` and `*.bak`, get real secrets out of the working tree, and close the validator hole where `packs/builtin/pack.yaml` omits `content:` and ~49 component manifests escape schema checks. **Closing that hole is gated on first fixing the orchestrator JSON Schema, which is currently fiction:** `schemas/v1/_defs.json` requires `runtime.type` (`"python-cli"`/`"command"`) + `entrypoint`, but every real manifest and the Python parser (`orchestrator/schema.py:_parse_runtime`) use `runtime.kind` + `command`/`module`/`function`; and `orchestrator.json` requires `schema_version`, which **all 10** builtin orchestrator manifests omit. Closing the `content:` hole without first rewriting the schema to match reality (and adding `schema_version` to the 10 manifests) turns CI red on every orchestrator. Fix schema→reality, then enforce. While here, finish the dedup cluster the review found: `_utc_now` (6 copies across pack `run.py` files), `_read_env_value`/`_candidate_env_files` (3 implementations, plus packs importing env helpers from `generate_image_openai.run` instead of a shared util), and `probe_duration` (2 ffprobe copies) all route through one helper. And fix two `REPO_ROOT` defects: `core/element/cli.py` defaults `project_root=REPO_ROOT` while its executor/orchestrator siblings correctly use `Path.cwd()` (breaks any non-repo-root invocation), and `core/executor/install.py` re-derives a local `REPO_ROOT` that actually resolves to the *package* dir, landing venvs inside the package tree. Doing this now keeps the next eight weeks legible.

**Ship state:** no user-visible change. Branch, snapshot, inventory, harness, two spikes, regression workload, two living docs. Sprint 1 starts from a known floor.

---

## Sprint 1 — Sessions and the binding contract (~1.5 weeks)

**Goal:** end multi-tab races; make "what am I bound to" first-class; ship the agent's anchor.

### Decisions

- Session id = ULID. Stored in `~/.astrid/sessions/<ulid>.json` with bound project, timeline, run, attached_at, last_used_at.
- `ASTRID_SESSION_ID` env var binds the tab. Subprocesses inherit through `fork`/`exec`; audit the executor runner to confirm nothing scrubs env.
- Per-user default project in `~/.astrid/config.json`; per-workspace override in `.astrid/config.json`. Neither auto-attaches — both only feed the suggestion shown by `status` when unbound.
- Per-project default timeline pointer recorded in `project.json` (full timeline container lands in Sprint 2; record the slug now, wire it then).
- Read-only attach when a run is held by another session. Takeover is an explicit verb (`astrid sessions takeover <id>`); both old session and new session see a `takeover` event.
- **Run lease epoch (`writer_epoch: int`) on every run.** Stored in `runs/<ulid>/lease.json` alongside `attached_session.json`. Every mutating verb reads the epoch, includes it in its event, and the kernel CAS-rejects if the on-disk epoch has moved. Takeover atomically increments the epoch in the same write that swaps `attached_session.json`. This is what actually closes the takeover-mid-ack race; the takeover *event* is just observability. **Reading the epoch is fail-closed, not best-effort.** Today `lifecycle_ack.py` reads `writer_epoch` under `except Exception: pass # best-effort`, so a corrupt or unreadable `lease.json` silently degrades the stale-ack check to a no-op — the exact opposite of a fence. The rewritten append path treats an unreadable lease as a hard rejection (cannot prove freshness ⇒ refuse the write), never a silent skip.
- Stuck-attachment recovery: `status` from a fresh tab proactively flags suspected-dead sessions (no recent events + old file mtime) and offers takeover with a "may still be live elsewhere — confirm" warning. Manual `astrid sessions detach <id>` is the escape hatch.
- Threads die. `thread show @active` and friends are removed; any persistent thread state is migrated into session bindings in a one-shot pass.
- Inbox primitive standardized: every run has `runs/<ulid>/inbox/`. Sessions and external systems write JSON files; `astrid next` consumes them. This is what makes async work possible from day one.
- **First-run bootstrap is part of this sprint, not assumed.** A fresh tab post-migration must not produce a string of errors. When `~/.astrid/identity.json` is missing or no default project is set, `astrid` prompts through the setup explicitly (identity, project discovery, default selection). `astrid status` when unbound + no default lists discoverable projects with the `attach` command spelled out, not just "no session."
- **Migration sets a per-project default-timeline sentinel** even though Sprint 2 wires the actual timeline container. Otherwise Sprint 2 has to backfill across the entire project tree.
- **Stop-line:** if the env-inheritance spike (Sprint 0) reveals `ASTRID_SESSION_ID` doesn't survive a subprocess path we depend on, halt and redesign. Don't ship session-as-env if the env can be scrubbed.

### Deliverables

- `astrid attach <project> [--timeline <slug>] [--session <id>]`
- `astrid sessions ls / detach / takeover` (takeover atomically bumps `writer_epoch`)
- `astrid status` rewritten with full breadcrumb (session, project, timeline, run, current step, recent events, inbox count, takeover hint when read-only, default-project/timeline suggestion when unbound)
- `runs/<ulid>/lease.json` carrying `writer_epoch`
- **Locked event-append path — already largely built; the work is routing + closing holes, not inventing the lock.** Verification found `append_event_locked` already exists at `astrid/core/task/events.py:94` and holds one `fcntl.flock(LOCK_EX)` across re-read-tail + re-read-epoch + append — and an adversarial review judged that *core critical section* race-free. (idea.md's earlier "append is unlocked" framing was stale.) The remaining S1 work is therefore narrower and concrete: (a) route **every** mutating verb through the locked helper — today `cmd_ack`'s retry/iterate paths (`lifecycle_ack.py:357,425`) call the legacy unlocked `append_event` directly, letting a *read-only* session append events and bypass the `WriterContext` `attached_session_id` check; (b) delete or forbid the legacy `append_event` path so nothing can skip the fence; (c) fix the takeover **warm-check TOCTOU** — `cmd_sessions_takeover` reads warmth outside the flock (`cli.py:587`) then bumps the epoch (`cli.py:595`), so a live writer can be taken over without `--force`; move the warm check inside the locked bump; (d) delete the dead fail-open `writer_epoch` read (`lifecycle_ack.py:190-196`, `except Exception: pass`) or wire it into a real fail-closed check.
- `~/.astrid/identity.json` with `agent_id`; first-run bootstrap prompts the user to set one
- CLI gate: every verb except `attach`, `status`, `projects ls/create`, `sessions ls`, `sessions takeover` errors out unbound
- `~/.astrid/config.json` + `.astrid/config.json` schema and reader
- Migration: read existing `<project>/active_run.json` once, materialize as session binding for the calling tab, delete the file
- Migration: thread state → session bindings, then remove the thread subsystem
- SKILL.md / AGENTS.md rewritten around `astrid status` as step 1; stop-hook preamble updated
- First-run bootstrap path: identity prompt + project discovery + default selection + per-project default-timeline sentinel
- Sprint 0 spike findings consumed (env-inheritance + flock-APFS results inform implementation; if either invalidates a design assumption, the sprint design is updated *before* coding)

**Ship state:** multi-tab is safe, defaults honored, status is the anchor. Timeline still isn't a container; canonical orchestrators still don't emit plans. The agent works in the existing model, just much less likely to clobber itself.

---

## Sprint 2 — Timelines as containers + final outputs (1.5 weeks)

**Goal:** make timelines a first-class persistent thing under projects; capture final outputs explicitly; enforce slug uniqueness.

### Decisions

- `<project>/timelines/<ulid>/` with three files:
  - `assembly.json` — the editable timeline, **stored as a `TimelineConfig` document** (`banodoco_timeline_schema` — the exact shape reigh-app renders). Not "mirrors TimelineConfig" — *is* `TimelineConfig`. The edit-event log (`assembly.jsonl`) projects directly into this shape; there is no second projection format. Hype's render-ready artifact under a run's `produces/` is the **same `TimelineConfig` shape** — a finalized snapshot of an assembly, not a different format. It keeps the `timeline.json` filename only because it's a run-output artifact, but the schema is byte-identical to the container assembly. One format; the only difference is role (live container vs. finalized snapshot).
  - `manifest.json` — list of contributing runs, list of final outputs.
  - `display.json` — slug, human name, default flag.
- **Hard prerequisite: the projection must emit a `track` on every clip, or it produces invalid `TimelineConfig`.** `banodoco_timeline_schema`'s `TimelineClip` requires `['id', 'at', 'track']`; `validate_timeline` hard-fails a clip without `track`. Astrid's event vocabulary has `track.added`/`track.removed` (the lanes exist as objects) but **no event binds a clip to a track**, and the current projection emits neither `at` nor `track` in the required shape. So "retarget the projector to `TimelineConfig`" is not a pure rename: S2 must add a clip→track assignment to the event vocab (e.g. a `track` field on `clip.added` + a `clip.retracked` event) and have the projector populate `id`/`at`/`track` on every clip. **Good news bounding the risk:** the installed schema and reigh-app's vendored copy are byte-identical (zero version drift), and `track` is the *only required* field Astrid can't yet produce — the other render fields the renderer reads (`speed`, `hold`, `opacity`, `x/y`, `output`, `pinnedShotGroups`, animations, …) are all *optional*; a timeline without them still validates and renders. Producing those is deferred until a timeline actually needs the feature, not an S2 blocker.
- **Unify the timeline format; delete the parallel clip shape.** Today `core/timeline`'s projector emits clips as `{kind, asset_id, start, duration}` while `TimelineConfig` uses `{clipType, asset, at, from, to, …}`, and *nothing bridges them* — two document shapes for one composition, with hype writing both. S2 retargets the projector to emit `TimelineConfig` directly, deletes the neutral clip shape, and removes the false `model.py` "mirrors reigh-app's TimelineConfig" docstring (it now *is* the schema, imported from `banodoco_timeline_schema`, not a hand-rolled lookalike). The event vocabulary (`clip.added`, `clip.retimed`, `theme.set`, `track.added`, …) is unchanged — only its projection target changes. Migration rewrites any existing `assembly.json` from the old projection shape into `TimelineConfig` in the same one-shot pass as the file rename. **No shim, no compatibility shape, no converter layer** — the projection target and the render format become one thing.
- Slug is a mutable alias; ULID is identity. Renaming = updating `display.json`. Deleting = soft-tombstone (mark in manifest, leave files); hard delete is a separate, rarely-used verb.
- Per-project default timeline pointer (recorded in Sprint 1) is now consumed: `astrid attach <project>` uses it when no `--timeline` is passed; status shows it in the breadcrumb. Still requires explicit confirm.
- One run feeds exactly one timeline (single `timeline_id` ULID on `run.json`). Timelines can't span projects.
- **Final outputs list** on the timeline manifest: `final_outputs: [{ulid, path, kind, size, sha256, check_status, check_at, recorded_at, recorded_by, from_run}]`. Path is a pointer to wherever the file actually lives; `size` and `sha256` are captured at finalize time so the audit record stands even if the file later moves or rots. Multiple per timeline allowed; one timeline can finalize a video plus its thumbnail plus its transcript.
- `astrid timeline finalize <slug> --output <path> [--kind <label>] [--from-run <run-id>]` records an entry, computing `size` + `sha256` at call time and stamping `check_status: ok`. `--from-run` is provenance and defaults to the current run.
- `astrid timeline show` recomputes `check_status` for each final output if `--verify` is passed (cheap stat + sha256). Without `--verify`, it just reports the recorded values.
- Migration: existing per-project / per-run `timeline.json` files are rewritten into the new shape in a one-shot pass. The dangling `<project>/timeline.json` schema path is removed.
- Project slug uniqueness enforced at `astrid projects create` under the same root; across roots is fine.

### Deliverables

- New on-disk schema for `<project>/timelines/`
- **Projector retargeted to `TimelineConfig`**: `core/timeline` projects the event stream into `banodoco_timeline_schema`'s `TimelineConfig` shape; the parallel `{kind, asset_id, start, duration}` clip shape is removed and the `model.py` "mirrors" docstring deleted. Hype writes one shape (`TimelineConfig`) for both its render artifact and its timeline edits — the dual-write that exists today is collapsed.
- `astrid timelines ls / create / show / rename / finalize / tombstone`
- `timeline_id` field on `run.json`; `--timeline` flag on `astrid start`; defaults to project default if set, otherwise `start` errors with the choice prompt
- Wire timeline + final outputs into `astrid status` output
- One-shot migration script for existing `timeline.json` files (per-project and per-run), **rewriting any old-projection-shape `assembly.json` into `TimelineConfig` in the same pass**
- `astrid projects create` blocks duplicate slugs under the same root
- Default-timeline pointer in `project.json` consumed by attach + start

**Ship state:** projects have multiple named timelines; runs declare which timeline they feed; the breadcrumb in `status` is complete; final outputs are explicitly captured wherever they live. Step model and orchestrator porting are next.

---

## Sprint 3 — Step model overhaul, mutable plans, location-agnostic execution (2 weeks)

**Goal:** simplify the step model; make plans editable mid-run; make execution location-agnostic; add the claim verb.

### Decisions

- **Step model collapsed.** One step type:
  ```
  Step {
    id: str
    version: int          (bumped when a dispatched step is superseded)
    adapter: "local" | "manual" | "remote-artifact"
    requires_ack: bool
    assignee: "system" | "agent:<id>" | "human:<name>" | "any-human"
    produces: [{name, path, check}]
    repeat: until | for_each | none
    command: str?         (leaf step: the thing to run; interpreted by adapter)
    children: [Step]?     (group step: nesting; replaces old `nested` kind)
    cost: {amount, currency, source}?  (recorded at completion)
    superseded_by: { to_version: int, scope: "all" | "future-iterations" | "future-items" }?
  }
  ```
  **Supersession scope is required, not optional.** A `repeat.until` step with iteration 2 in flight that's superseded with `scope: "future-iterations"` finishes iteration 2 against the old version, then iteration 3+ uses the new version. `scope: "all"` aborts the in-flight iteration and restarts at iteration 1 of the new version. `scope: "future-items"` is the equivalent for `repeat.for_each`. Without an explicit scope, supersede is rejected.
  - Leaf step has `command`, no `children`.
  - Group step has `children`, no `command`. Its `produces` aggregates from descendants.
  - `code` / `attested` / `nested` step kinds are gone.
- **`repeat.until` condition grammar must be specified in this sprint, before the schema locks** — the hype port depends on it. The schema says `repeat: until | for_each | none` but never defines what `until` *evaluates*. Hype's editor-review loop (re-run cut→refine→render→review until `verdict == "ship"`) needs `repeat.until` on a **group** step that can reference a descendant's `produces` (e.g. `editor_review.produces.review.verdict == "ship"`). Decide and write down: (1) the `until` expression grammar (what it can reference — a produces field, a path-freshness sentinel for cache-skip, etc.); (2) explicitly whether a **group step may carry `repeat`** (the hype loop assumes yes). If group-repeat is not supported, the loop falls back to agent-driven plan-mutation (append cut-v2/render-v2 each revision) — auditable but clunky. The hype spike (back half of this sprint) is where this gets pinned; the spike must produce the grammar, not just discover it's missing.
- **Ack identity at ack time, not plan-author time.** `astrid ack <step> --decision {approve,retry,iterate,abort} --agent <id>|--human <name> [--evidence <path>]`. Both `--agent` and `--human` are required (one or the other) — no anonymous acks. (`--human` replaces the old `--actor` flag in step with the `actor`→`human` kind rename.) Every ack also carries the `writer_epoch` it read; stale acks are rejected by the kernel.
- **Authoring keeps reusable composition; runtime stays uniform.** Two template kinds at authoring time:
  - **Leaf-template** — what we used to call an executor. One concrete unit of work. Same pack layout on disk.
  - **Plan-template** — what we used to call an orchestrator: a reusable composition of leaf-templates and other plan-templates. Materializes into a step subtree at plan-build or plan-mutation time.
  Runtime never sees templates — only the resulting step tree. This keeps hype-style work compositional without re-introducing a parallel runtime abstraction.
- **Template authoring transition (S3 → S5b).** During Sprint 3 the new template kinds land alongside the legacy `OrchestratorDefinition` YAML — both readable. `astrid pack list / inspect` show both kinds with their type. `astrid pack run` accepts both; legacy YAML is materialized into the new step tree on the way in. Sprint 5b removes legacy YAML acceptance once hype + event_talks + thumbnail_maker are all ported. There is no third intermediate format; users write either the legacy YAML (until Sprint 5b) or the new template kinds (from S3 onward).
- **Plan mutation invariants** — every mutation, before it's accepted, must pass:
  - Schema validation on the proposed effective tree (full re-validate, not a diff).
  - Sibling-id uniqueness at every frame (the existing rule in `plan.py:_assert_unique_paths`, applied to the effective tree).
  - `produces` reference integrity (no dangling refs to deleted/tombstoned steps).
  - Adapter validation (declared adapter is one of `local | manual | remote-artifact`, command shape matches adapter).
  - Repeat-source validation (`repeat.for_each.from_ref` resolves to a real prior `produces` in the effective tree).
  - Lease epoch CAS (the writer's epoch matches current).
  Mutations that fail any check are rejected at the verb, not partially applied.
- **Plans are mutable, but mutation rules are explicit.** Verbs: `astrid plan add-step`, `astrid plan edit-step`, `astrid plan remove-step`, `astrid plan supersede-step`. Each emits a `plan_mutated` event carrying the diff, the actor, and the `writer_epoch`. The hash chain extends to plan mutations.
  - The initial plan is the **genesis event** of `events.jsonl` (`plan_initialized`), written once at run start; `plan.json` is a cached projection of it, not a separate source of truth — the log wins on any disagreement, and `astrid events verify` validates the plan from the genesis event forward.
  - The *effective* plan = genesis event + replayed mutation events.
  - **Append-only once dispatched.** A step is "dispatched" the moment `astrid next` returns its payload (event: `step_dispatched`). After dispatch:
    - `remove-step` is rejected. Use `abort` on the run instead, or `supersede-step` to write a new version that replaces it for any not-yet-done iterations.
    - `edit-step` is rejected. Use `supersede-step` to bump `version` and write a new step record; the old version stays in `events.jsonl` and on disk as the audit record of what was actually attempted.
    - **Canonical step path is always versioned.** Every step lives at `steps/<id>/v<N>/...` (v1 for the initial step, v2+ for supersedes). Iterations and items live under `steps/<id>/v<N>/iterations/NNN/` and `steps/<id>/v<N>/items/<item-id>/`. The current unversioned layout is migrated forward in one shot.
    - The original `steps/<id>/v1/` directory is never deleted. The cursor knows which version it's tracking via `(step_id, step_version, dispatch_event_hash)`.
  - **Undispatched steps** can be added, edited, or removed freely. `remove-step` of an undispatched step writes a tombstone event; the cursor skips tombstoned steps when walking the effective plan.
  - Adding a step ahead of the cursor inserts work; adding behind the cursor is a no-op for execution but recorded for audit.
- **Execution is location-agnostic via three adapters; only `local` and `manual` ship in this sprint.** Step schema reserves `adapter: "local" | "manual" | "remote-artifact"`. Execution semantics live in the adapter:
  - **`local`** — `command` is a shell command run as a subprocess in the project root. Outputs land directly in `produces/`. Completion is exit code 0 + produces checks pass.
  - **`manual`** — agent (or human) runs the work somewhere out-of-band; `command` is the dispatch payload (instructions for the agent / actor). The agent is responsible for landing outputs in `produces/`. Completion is `astrid ack` (sync) or a completion JSON in inbox (async).
  - **`remote-artifact`** — schema-reserved here, **implemented in Sprint 5a alongside hype** (its first real client). Steps declared with `adapter: remote-artifact` are rejected by the kernel in S3 with a clear "not yet implemented" error. This keeps S3 focused on the kernel and avoids building a small job system in the abstract.
  Adapters are first-class code, not config. New adapters can be added later (`docker`, `bigquery`, etc.) without changing the step schema.
- **Async is the default path.** No special "long-running" step kind — the `manual` and `remote-artifact` adapters both naturally support "dispatch now, complete later." The agent can dispatch a step, close the tab, return tomorrow, reattach the session, and `astrid next` will pick up wherever inbox/remote-status left things.
- **Claim verb.** `astrid claim <step> [--for human:<name>] [--for agent:<id>]`. Default `--for` = the current session's identity. The typical case is one agent in one tab claiming for itself or for its human user. Emits `claim` / `unclaim` events. Read-only sessions are blocked from claiming.
- **Capture-everything rule.** Anything producing an audit-worthy artifact = a step. The friction is small: `astrid plan add-step --command '...' --produces '...'` + `astrid next`. The alternative — agent runs python ad-hoc, artifact appears with no provenance — is what we're trying to eliminate. Truly ephemeral commands don't need it.
- **Hype port spike — back half of Sprint 3, throwaway, do not merge.** Take the first three steps of `builtin.hype` only (transcribe → cut → render) and port them against the new step model in a scratch branch. Deliverable is `docs/reshape/sprint-3/hype-spike-findings.md` listing every schema gap, adapter mismatch, and cost-field ambiguity discovered. Then *revise the Sprint 3 schema while it's still cheap*. Without this spike, Sprint 5a discovers the gaps after the schema is locked and either ships a band-aid or slips. ~2 days, buys ~2 weeks of insurance.
- **Stop-line:** if the hype spike reveals plan-template materialization can't express hype's dynamic discovery (or that any step shape is fundamentally wrong for hype), halt before locking the Sprint 3 schema. Redesign rather than push through.
- **Dogfooding starts at the Sprint 2 ship and is mandatory by Sprint 3 entry.** Sprint 3 development itself happens against an Astrid project (e.g. `reshape-sprint-3`); every meaningful action is `astrid plan add-step`. Friction felt here is friction every user feels.

### Deliverables

- New step schema (with `version`, `adapter`, structured `superseded_by`); rewrite `astrid/core/task/plan.py`
- Versioned step path migration: every existing `steps/<id>/...` becomes `steps/<id>/v1/...` in one shot
- `astrid plan add-step / edit-step / remove-step / supersede-step` and `plan_mutated` event kind in `events.jsonl`
- **`plan_initialized` genesis event**: run start writes the full initial plan as the first hash-chained event in `events.jsonl`; `plan.json` is regenerated as a projection of it. `astrid events verify` validates the chain from this event forward
- **Plan-mutation validator** — single function that runs all six invariants (schema, uniqueness, produces refs, adapter, repeat-source, epoch CAS) against the proposed effective tree. Every mutation verb routes through it; rejection is total, not partial.
- Mutation rule enforcement: edit/remove rejected on dispatched steps; supersede creates a new version under `steps/<id>/vN/` and requires a `scope` argument
- Cursor stores `(step_id, step_version, dispatch_event_hash)`; walks the effective plan respecting tombstones and supersedes (honoring `scope` per repeat semantics)
- **Four current-kernel bugs land as regression tests the rewrite must pass** (tests, not fixes to the code being deleted): (1) a `repeat.until` step that fails a produces-check *and* emits iterate feedback in one dispatch advances the iteration counter by exactly 1, never 2 (today's `gate.py` double-emits `iteration_failed` and silently skips an iteration); (2) inline produces-checks resolve against the cursor's `step_version`, not a hardcoded `v1` (today's `gate.py` looks in `v1/` after a supersede and stalls forever); (3) iteration-feedback writes are atomic (tmp+rename) so a crash mid-write can't reset the cumulative ledger to empty; (4) **a `manual` step whose `completion.json` is missing its `status` field is treated as `failed`, never `done`** — today `manual.py`'s `poll()` returns `done if completion.get("status") != "failed"`, so a malformed completion (`None != "failed"` ⇒ `True`) silently advances the cursor past a step that never finished. The new adapter resolves missing/unknown status to `failed` (fail-closed). The collapsed step model + locked-append path + versioned cursor + fail-closed adapters above should make all four structurally impossible — these tests prove it rather than trusting it.
- **Inbox path+version match** — rewrite `inbox.py` so entries match on `(plan_step_path, step_version, item_id?)` not just the leaf step id. Inbox entries from before a supersede event are routed to the original version's directory; entries after route to the new version. Stale entries that target a tombstoned or fully-superseded step move to `.rejected/`.
- All mutating verbs read + include `writer_epoch` and CAS-check (relies on Sprint 1's lease)
- `astrid claim` / `astrid unclaim` and `claim` / `unclaim` event kinds
- `requires_ack` enforcement; `--agent` or `--human` required at ack time
- **Assignee/ack taxonomy collapse migration**: delete `any-agent` (rewrite any existing `any-agent` assignees to `system`); rename the `actor` ack-kind to `human` and the `--actor` flag to `--human` (`AckRule.kind` → `Literal["agent","human"]`, `human:` prefix → kind `human`); keep `any-human`. One-shot rewrite of existing plans + ack events
- Two execution adapters implemented: `local` and `manual` — each with dispatch + completion + failure semantics. **All adapter sidecar writes (`dispatch.json`, `completion.json`, etc.) go through the atomic tmp+rename helper, not bare `write_text`** — the current adapters write these non-atomically, so a crash mid-write corrupts the state the cursor reads. **Missing/unknown completion status resolves to `failed`, not `done`** (the bug-4 regression test above). `remote-artifact` is schema-reserved and rejected at runtime with a clear deferral error; full implementation lands in Sprint 5a.
- Authoring concept split: leaf-template (existing pack layout) and plan-template (composition unit). Plan-template materialization at plan-build / plan-mutation time. Legacy `OrchestratorDefinition` YAML continues to be readable; materialized into the new step tree on the way in.
- Inbox-driven async-completion path documented and exercised end-to-end with a worked example for `local` (subprocess that outlives the tab) and `manual` (out-of-band ack)
- `cost` field on step completion events (declared by the executing code or adapter)
- One-shot migration of any existing `plan.json` files to the collapsed schema (every existing step gets `adapter: local` and `version: 1`), **seeding a `plan_initialized` genesis event at the head of each existing run's `events.jsonl`** so the chain is self-contained going forward
- **Hype port spike** in a throwaway branch: first three hype steps (transcribe → cut → render) ported against the new step model, with `docs/reshape/sprint-3/hype-spike-findings.md` enumerating every gap. Schema revisions resulting from the spike land *in this sprint*, not deferred.

**Ship state:** the step model is the simpler one we want long-term. Plans are living. Anything the agent does is captured as a step. Async / remote work has a clear, uniform path. Ready to port hype.

---

## Sprint 4 — RunPod Astrid pack (substrate already lifted) (~1 week)

**Goal:** stand up `external.runpod.*` as a first-class Astrid pack on the already-lifted `runpod-lifecycle` substrate, so any orchestrator — `lora_train`, `scene_render`, future GPU work, the Sprint 5a hype port — can request GPU compute through one substrate without depending on vibecomfy to talk to RunPod.

**The generic substrate already exists** — this sprint builds the Astrid consumer on top of it, it does not perform the lift. `runpod-lifecycle` is at v0.3.0 with the full generic surface shipped (`guard.py`/`shipping.py`/`runner.py`, `Pod.upload_path`/`download_archive`, `ship_and_run`/`ship_and_run_detached` with `terminate_after_exec`, `api.create_network_volume` + `Pod.create_storage`/`list_storages`/`get_storage`), and `vibecomfy/scripts/runpod_runner.py` is already the thin ~258-line consumer re-exporting from it (~78/22 generic/specific split). So the real work here is: stand up the Astrid `external.runpod.*` pack, the sweeper, `astrid doctor` integration, and `astrid runpod ensure-storage`; pin the substrate version; and *confirm* (not perform) vibecomfy backward-compat. The history of how the substrate got lifted out of vibecomfy is recorded in `docs/reshape/review-findings.md`; this sprint assumes it as done.

### Decisions

- **Three-layer split, with the line drawn cleanly between "extract the archive" (lifecycle) and "interpret the archive" (consumer).**
  - **`runpod-lifecycle`** owns: pod launch, stateless reattach by id (`discovery.get_pod`, already there), `PodGuard` + signal handlers, the entire upload mechanism (sftp_walk + tarball, exclude set, disk preflight), sync + detached-with-poll exec, artifact archive pull + extract.
  - **`vibecomfy`** keeps: `_runpod_config_kwargs` (env-var conventions), `REMOTE_ROOT`, `DEFAULT_UPLOAD_EXCLUDES` as module constants, and the entire artifact-format reader stack — `_parse_tsv`, `_collect_outputs`, `_collect_run_metadata`, `_collect_watchdogs`, `_build_artifact_manifest`, `_write_artifact_report`, `_print_detached_summary`. These read vibecomfy-shaped paths (`out/corpus_matrix/results.tsv`, `out/runs/*/watchdog.json`) and are genuinely consumer concerns.
  - **`Astrid`** gets a new pack at `astrid/packs/external/runpod/` with four executors plus a sweeper. The pack consumes the lifted lifecycle directly — it does not go through vibecomfy.
- **The substrate surface Astrid consumes is already shipped (v0.3.0); the pack just calls it.** Available and relied on: `guard.py` (`PodGuard` + signal handlers), `shipping.py` (both upload modes, disk preflight, artifact download), `runner.py` (`ship_and_run` / `ship_and_run_detached`, with `terminate_after_exec` — the flag that lets the split trio leave a pod alive between exec calls); `Pod.upload_path` / `download_archive`; the full storage surface — discovery, attachment, expansion, and **creation** (`api.create_network_volume` + `Pod.create_storage` / `list_storages` / `get_storage`). Volume **deletion** is intentionally absent — rare, scary, do it via the RunPod console. The pack pins `runpod-lifecycle>=0.3`.
- **Vibecomfy backward compat is non-negotiable.** The shim already re-exports `run_pod`, `run_pod_detached`, `REMOTE_ROOT`, `DEFAULT_UPLOAD_EXCLUDES`, and the artifact-format readers; every existing caller (`runpod_validate.py`, `runpod_model_matrix.py`, `runpod_corpus_matrix.py`) imports unchanged. Keep that surface stable — it's the compat contract the confirmation gate below checks.
- **Astrid pack shape: one folder, four executors in a single `executor.yaml`** (matches the `external.vibecomfy.{run,validate}` precedent):
  - **`external.runpod.session`** — the workhorse, composite. provision → exec → download → terminate inside a single Python `try/finally`. Guaranteed cleanup. This is what `lora_train` and most callers use day one.
  - **`external.runpod.provision`** — emits `pod_handle.json` (`{pod_id, ssh, name, terminate_at, config_snapshot}`). Does not terminate.
  - **`external.runpod.exec`** — consumes `pod_handle.json`, reattaches via `discovery.get_pod`, ships `local_root` + `remote_script`, downloads artifacts. Leaves pod alive.
  - **`external.runpod.teardown`** — consumes `pod_handle.json`. Idempotent.
- **Astrid has no `try/finally` / `on_failure` / `cleanup` step kind at the plan level** — confirmed against `astrid/core/task/plan.py`, `astrid/orchestrate/dsl.py`. Two consequences: (a) the composite `session` executor is **mandatory, not optional**, because it's the only honest way to guarantee teardown for callers that don't need a hot pod across steps; (b) the split provision/exec/teardown trio needs a **sweeper** as its safety net — a crashed orchestrator between `provision` and `teardown` would otherwise leak a paid GPU pod.
- **Sweeper: `astrid runpod sweep`** — walks every `astrid-projects/<project>/runs/<run-ulid>/steps/<step-id>/v<N>/[iterations/NNN/]produces/pod_handle.json`, parses, calls `runpod-lifecycle`'s `discovery.list_pods` with the pack's `name_prefix`, then decides per-pod with a **two-mode policy**:
  - **Default (safe) mode** — terminate only if **all** of: `terminate_at` has passed; no live session has the handle ack'd (cross-checked against `runs/<ulid>/lease.json` + active sessions); no in-flight exec on the pod (lifecycle's `discovery.get_pod` reports idle, not running). Pods that fail any check are left alone and reported. This is the right default for the "I crashed between provision and teardown" case.
  - **`--hard` mode** — bypasses the live-session and idle-exec checks. Terminates anything past `terminate_at` regardless. For when the user explicitly wants to nuke it (orphaned handle from a prior run that never had a session, etc.).
  Every termination — in either mode — appends a `pod_terminated_by_sweep` event to the owning run's `events.jsonl` with `{pod_id, terminate_at, mode: "default"|"hard", reason}`. Otherwise a swept pod just disappears from the audit log, which is exactly the failure mode the rest of the design works hard to prevent.
  `astrid doctor` *reports* stale handles (read-only, same scan logic, no mutation); the `sweep` verb *mutates*. Doctor is the alert; sweep is the broom.
- **Pod-handle JSON format is Astrid's invention, not lifecycle's.** Lifecycle exposes the primitives to round-trip a pod by id; the artifact shape is the pack's internal contract.
- **`session` produces minimal gate-checked outputs only**: `exec_result.json` (`{exit_code, pod_id, artifact_dir, terminated, cost: {amount, currency: "USD", source: "runpod", basis: "wallclock_seconds * gpu_hourly_rate"}}`) plus an `artifact_dir/` of raw downloaded contents. **Cost is computed at completion** from the pod's wallclock seconds (provision → teardown) × the GPU type's hourly rate (looked up from RunPod's pricing API at completion time, or from a pinned table if the API call fails — the pinned table is recorded in the executor and updated periodically). The same cost field flows into the step completion event per Sprint 3's cost contract, so `astrid run cost` aggregates RunPod spend without S5a having to wire anything new. `provision`/`exec`/`teardown` emit cost on each call so the split-trio path adds up to the same total. Consumers post-process `artifact_dir/` into their own gate-checked outputs. Vibecomfy's rich `manifest.json` / `report.md` stay vibecomfy-side and are *not* baked into Astrid's contract — that keeps the pack useful for non-vibecomfy callers (ai-toolkit training, raw script execution, future GPU work).
- **Relationship to Sprint 5a's `remote-artifact` adapter.** The two are complementary, not redundant. `remote-artifact` is the **generic framework** for "Astrid knows about a remote job, owns dispatch/poll/fetch/checksum semantics." `external.runpod.session` is **one concrete substrate** that framework can call. The S5a hype port can either invoke `external.runpod.session` directly via `adapter: local` (the executor process is local; GPU work happens via SSH from inside it) or call it through `remote-artifact` for additional plan-level visibility. We ship the substrate here; S5a decides which mode hype uses.
- **Order: confirm the substrate, then build on it.** (1) Pin `runpod-lifecycle>=0.3` and verify the surface; resolve the one known seam — the vibecomfy shim passes four kwargs (`guard_factory`, `poll_command_template`, `poll_exit_marker`, `artifact_paths`) that `ship_and_run_detached` may not accept (live `TypeError` vs. stale-on-disk lifecycle — settle which); rename `PodGuard`'s `VIBECOMFY_RUNPOD_MAX_RUNTIME_SECONDS` default to a neutral env name so non-vibecomfy consumers don't inherit the consumer's name. (2) Build the Astrid pack. (3) Wire the sweeper + doctor reporting. Each lands cleanly before the next.
- **Stop-line: vibecomfy's three scripts must still pass unchanged against the pinned substrate.** `runpod_validate.py`, `runpod_model_matrix.py`, `runpod_corpus_matrix.py` are the canary — if any regresses against `runpod-lifecycle>=0.3`, the substrate (not the pack) is broken; halt and fix it before building on top.
- **Sweeper is load-bearing regardless of who uses the split trio.** A Python crash *inside* `session`'s `try/finally`, between provision and the cleanup, still leaks a paid pod. The sweeper covers that case from day one — it's not conditional on whether anyone uses provision/exec/teardown directly.
- **Open question, deferred to first real caller (not blocking this sprint):** does `scene_render`'s per-shot judge-and-reroll loop want a hot pod across iterations? The answer informs how much the split provision/exec/teardown trio gets exercised in real workloads, but doesn't change what we ship — both the composite and the trio land here, work delta is ~100 lines.

### Deliverables

**runpod-lifecycle + vibecomfy (confirm + pin — the lift already shipped):**

- Pin `runpod-lifecycle>=0.3` in the pack's `requirements.txt`; verify the consumed surface (`guard`/`shipping`/`runner`, `terminate_after_exec`, `create_network_volume` + storage methods, reattach-by-id) against a live pod.
- Resolve the shim signature seam (the four extra `ship_and_run_detached` kwargs) and rename `PodGuard`'s `VIBECOMFY_…` env default to neutral.
- **Backward-compat confirmation gate:** `runpod_validate.py`, `runpod_model_matrix.py`, `runpod_corpus_matrix.py` pass a live RunPod run against `runpod-lifecycle>=0.3` with zero source change. This is the entry gate, not new work — the shrink is already done.

**Astrid (the new first-class resident — the bulk of this sprint's real work):**

- New pack `astrid/packs/external/runpod/` with `executor.yaml` (single JSON array declaring four executors), `run.py` (argparse dispatcher: `provision | exec | teardown | session`), `STAGE.md`, and `requirements.txt` pinning `runpod-lifecycle>=0.3`. Pack registered in `astrid/packs/external/pack.yaml`. Same on-disk shape as `external.vibecomfy/`.
- Inputs/produces per executor follow the Sprint 3 step schema. **All `pod_handle.json` artifacts land at the canonical produces path** (`steps/<id>/v<N>/[iterations/NNN/]produces/pod_handle.json`) — this is the path the sweeper walks:
  - `provision`: inputs `[gpu_type?, storage_name?, max_runtime_seconds?, name_prefix?]`; produces `pod_handle` (json_schema check on `{pod_id, ssh, terminate_at, gpu_type, hourly_rate, provisioned_at}`) and `cost` (provision-only fraction).
  - `exec`: inputs `[pod_handle, local_root?, remote_root, remote_script, timeout, upload_mode, excludes]`; produces `exec_result` + `artifact_dir` + `cost` (exec-window fraction).
  - `teardown`: inputs `[pod_handle]`; produces `teardown_receipt` + `cost` (final settle-up).
  - `session`: inputs of provision + exec, no pod_handle escapes; produces `exec_result` (with full `cost`) + `artifact_dir`.
- **Cost emission**: each executor declares `cost: {amount, currency: "USD", source: "runpod", basis}` on its completion event per Sprint 3's cost contract. The trio's three partial costs sum to what `session` would emit as one. Hourly rates come from RunPod's pricing API with a pinned-table fallback shipped in the pack.
- **`astrid runpod sweep`** verb with default-mode and `--hard` mode; default mode skips pods with a live ack'd session or in-flight exec, `--hard` bypasses both checks. Every termination emits `pod_terminated_by_sweep` to the owning run's `events.jsonl` with `{pod_id, terminate_at, mode, reason}`.
- **`astrid runpod ensure-storage <name> [--size <GB>] [--datacenter <id>]`** verb — find-or-create a storage volume by name. Resolves via `Pod.get_storage(name)`; if missing, calls `Pod.create_storage(name, size_gb, datacenter_id)` (default size from a pack-level config, default datacenter from env / pack default). Idempotent. This is the explicit user-driven path; `external.runpod.session` and `external.runpod.provision` continue to **error clearly** when `storage_name` resolves to nothing — they do not silently auto-create. Auto-create as a side effect of a render is too easy a way to spend money by accident; making it an explicit verb keeps the cost decision visible.
- **`astrid runpod volumes ls`** verb — passes through to `runpod-lifecycle`'s `volumes ls`. Read-only inspection; no surprises.
- **`astrid doctor`** integration reports stale `pod_handle.json` files (read-only; same scan logic as sweep, no mutation).
- **End-to-end smoke**: one canonical worked example — a plan-template invocation of `external.runpod.session` with `remote_script = "nvidia-smi -L; echo ok"` that produces a verified `exec_result.json` (including non-zero `cost`) and `artifact_dir/`. Lives in the pack's tests and runs as part of CI.
- **End-to-end sweeper test (live pod)**: provision via `external.runpod.provision`, kill the orchestrator process before teardown runs, then invoke `astrid runpod sweep` and verify (a) the pod is terminated through the lifecycle API, (b) a `pod_terminated_by_sweep` event lands in the owning run's `events.jsonl`. Re-run with `--hard` against a deliberately ack'd handle to verify the bypass path. Without this test, the sweeper isn't really proven.
- Pinned regression workload extension: include the vibecomfy `runpod_validate` smoke in the Sprint-entry regression gate so Sprint 5a verifies the lift survives a real pod launch.

**Ship state:** RunPod is a peer Astrid capability. Vibecomfy works exactly as before but now consumes the shared substrate. Any orchestrator (lora_train, scene_render, ad-hoc GPU work, the Sprint 5a hype port) can request a pod, ship code, run, and pull artifacts back through one well-defined pack. The `remote-artifact` adapter in Sprint 5a can either call `external.runpod.session` from hype's render steps or use it as the substrate primitives are also exposed as `provision`/`exec`/`teardown`. Future GPU providers (Modal, Lambda, etc.) get the same shape — different pack, same contract.

---

## Sprint 5a — Port hype + remote-artifact adapter + core audit reads (2.5 weeks)

**Goal:** prove `plan.json` and the new step model work on the canonical orchestrator; ship the per-run audit commands.

This sprint exists separately from Sprint 5b on purpose. Bundling them was unrealistic — porting hype against a freshly-rewritten step model carries enough risk on its own. **Don't port event_talks or thumbnail_maker here.** Hype must survive real runs first.

### Decisions

- **Port `builtin.hype` first and only.** Canonical example; if it doesn't work end-to-end against the new model, nothing does. Riskiest single deliverable in the whole plan.
- **Hype uses plan mutability.** When it discovers shot count / scene count / etc. mid-run, it calls `plan add-step` (or materializes a plan-template) rather than pre-declaring a fixed grid. This exercises Sprint 3 in anger.
- **Hype uses the right adapter per step.** LLM calls = `local` or `manual`. RunPod renders = call `external.runpod.session` from Sprint 4 via `adapter: local` **by default** (the executor handles the SSH-and-fetch from inside; Astrid sees a local subprocess; cost is already emitted by the pack). Promote a render step to `adapter: remote-artifact` only if plan-level visibility — `awaiting-fetch` UX, `astrid step retry-fetch`, partial-failure replay — turns out to matter for hype's specific flow. Default lean is local-via-session because the substrate already gives us provisioning + cleanup + cost; `remote-artifact` adds a layer that's worth its weight only when retry semantics surface to the user.
- **`remote-artifact` adapter is built here, against hype as the first client.** Schema reservation existed in S3; implementation lands now. Owns dispatch, status polling, artifact fetch into `produces/`, checksum verification, partial-failure semantics. Completion is "remote done AND artifacts pulled AND checksums match." The `awaiting-fetch` state and `astrid step retry-fetch` verb ship as part of this work.
- **`run_completed` event** is written when the cursor reaches the end of the effective plan without abort. `astrid runs ls` distinguishes completed / in-flight / aborted (resolves the FLAG-P5-006 concern from the V1 plan doc).
- **Cost surface for runs only in Sprint 5a.** Step-level cost field (Sprint 3) is consumed by `astrid run cost <run-id>`. Timeline / project aggregations come in Sprint 5b.

### Deliverables

- `builtin.hype` ported end-to-end on the new model: emits initial plan, uses `plan add-step` (or plan-template materialization) for dynamic discovery, picks adapter per step, declares cost where known (LLM calls), populates `consumes`
- **`remote-artifact` adapter implementation**: dispatch + status polling + artifact fetch + checksum verification + partial-failure handling. `awaiting-fetch` step state + `astrid step retry-fetch` verb. First exercised by hype's RunPod render steps. (The current prototype has a tee-thread bug — the stdout log handle is `close()`d in a `finally` while the daemon tee thread is still writing to it, and the thread's `except: pass` swallows every resulting write error, dropping all but the first log line. The clean implementation keeps the handle open until the subprocess drains, or moves the close into the thread.)
- `run_completed` event + `astrid runs ls` status filtering (completed / in-flight / aborted)
- `astrid run show <run-id>` — initial plan + effective plan + outcomes + ack ledger + cost summary
- `astrid run artifacts <run-id>` — flat list: step-id, version, iteration, item, name, path, check status, sha256, declared cost
- `astrid run trace <run-id> --step <step-id>` — every event touching a step (including supersede / tombstone history)
- `astrid run cost <run-id>` — per-run cost aggregation grouped by `source`
- `consumes` field on `run.json`, populated by hype

**Ship state:** hype works on the new model end-to-end; per-run audit is testable. Other orchestrators still on legacy YAML and slated for Sprint 5b once hype has logged real runs without regression.

---

## Soak — Hype shakedown (≥1 week, explicit calendar slot)

**Goal:** prove the kernel under real load before porting more orchestrators on top of it.

Not a coding sprint. Dogfood hype against production-equivalent workloads. Triage papercuts. Tighten SKILL.md / AGENTS.md based on actual friction. Update the risk register. The soak ends when hype has run cleanly for at least seven consecutive days against the pinned regression workload + at least one fresh workload, with no kernel-level fix required.

**Stop-line:** if soak surfaces a kernel issue (lease, append, plan mutation, adapter, inbox), Sprint 5b does not start. Fix in a dedicated patch sprint first. Porting two more orchestrators on top of a wobbly kernel is the failure mode this gate exists to prevent.

---

## Sprint 5b — Port the rest, ship export + verify + cost aggregation (2 weeks)

**Goal:** finish the orchestrator port; remove legacy YAML acceptance; ship the cross-run / cross-timeline audit commands; close the cost story.

**Gate:** do not start until hype has run cleanly on production-equivalent workloads for at least one week. If hype is still bleeding, fix it first.

### Decisions

- **Port `builtin.event_talks` and `builtin.thumbnail_maker`.** Less risky once hype's port is settled. Legacy YAML stays *readable* until both are ported; the moment all three canonical orchestrators run on the new template kinds, legacy YAML acceptance is removed in the same commit. No deprecation window — single user, no compat burden.
- **Aborted-run handling in exports.** `timeline export` and `project export` take `--include-aborted`, default off. Aborted-run artifacts stay on disk (they're audit-grade); the default just excludes them from clean shareable bundles.
- **Hash chain verifier.** `astrid events verify --run <id>` recomputes and validates the chain (initial plan + plan mutations + step events + acks). Cheap reader on top of Sprint 1's events.jsonl.
- **Cost aggregation up.** Timeline-level and project-level rollups, grouped by source.

### Deliverables

- `builtin.event_talks` ported
- `builtin.thumbnail_maker` ported
- Legacy `OrchestratorDefinition` YAML format removed
- `astrid timeline show <project> <timeline>`
- `astrid timeline export <project> <timeline> --out <bundle> [--include-aborted]`
- `astrid project export <project> --out <bundle> [--include-aborted]`
- `astrid timeline cost <project> <timeline>` / `astrid project cost <project>`
- `astrid events tail --run <run-id>`, `astrid events verify --run <run-id>`
- `consumes` populated by event_talks + thumbnail_maker

**Ship state:** full vision is real for all canonical orchestrators. Audit story is testable end-to-end. Cost is captured and aggregable wherever known.

---

## Sequencing

**Strictly serial for one developer.** The "Sprints 1 and 2 in parallel" framing was fiction: Sprint 2 consumes Sprint 1's per-project default-timeline pointer, and a single brain can't hold the session/lease/CAS write path *and* the timelines schema migration in working memory without one polluting the other. Net cost > net savings.

Honest budget:

Lengths re-baselined against what's already built: the flock'd append primitive exists (shrinks S1) and the RunPod substrate is shipped (shrinks S4). S2/S3 are unchanged — S2's bounded `track`-binding addition offsets nothing it lost.

| Sprint | Length | Gate to enter |
|---|---|---|
| Sprint 0 — Prerequisites | ~5 days | — |
| Sprint 1 — Sessions | ~1.5 weeks | Sprint 0 deliverables present; spike findings green (flock + env already confirmed) |
| Sprint 2 — Timelines | 1.5 weeks | Sprint 1 merged to `reshape/`; default-timeline sentinel exists |
| Sprint 3 — Step model (`local`+`manual` adapters only) | 2 weeks | Sprint 2 merged |
| Sprint 4 — RunPod Astrid pack (substrate already lifted) | ~1 week | Sprint 3 merged; step schema final |
| Sprint 5a — Hype port + `remote-artifact` + audit | 2.5 weeks | Sprint 4 merged; vibecomfy regression unchanged; new pack smoke passes |
| Soak — Hype shakedown | ≥1 week | Sprint 5a merged; pinned regression passes |
| Sprint 5b — Rest of orchestrators + export + remove legacy YAML | 2 weeks | ≥7 clean days of hype runs against pinned + one fresh workload |

**Total: ~11–13 weeks** depending on soak duration and whether any stop-line fires.

`reshape/` only merges to main after Sprint 5a soak passes. Half-shipped reshape on main is the failure mode the long-lived branch exists to prevent.

---

## Megaplan profile per sprint

One profile per sprint, no bake-offs. Each sprint runs as a single megaplan job; the tier is set by the **highest-stakes deliverable in the sprint**, lower-stakes items inherit. Picks follow the profile-selection rubric at `/Users/peteromalley/Documents/megaplan/docs/profile-selection.md` — three independent dials (intelligence tier / planning complexity / depth) weighed together.

Three principles drive the picks:

1. **`apex` only on S3 (the kernel schema); `premium` is the ceiling everywhere else.** Of the two kernel sprints, only **S3** runs at `apex`. Its step schema is consumed by S4/S5a/S5b, so a defect cascades into three later sprints *before* an audit would catch it — the one place the default-lower-then-audit bet breaks down, since the foundational artifact can't be cheaply re-audited once downstream work builds on it. That asymmetry (cheap to get right now, expensive to fix once load-bearing) is exactly tier-5's reason for being, so S3 pays for the second vendor (Opus authoring + Codex structural critique) up front. **S1** (lease/CAS), though also corruption-class, stays `premium`: its design is already locked (the flock'd primitive exists and is sound; the work is closing named holes), so there's no live architectural decision for a second vendor to stress — `premium`'s premium-mind critic plus the compensating controls in principle 2 suffice, and a mid-flight `override set-profile --profile apex` is the escape hatch if it struggles.
2. **`full` robustness everywhere; trust routing on the kernel, audit after.** No sprint uses `thorough`. `full` is the sane default and almost always perfect. The kernel sprints (S1, S3) need no execute-pin: execute is per-task routed, so the complexity-5 kernel tasks (CAS write path, mutation validator) route to Opus on their own, and a premium finalize hard-validates those scores. A pin would only force the *trivial* kernel tasks premium too — caution the routing already covers. Rely instead on routing + premium finalize + the standing *sense-check-after* discipline (post-run plan-vs-tree diff + full test suite). If a kernel run visibly struggles, escalate mid-flight.
3. **The instinct to climb to tier 3 the moment "code" appears is wrong** — the rubric calls this out explicitly. Most lift / port / glue / mechanical-refactor work belongs in `solo` or `directed`. Sprint 0's harness, Sprint 4's lift, and Sprint 5b's orchestrator ports all fit lower tiers than the prior version of this section had.

Within tier-5 / tier-4 picks, bump the planner via `--depth high` when the brief is long or invariants are interlocking. Critic + mechanical phases stay at `:low` (the asymmetry principle). Vendor (`--vendor claude|codex`) is interchangeable at tiers 2-4 per rubric policy; honors your config default — flag explicitly only to override per-sprint.

| Sprint | Length | Tier | Robustness | Depth | Why |
|---|---|---|---|---|---|
| **S0 — Prerequisites** | ~5 days | **`directed`** | `full` | default | Most of S0 (snapshot script, inventory CSV walker, two-tab harness, spikes-as-fixtures, regression fixtures) is tier-1 "just write it." But it also carries the **orchestrator-schema rewrite that gates CI for the entire chain** (`runtime.type`/`kind` mismatch across 10 manifests + the parser, plus closing the `content:` validator hole) — get that wrong at `solo/light` and every later sprint's exit-gate regression runs on a broken floor. Raised to `directed/full` so a premium plan + full critique cover the schema fix; execute stays routed/cheap for the scaffolding bulk. (Both holistic sense-check jurors independently flagged solo/light as the chain's most under-protected high-leverage milestone.) |
| **S1 — Sessions** | ~1.5 weeks | **`premium`** | `full` | **`high`** planner | Lease + `writer_epoch` CAS — corruption-class if wrong, and concurrency design is where a premium *critic* earns its keep. The flock'd append primitive already exists (sound); the work is routing every verb through it + closing the ack-bypass / takeover-TOCTOU holes. `premium`/`full` (default-lower from `apex`/`thorough`); execute stays routed — the complexity-5 CAS tasks reach Opus on their own, premium finalize adjudicates, audit catches the rest. Long brief, interlocking invariants → planner at `high`. |
| **S2 — Timelines** | 1.5 weeks | **`directed`** | `full` | default | Was `premium` for "schema definition" — but the timeline format is now **locked on `TimelineConfig`** (see S2 decisions), so the hard design decision is already made. What's left — container dirs, CRUD verbs, projector retarget, a snapshot-recoverable migration — is premium-*plan* + routed/mechanical execute = tier 2. The format unification dropped this sprint a tier. |
| **S3 — Step model** | 2 weeks | **`apex`** | `full` | **`high`** planner | Step schema + plan replay + mutation validator + cursor + supersession + the `repeat.until` grammar is *the* kernel everything builds on — and it's *consumed by S4/S5a/S5b* before any audit would catch a defect. That cascade is why this one sprint earns `apex` (Opus authoring + Codex structural critique) where S1 doesn't: S1's design is locked, S3's is being *made* here and is foundational. `full` robustness; execute stays routed (hard kernel tasks reach a premium model on their own); planner at `high` for the interlocking invariants. Vendor pin is ignored at apex. |
| **S4 — RunPod pack** | ~1 week | **`directed`** | `full` | default | Substrate already lifted (runpod-lifecycle v0.3); this is the Astrid pack + sweeper policy + a backcompat confirmation. Tier 2 still fits — sweeper two-mode policy needs a smart plan; the pack wiring is mechanical once mapped. Premium plan, cheap execution. |
| **S5a — Hype port + remote-artifact + audit** | 2.5 weeks | **`premium`** | `full` | **`high`** planner | `remote-artifact` is its own small job system with persistent state + partial-failure semantics. Capped at `premium`/`full`; no execute-pin (a fetch/checksum bug fails loud-ish, unlike silent kernel corruption — routing + premium finalize is enough). Hype port is the canonical proof point; planner at `high` for the partial-failure semantics. |
| **Soak** | ≥1 week | — | — | — | No megaplan; manual dogfooding. |
| **S5b — Rest of orchestrators + export** | 2 weeks | **`partnered`** | `full` | default | Two orchestrator ports following hype's worked pattern + export with `--include-aborted` selection rules + read-side audit verbs. Cross-cutting work in a now-known architecture, not kernel-cascade — tier 3 default for "real engineering work." |

Cost shape: S3 at `apex` plus S1 + S5a at `premium full` carry most of the spend — and even there, premium is concentrated in the *reasoning* phases; **execute is per-task routed**, so the mechanical bulk still runs on cheap DeepSeek and only complexity-4/5 tasks reach Sonnet/Opus. S2 + S4 + S0 at `directed` and S5b at `partnered` are cheaper; soak is free. (Apex is spent *only* on S3 because its artifact cascades; everywhere else caps at `premium`/`full` with execute routed rather than pinned — the deliberate default-lower choices, with mid-flight escalation as the escape hatch.)

Worked invocations:

```bash
# S0 — directed: the chain-gating orchestrator-schema fix gets a premium plan + full critique
megaplan init <brief> --profile directed --robustness full

# S1 — kernel (premium): design locked, premium critic + routed execute; planner high for interlocking invariants
megaplan init <brief> --profile premium --robustness full --depth high

# S3 — kernel (apex): foundational schema cascades to S4/S5a/S5b; Opus authoring + Codex critique, planner high
megaplan init <brief> --profile apex --robustness full --depth high

# S2 — directed: timeline format locked on TimelineConfig, so premium plan + routed/mechanical execute
megaplan init <brief> --profile directed --robustness full

# S4
megaplan init <brief> --profile directed --robustness full

# S5a
megaplan init <brief> --profile premium --robustness full --depth high

# S5b
megaplan init <brief> --profile partnered --robustness full
```

No sprint warrants `--with-prep` (briefs are clear from this doc; no unfamiliar libraries; the spikes that look like research are S0 deliverables, not megaplan jobs). No sprint warrants `--critic` overrides (rubric defaults fit).
