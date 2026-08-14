# Checkpoint 2 — Batch 2 (Layer Stack) — PASS

Oracle: Grok 4.6. Delegated Flash facts + critique
(`.oracle/findings/oracle-b2-facts.txt`, `oracle-b2-critique.txt`).
Validated cited lines. Frozen gate: `151 passed` (host).

## PASS

- Scope clean: `dce60b9f` touches only `service.py` + `test_service.py`.
- `_window_timeline` (`service.py:1111–1164`): keyword-only `tracks=None`.
  Clips pre-filtered at 1136 **before** `_window_clip` (1138). Allowlisted
  track survives empty window (1144–1151). Unknown allowlist ids are
  **filtered** (intersection with `raw_tracks`), not added.
- `_segment_request` (`1086–1100`): `tracks=layer.tracks` iff layer set;
  stamps `metadata.astrid_layer = {z, alpha: z>0}` via setdefault-container
 ## PASS

Batch 3 may start.

**Delegated:** Flash facts + critique (`.oracle/findings/oracle-b2-{facts,critique}.txt`). Host `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_contracts.py` → **151 passed**.

**Slice** (`service.py:1111–1164`): keyword-only `tracks`. Allowlist skips clips at 1136 **before** `_window_clip` (1138). Empty allowlisted tracks survive (`used_tracks = allowlist`, then intersect `raw_tracks` at 1147–1151). Phantom ids are **filtered**, not added.

**Stamp** (`1086–1100`): `tracks=layer.tracks` iff layer set; `setdefault("metadata", {})` then `["astrid_layer"] = {z, alpha: z>0}`. Other keys kept; a pre-existing `astrid_layer` is overwritten (correct). `layer=None` → `tracks=None`, no stamp. None-path clip loop matches parent `5f7b1803`.

**B4:** remotion + threejs are `supports_windows: false` — they take this host-slice and can honor the stamp. Key is namespaced.

**B1 note:** no conflict. Empty-window + stamp is the known-layer request B3 pads; `alpha: false` means opaque content, not full span.

**Elegance:** two sites, optional kwarg, no new types. Six tests pin real properties.

Flash’s proposed fail-closed on unknown allowlist ids is **YAGNI** (B5 planner). Not a Batch-2 defect.
