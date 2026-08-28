# Settled-plan wave 1 — synthesis (oracle disposition)

Wave: 2 independent normal-pool critics (DeepSeek V4 Flash), same immutable plan snapshot
(sha256 d35a66f5a9f42fd11182d7fc3eef13fc28e1f101261c9034d5587736fc42fc6b).
Lens1 simplicity (142.7s), Lens2 scope/verification/sequencing (117.0s). Both launch exit=0.

## Lens 1 (simplicity) findings

### F1.1 Expand hook writes twice — merge into snapshot resolution
**Disposition: investigate.** Plan's hook expands the in-memory snapshot after
`resolve_managed_render_snapshot`; the loader is a sibling `SELECT document_json,
asset_registry_json FROM timelines WHERE id=?` beside the existing snapshot query. The
"double write" claim is not accurate — the snapshot is read-only materialized CAS, the
expanded doc is a new in-memory dict; nothing is written back to sqlite (plan says "Do not
expand stored docs"). The simplification to a single reusable callable is sensible for
T5/T6 structure (pure function + one hook point). ACCEPT the structural note: implement
`expand_shot_clips(config, registry, *, load_timeline)` as one pure function; hook
invocation once in `_prepare_managed_render_inputs`; guarantee no sqlite write-back
(expansion is memory-only; stored doc unchanged — T6 already asserts this).

### F1.2 Text rendering over-generalized — narrow to intro shape
**Disposition: reject as stated, accept the intent.** The plan already restricts to
intro-shaped support only ("ffmpeg — intro-shaped only, not a general compositor"):
relax only media+text clipTypes, stills use hold, extra visual tracks iff text-only,
text fades only, text params {anchor, offsetX/Y, maxWidth, weight, textShadow}. That IS
the narrow shape. A single captions-only schema with hardcoded anchor/font would break
generic text clips already in the timeline corpus (brand wordmark uses params;
storyboard captions use params) and would FORCE renderer.yaml/support to special-case
rather than declare capabilities. The support fail-closed suite (T2) already enforces
the boundary. REJECT hardcoding; ACCEPT that T3 keeps the text path minimal and
intro-shaped (bottom-center captions default + brand overlay), no general layout engine.

### F1.3 `--shots` default vs opt-in flag
**Disposition: reject.** Goal says default compile stays flat ("Default compile stays
flat unless `--shots`") — the flat 76-clip emitter is the existing contract and the
golden test keeps it. Making `--shots` default changes the default compile output and
would surprise the existing pipeline. Keep flag opt-in; it is one branch, cheap.
REJECT.

## Lens 2 (scope/verification/sequencing) findings

### F2.1 Scope drift: timeline_document_id → strengthen idempotency proof
**Disposition: accept (cheap, meets kernel-evolution rule).** Add to T10/T12 acceptance:
run compile twice on the temp project → same 25 shots / same 25 timeline rows, NO new
rows on the second run. This is already implicit in done criterion 1 ("running the
compiler twice yields the same 25 shots / 50 items"); make it explicit as a T10 assert
and add "and 25 timeline rows, second run adds none" to the T10 acceptance.

### F2.2 Parallelism: B1 ∥ B2 but B2/B3 also independent
**Disposition: accept.** B2 (expand pure fn + hook) and B3 (compiler projection) are
indeed independent: T5/T6 don't read compiler output; T8-T12 don't depend on the expand
hook (T12's golden-becomes-expansion test uses the pure function, which is available
after B2's T5 regardless of B1). Correct statement: **B1 ∥ B2 ∥ B3** (within-batch
order only), **B4 last** (needs B1 ffmpeg render + B2 expand + B3 --shots parent).
Sync point: B4 starts only after B1, B2, B3 all pass their checkpoints.

### F2.3 Golden test contract not explicit
**Disposition: accept (clarify).** T12 acceptance already says "expand(shot parent) ==
flat modulo clip ids" — make the golden test assert BYTE-EQUIVALENCE modulo clip ids
explicitly in T12 text and add it to done criterion 4 wording ("byte-equivalent modulo
clip ids" is there; keep it and reference T12).

### F2.4 Renderer output canonical location
**Disposition: accept.** Specify one canonical evidence output:
`.oracle/evidence/shot-pipeline.mp4`. T14 writes there; T16 documents that path as
authoritative. Cheap, removes ambiguity.

### F2.5 Loop still-image input undefined
**Disposition: accept as investigate → decided.** The stills are 25 distinct PNGs, each
used once as a unique asset — `-loop 1 -t <hold>` per unique image `-i` in
`build_filter_graph`'s existing unique-asset input list; concat=v=1 sequence preserved.
This is already how media-only stills would flow; T3 makes it concrete. No reuse
machinery needed (each image appears once).

### F2.6 B2/B3 sequential false dependency (dup of F2.2)
**Disposition: same as F2.2 — accept, parallelize.** B1 ∥ B2 ∥ B3; B4 last.

## Accepted changes for revision (fed to grok)

1. B1 ∥ B2 ∥ B3, B4 last (F2.2/F2.6) — clean up the parallelism statement.
2. T10/T12 acceptance: idempotency assert "compile twice → same 25 shots, same 25
   timeline rows, no extra rows on second run" (F2.1).
3. T12/test wording: golden expansion test asserts byte-equivalence modulo clip ids
   explicitly (F2.3).
4. Canonical render output `.oracle/evidence/shot-pipeline.mp4` (F2.4).
5. Structural note: `expand_shot_clips` pure function, single hook, memory-only expand,
   stored doc never written back (F1.1).
6. T3: stills = per-unique-image `-loop 1 -t <hold>` in the existing input list,
   concat=v=1 unchanged (F2.5).

## Rejected (with rationale)

- F1.2 hardcoded single captions-only text schema (breaks brand wordmark + generic text
  clips; support suite already enforces the boundary).
- F1.3 `--shots` as default (changes default compile contract; opt-in flag is one
  branch, golden flat emitter stays canonical).

No material reopening: the plan remains coherent end to end; changes are clarifications
+ one sequencing correction. All settled-plan-wave outputs and this synthesis are
recorded with invocation receipts. Next: feed accepted findings to grok for full-plan
revision → expect `STABLE` → fresh settled wave only if material change (none expected;
findings are non-material clarifications).