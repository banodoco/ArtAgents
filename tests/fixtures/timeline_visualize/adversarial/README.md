# Adversarial fixture corpus — timeline_visualize (R23)

Hermetic adversarial cases for the timeline-visualization evidence pipeline. Every case is
a small fixture (timeline/answer payload + expected behavior) that
`tests/packs/rendering/test_timeline_visualize_adversarial.py` exercises through the REAL
pipeline (executor / CLI / scorer / frozen loader) and asserts is DETECTED — never silently
accepted.

## Cases (see `manifest.json` for the machine-readable index)

| id | Adversarial behavior | Detection surface |
|---|---|---|
| `changed_media` | registry hash vs on-disk bytes diverge | `verify_now` → `hash_mismatch`; sampling refused; verified sibling still sampled |
| `changed_transcript` | declared transcript sha256 vs actual bytes | attachment `integrity=hash_mismatch`; transcript never normalized (no TS ids) |
| `image_order_swap` | two PNGs swapped between pack and gate | `evidence.image_hashes` order preserved; `session_identity` differs |
| `model_changed` | `returned_model != requested` | provenance records both; divergence flagged |
| `resegmentation` | same audio, different segment boundaries | TS ids re-scope under the transcript hash; old refs do not re-resolve |
| `clip_removal` | clip referenced by an SP is removed | frozen load raises `FrozenIntegrityError` naming the dangling SP |
| `tombstone` | timeline tombstoned after the root | frozen drill-down still resolves; fresh render surfaces the tombstone |
| `malformed_answers` | VLM returns garbage | `score_answers` → 0.0 with schema-failure/parse-failure detail |
| `snapshot_drift` | root v159, live v160 | drill-down frozen; `refresh-root` → new SNS |

## Conventions

- All fixtures are deterministic: no datetimes (fixed sentinel strings only), no randomness,
  no live API calls.
- The corpus is hermetic: it must run under default CI (`-m "not integration and not opt_in
  and not live"`), credential-free.
- R24 (live gates) consumes the answer-side fixtures (`image_order_swap`, `model_changed`,
  `malformed_answers`) as locked question/expected-answer sets.
