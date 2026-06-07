# Design: an elegant generation facade for Astrid

> Status: **draft / vision**. The "what exists today" section is being verified by
> three exploration agents (does a facade already exist? what idioms to mirror?
> what to borrow from VibeComfy?) — findings will refine §3 and §6.

## 1. The problem, precisely

Astrid's generation capability is exposed **CLI-first**, not **library-first**.
The richest entry point is:

```python
def main(argv: list[str]) -> int:        # argv in, EXIT CODE out
    result: GenerationResult = adapter.generate(...)   # the real typed result…
    # …converted to manifest dicts, written to {out}/manifest.json…
    return 0                              # …and discarded
```

`main()` builds a `GenerationResult` (paths, `model_actual`, hashes) and the full
manifest — then **throws them away**, persisting to disk and returning `0`. The
proof this hurts: Astrid's own golden demo has to round-trip through a file to
recover what it just made:

```python
code = main(argv)                                     # get back an int
manifest = json.loads((Path(out)/"manifest.json").read_text())   # then re-read off disk
```

Every programmatic use pays this tax. Concretely, that is **why** ad-hoc scripts
were messy:

- **Re-encoding the output location every time** — the contract is `--out <dir>`;
  there is no "save to the canonical run dir and tell me where."
- **Writing a custom script at all** — the only entries are guarded argv-`main()`
  or raw backend internals.
- **Reaching into private internals** (`_extract_asset_urls`) and losing the
  manifest — because the executor couldn't do what was needed (e.g. LoRAs).

The boundary is CLI-shaped (*strings/argv in, files/exit-code out*) when a script
needs library-shaped (*objects in, a typed result out*).

## 2. The vision

One import. Sensible defaults. A typed result you compose. The system owns the
output location and writes the manifest + embedded metadata for free. Same code
path as the executor — a facade, **not** a parallel implementation.

```python
import astrid

# Simplest possible — one image.
img = astrid.generate.image("a glass teapot on basalt")
img.open()                      # show it
img.path, img.seed, img.model   # typed access, no file parsing

# Full control — LoRAs are first-class, routing + base-match validation automatic.
res = astrid.generate.image(
    "weathered fisherman hauling a dripping net, golden hour, 85mm",
    model="z-image",
    seed=7,
    steps=20,
    loras=["z-realgen-v2@1.1"],   # registry id @ scale
    # project omitted -> default project, no ceremony
)
res.path        # Path, already inside the project's run dir
res.manifest    # full manifest dict
res.metadata    # prompt / model / endpoint / seed / loras
```

### Batch & compose — the throwaway-script killer

```python
grid = astrid.generate.image.batch(
    prompts=FOUR_REALISM_PROMPTS,
    models=["z-image", "qwen-image-2512", "flux2-klein-9b"],
    seed=lambda i: 1000 + i,      # same seed per column -> fair comparison
)
grid.contact_sheet("compare.png").open()   # built-in composition
```

### Video — same shape

```python
clip = astrid.generate.video("a wave crashing on rocks", model="wan-2.2", mode="t2v")
clip.path, clip.manifest
```

## 3. The result type (the missing primitive)

A single typed object is what "fetch outputs and return them in a standardized
way" actually means:

```python
@dataclass(frozen=True)
class GenerationResult:
    images: list[Path]          # or videos
    path: Path                  # convenience: images[0]
    manifest: dict              # the full canonical manifest
    metadata: Metadata          # prompt, model, model_actual (endpoint), seed, loras, request_id
    run_dir: Path               # where it landed (canonical project run dir)
    source_urls: list[str]      # cloud provenance, if any
    def open(self) -> None: ...           # macOS `open`
    def contact_sheet(self, out, **kw): ...  # compose (for batches)
```

It is the SAME data `main()` already computes — just **returned** instead of
discarded.

## 4. Design principles

1. **One code path.** The facade calls the same `adapter.generate` + save +
   manifest + PNG/MP4 metadata-embedding the executor uses. No second engine.
2. **Typed returns, never file-hunting.** Callers get objects; the manifest is a
   field, not a path to parse.
3. **The system owns the output location.** Defaults to the canonical project run
   dir. You never pass `--out`.
4. **No ceremony.** Rides the default-project auto-bind; no `attach`/timeline for
   stateless generation.
5. **First-class LoRAs / params.** `loras=[...]` with registry ids; routing,
   base-match validation, and provenance handled below the facade.
6. **Composable.** Results are objects; batches expose composition (contact
   sheets, i2v chains) so scripts stay short.

## 5. Before / after

The 40-line `out/cloud_compare/_driver.py` (argv building, hardcoded `--out`,
`ASTRID_INTERNAL_INVOCATION`, manifest-reading off disk) becomes:

```python
grid = astrid.generate.image.batch(prompts=PROMPTS, models=MODELS, seed=lambda i: 1000+i)
grid.contact_sheet("compare.png").open()
```

The raw-fal LoRA test (HttpClient, `_extract_asset_urls`, no manifest) becomes:

```python
a = astrid.generate.image(PROMPT, model="z-image", seed=4242)
b = astrid.generate.image(PROMPT, model="z-image", seed=4242, loras=["z-realgen-v2@1.2"])
a.compare(b).open()
```

## 6. What this builds on (CONFIRMED by exploration)

This slots into the **existing public SDK** — it is NOT a from-scratch build.

**Already exists (reuse, don't fork):**
- `astrid/sdk.py` + `astrid/__init__.py` — the **public v1 SDK boundary** with
  lazy `_SDK_EXPORTS`. `sdk.invoke()` (sdk.py:1187) already does kwargs →
  resolve capability → `ExecutorRunRequest` → `run_executor()` → typed
  `InvocationResult`. **This is the seam.**
- `GenerationResult` (generation/backends/base.py:76) — the *ideal* typed result
  (`image_paths`, `seed_used`, `model_actual`, `cost_usd`, `error`, `ok`). It is
  produced in-process by `BackendAdapter.generate()` **and then discarded** (the
  executor converts it to `manifest.json` and `main()` returns `0`).
- `Session` (frozen) + `project_run_dir()`/`project_dir()` (core/project/paths.py)
  — the object + helper for **default output routing, no ceremony**.
- `Timeline` is the rich-facade idiom to mirror (`from_*()` classmethods, typed
  props, `to_dict()`/`dump()`).

**Conventions to conform to (Explorer 2):** add to `astrid/__init__.py` exports +
implement in `astrid/sdk.py`; frozen result DTO carrying `error: ExecError | None`
with an `ok` property and `to_dict()`; keyword-only params; lazy imports;
`AstridSDKError` on the public boundary.

**VibeComfy ergonomics to borrow (Explorer 3):**
1. Typed result with **resolved output paths** — callers never parse internals.
2. **Every layer public** — `generate.image() → result`, but also `.load()` →
   workflow, `compile()`, `run()`; no lock-in.
3. **Verb namespace that is plugin-extensible** — `register_op("image","t2i",…)` +
   `ensure_plugins_loaded()` so `astrid.generate.image.<verb>` auto-discovers
   third-party model packs. (Directly serves the **skills-discoverability** goal.)
4. **Default output to a per-run dir** (`runs/<id>/` + metadata), from config not
   hardcoded.
5. **Separable router** — `router.pick(...)` inspectable/overridable.

### The whole feature, in 4 precise moves
1. Add a verb-native `generate()` (`astrid.generate.image/video`) on the
   `sdk.invoke()` seam.
2. **Stop discarding `GenerationResult`** — surface it (refactor the generation
   executor / adapter path so the typed result flows out instead of only
   `manifest.json`).
3. Default `out` → `project_run_dir()` via the bound/auto `Session`.
4. Model/mode inference + a **discoverability skill** documenting the facade and
   the scratchpad convention.

## 7. Phasing

- **v0 (small):** `astrid.generate.image(**kwargs) -> GenerationResult` wrapping
  the existing executor/adapter — typed return + default-to-project-dir. This
  alone retires the throwaway-script pattern.
- **v1:** `.batch()` + composition helpers; `.video`; the scratchpad runner
  (`astrid scratch run <file.py>` wiring project context).
- **Platform:** fold into the full SDK (facade + invocation/session/event).

## 8. Build-plan requirements (drive the megaplan)

Per the project owner, the megaplan that builds this must:

1. **Fit the broader app.** The facade strategy must make sense from the whole-app
   perspective — align with the Python-SDK platform direction, reuse existing
   idioms (timeline/threads/reigh facade patterns, the session/project context,
   `AstridError`), and not fork a second generation engine.
2. **Be discoverable via the skills.** A user who wants to write a custom script on
   top must find it **obvious** how — i.e. ship/update a skill (and `astrid skills`
   discoverability) that documents the `astrid.generate` facade + the scratchpad
   convention with copy-pasteable examples. The skills surface is part of the
   deliverable, not an afterthought.
3. **Land an elegant service.** The end state is a clean, first-class service — the
   typed-result facade, default output routing, no ceremony, composition helpers —
   such that the throwaway-script pattern is fully retired.
4. **Execute end-to-end autonomously.** Run the megaplan to completion without
   approval gates (auto-merge/auto-advance); the owner has pre-authorized execution.
