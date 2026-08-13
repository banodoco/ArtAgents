I'll verify the flagged files and line ranges so the cleanup plan matches the code as it exists now, then write a concrete ordered plan.Findings look solid; I’m now reading the exact helper sites, profile blocks, and remotion pins so the plan names real symbols and files.I have the remotion pin and helper call sites; next I’ll pull the function bodies and test-helper copies so the plan can name exact moves.I'll locate the backendI'll extract the exact code blocks run files and shared and search helpers, then extract the hits for the 90k exactHz import quirk/,function Rem facts youotion pins, Chrome VERSION workaround, and listed. test-helper duplication.Paths are under `backends/`. Next I’ll quote the 90kHz blocks, Remotion pins, and the rendering test helpers.The first search missed those two helper names. I'll read the import/alias blocks and search the function definitions next.Next I’ll read each remotion helper body and how ffmpeg/threejs call them.The Chrome VERSION search was too narrow. I’ll look in remotion setup/docs and pull the test-helper bodies plus renderer-parity paths.Checking whether `_canonical_profile` reads any settings field besides `theme_path`, and confirming there is no `backends/_shared`.# Helper coupling: remotion ↔ threejs (facts)

## 1. Paths

| Item | Path | Exists |
|---|---|---|
| threejs run | `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/threejs/run.py` | yes |
| remotion run | `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py` | yes |
| ffmpeg run | `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/ffmpeg/run.py` | yes |
| `backends/_shared/` | — | **no** |

`backends/` contains only `ffmpeg/`, `remotion/`, `threejs/`.

## 2. threejs → remotion aliases (`threejs/run.py` 56–67)

```56:67:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/threejs/run.py
from astrid.packs.rendering.backends.remotion import run as remotion_backend

# Reuse seam (T3.3): only the side-effect-free execution/provenance helpers.
# The shared Remotion render lock is acquired inside ``_execute_remotion``;
# this backend never adds a second lock or capture stack.
_execute_remotion = remotion_backend._execute_remotion
_render_provenance_payload = remotion_backend._render_provenance_payload
_serialize_timeline = remotion_backend._serialize_timeline
_load_registry_mapping = remotion_backend._load_registry_mapping
_input_path = remotion_backend._input_path
_duration_frames = remotion_backend._duration_frames
_canonical_profile = remotion_backend._canonical_profile
```

Names aliased: `_execute_remotion`, `_render_provenance_payload`, `_serialize_timeline`, `_load_registry_mapping`, `_input_path`, `_duration_frames`, `_canonical_profile`.

Not aliased (threejs defines its own): `_profile_mismatches` (L298), `_settings_from_request` (L249).

## 3. remotion/run.py helpers

### `_execute_remotion` — L600

```600:623:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py
def _execute_remotion(
    timeline_path: Path,
    assets_path: Path,
    staged_video: Path,
    *,
    provenance_out_path: Path,
    project_dir: Path,
    composition_id: str,
    theme_path: Path | None,
    min_free_gb: float | None,
) -> _ExecutionDetails:
    """Render one private video and return the data needed for provenance."""

    with remotion_lock.remotion_render_lock():
        return _execute_remotion_locked(
            ...
        )
```

- Remotion-specific internally: **yes**. `remotion_lock` (import L66). Locked path runs `npx remotion render` (L692–710), `@banodoco` project validation, remotion props file, `ASTRID_TIMELINE_COMPOSITION_SRC`.
- Used by ffmpeg: **no**.
- Used by threejs: **yes** (alias + call L513–522 with `composition_id=THREE_COMPOSITION_ID`).

### `_render_provenance_payload` — L483

```483:497:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py
def _render_provenance_payload(
    out_path: Path,
    *,
    engine: str,
    timeline_path: Path,
    assets_path: Path,
    project_dir: Path,
    composition_id: str,
    theme_path: Path | None,
    active_theme: dict[str, Any] | None,
    registry_state: dict[str, Any],
    stage_summary: dict[str, Any],
    segments: list[dict[str, float | str]] | None = None,
    segment_provenance: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
```

- Remotion-specific imports inside body: **no**. Builds a dict; calls `_active_pack_order_for_provenance` / `_active_theme_for_provenance`. Payload keys include `composition_id`, `project_dir`.
- Used by ffmpeg: **yes** — `remotion_backend._render_provenance_payload` at L149, L379, L579 (`engine="ffmpeg"`, often `project_dir=REPO_ROOT / "remotion"`, `composition_id="TimelineComposition"`).

### `_serialize_timeline` — L126

```126:131:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py
def _serialize_timeline(
    timeline_path: Path,
    *,
    default_theme: str = "banodoco-default",
) -> dict[str, Any]:
    return timeline.Timeline.load(timeline_path).for_render(default_theme=default_theme).to_json_data()
```

- Remotion-specific: **no** (`astrid.core.timeline` only).
- Used by ffmpeg: **no**.

### `_load_registry_mapping` — L878

```878:884:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py
def _load_registry_mapping(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"assets": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("assets"), dict):
        raise ValueError("assets registry must be an object containing an assets object")
    return data
```

- Remotion-specific: **no**.
- Used by ffmpeg: **no**.

### `_input_path` — L817

```817:819:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py
def _input_path(raw_path: str, workspace: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    return (candidate if candidate.is_absolute() else workspace / candidate).resolve()
```

- Remotion-specific: **no**.
- Used by ffmpeg: **no**. ffmpeg defines its own at L67 (same logic). Also duplicated at `backends/ffmpeg/command.py` L90.

### `_duration_frames` — L1051

```1051:1060:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py
def _duration_frames(video_path: Path, profile: RenderProfile) -> int:
    probe = ffprobe_metadata_strict(video_path)
    ...
    return max(1, int(frames + Fraction(1, 2)))
```

- Remotion-specific: **no** (`ffprobe_metadata_strict`).
- Used by ffmpeg: **no**. ffmpeg has a different signature at L512: `def _duration_frames(probe: MediaProbe, profile: RenderProfile) -> int`. Same arithmetic after probe.

### `_canonical_profile` — L887

```887:901:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py
def _canonical_profile(
    timeline_path: Path,
    assets_data: Mapping[str, Any],
    settings: _RenderSettings,
) -> RenderProfile:
    fallback_theme = settings.theme_path or (
        WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json"
    )
    active_theme = _resolved_theme_for_render(timeline_path, fallback_theme)
    return resolve_render_profile(
        timeline_path,
        assets_data,
        theme=active_theme,
        themes_root=REPO_ROOT / "themes",
    )
```

- Remotion-specific: **no** (core theme/profile). Annotated as `_RenderSettings`.
- Settings field actually read: **`theme_path` only**.
- Used by ffmpeg: **no**.
- Used by threejs: **yes**, passing `_ThreeSettings` (L388, L503).

### `_active_pack_order_for_provenance` — L460

```460:469:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py
def _active_pack_order_for_provenance() -> list[dict[str, Any]]:
    return [
        {
            "id": discovered.id,
            ...
        }
        for discovered in discover_pack_metadata(project_root=REPO_ROOT)
    ]
```

- Remotion-specific: **no**.
- Used by ffmpeg: **not directly**. Invoked only from `_render_provenance_payload`, which ffmpeg does call.

### `_resolved_theme_for_render` — L172

```172:175:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py
def _resolved_theme_for_render(
    timeline_path: Path,
    fallback_theme_path: Path,
) -> dict[str, Any]:
```

- Remotion-specific: **no** (`timeline.Timeline`, `timeline.resolve_timeline_theme`, `_theme_for_props` → `load_theme`).
- Used by ffmpeg: **no**. threejs uses it only via `_canonical_profile`.

### `_profile_mismatches` — L904

```904:917:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/run.py
def _profile_mismatches(
    requested: RenderProfile,
    canonical: RenderProfile,
) -> list[str]:
    requested_data = requested.to_dict()
    canonical_data = canonical.to_dict()
    mismatches: list[str] = []
    for field, expected in canonical_data.items():
        if field == "duration_tolerance":
            continue
        ...
    return mismatches
```

- Remotion-specific: **no**.
- Used by ffmpeg: **no**.
- threejs: **local copy**, not the remotion symbol. Body at `threejs/run.py` L298–311 is the same loop/`duration_tolerance` skip.

### `_reject_unknown_config`

**Does not exist** as a function anywhere in the repo.

Inlined in `_settings_from_request`:

- remotion L836–838
- threejs L251–253

Same pattern; message uses each file’s `BACKEND_ID`.

### `_parse_min_free_gb`

**Does not exist** as a function anywhere in the repo.

Inlined in `_settings_from_request`:

- remotion L860–868
- threejs L268–276

Bodies are the same (None / bool-or-non-number TypeError / `float` / negative ValueError).

## 4. ffmpeg aliases around L59

```53:64:/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/ffmpeg/run.py
from astrid.packs.rendering.backends.ffmpeg.support import (
    ALTERNATIVE_BACKENDS,
    BACKEND_ID,
    BACKEND_VERSION,
    support as strict_support,
)
from astrid.packs.rendering.backends.remotion import run as remotion_backend

# Compatibility spellings retained while callers migrate off the facade's
# historical private helper names.
_validate_ffmpeg_media_timeline = validate_ffmpeg_media_timeline
```

- Module alias: `run as remotion_backend`.
- Local alias only: `_validate_ffmpeg_media_timeline` ← `validate_ffmpeg_media_timeline` (ffmpeg `command.py`, not remotion).
- No `name = remotion_backend._name` block like threejs.

ffmpeg remotion call sites:

| Symbol | Lines |
|---|---|
| `_render_provenance_payload` | 149, 379, 579 |
| `_effective_registry_state` | 158, 388, 588 |
| `_render_provenance_sidecar_path` | 165, 412 |
| `_effect_registry_for_assets` | 300 |
| `_source_pack_id` | 359 |

## 5. `_reject_unknown_config` / `_parse_min_free_gb` search

`astrid/packs/rendering`: **0 hits** for either name. Whole workspace: **0 hits**.

Nearest same-body sites:

| Logic | remotion | threejs |
|---|---|---|
| unknown config vs `_CONFIG_KEYS` | L836–838 | L251–253 |
| `min_free_gb` parse | L860–868 | L268–276 |

`_CONFIG_KEYS` differ:

- remotion L74–76: `project_dir`, `composition_id`, `composition`, `theme_path`, `theme`, `min_free_gb`
- threejs L77: `project_dir`, `theme_path`, `min_free_gb`

Other unknown-config loops (different keys): `finalizers/ffmpeg/run.py:1001`, `planners/threejs_hybrid/run.py:358`, `planners/legacy_hybrid/run.py:396`.

## 6. `_canonical_profile` + settings types

**One definition:** remotion L887. threejs only aliases it.

`_RenderSettings` (remotion L80–84): `project_dir`, `composition_id`, `theme_path`, `min_free_gb`.

`_ThreeSettings` (threejs L90–93): `project_dir`, `theme_path`, `min_free_gb`. No `composition_id`.

`_canonical_profile` reads **`settings.theme_path` only**. `project_dir` / `composition_id` / `min_free_gb` unused here.

threejs calls: L388 (`support`), L503 (`render`) with `_ThreeSettings`. Runtime duck-type on `.theme_path`.

## 7. `backends/_shared` and `__init__.py`

`backends/_shared`: **absent**.

`__init__.py` under `backends/`:

- `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/ffmpeg/__init__.py`
- `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/remotion/__init__.py`
- `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/threejs/__init__.py`

No `backends/__init__.py`.

## 8. Cross-imports

| From | To | Fact |
|---|---|---|
| remotion/run.py | threejs | **no**. Only `from astrid.packs.rendering.backends.remotion import lock as remotion_lock`# Cleanup facts (exact (L66). |
|)

## A. 90 ffmpeg/run.py | rem kHz +otion | **yes**. L forced-AAC

**Paths59 `from astrid.packs.rendering. are `backends/`,backends.remotion import run not `remotion/run.py` / `threejs/run.py`.**

 as remotion_backend`.### Rem |
| threejs/runotion support.py — `/ | remotion | **yes**. L56 +Users/peteromalley/Documents/reigh-workspace 7 aliases/Astrid-threejs. |-cleanup/astrid/packs/rendering/backends/remotion/run.py` 1008–1024

```1008:1024:astrid/packs/rendering/backends/remotion/run.py
            # Remotion ALWAYS muxes an audio track (silent when the timeline
            # has none) and always muxes at the 90 kHz timescale; support must
            # describe the same contract render() implements.
            features["audio_ownership"] = AudioOwnership.RENDERED.value
            if request.audio is not None and request.audio is not AudioOwnership.RENDERED:
                reasons.append(
                    f"audio={request.audio.value!r} is incompatible with "
                    f"Remotion's always-rendered audio output"
                )
            if request.profile is not None:
                render_profile = replace(
                    canonical,
                    time_base=(1, 90000),
                    audio_codec=canonical.audio_codec or "aac",
                    audio_sample_rate=canonical.audio_sample_rate or 48000,
                    audio_channel_layout=canonical.audio_channel_layout or "stereo",
                )
```

### Remotion render — same file 1095–1109

```1095:1109:astrid/packs/rendering/backends/remotion/run.py
        declared_profile = request.profile or canonical
        # Remotion always muxes MP4 at the 90 kHz timescale regardless of the
        # input timeline's time base; the declared profile must match what the
        # renderer actually produces or strict validation rejects the output.
        declared_profile = replace(declared_profile, time_base=(1, 90000))
        # Remotion always muxes an audio track into its MP4 (silent when the
        # timeline has none), so ownership is effectively 'rendered' and the
        # declared profile must carry the AAC audio fields it always emits.
        ownership = AudioOwnership.RENDERED
        declared_profile = replace(
            declared_profile,
            audio_codec=declared_profile.audio_codec or "aac",
            audio_sample_rate=declared_profile.audio_sample_rate or 48000,
            audio_channel_layout=declared_profile.audio_channel_layout or "stereo",
        )
```

### Three.js helper — `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup/astrid/packs/rendering/backends/threejs/run.py` 314–321

```314:321:astrid/packs/rendering/backends/threejs/run.py
def _render_declared_profile(canonical: RenderProfile) -> RenderProfile:
    declared = replace(canonical, time_base=(1, 90000))
    return replace(
        declared,
        audio_codec=declared.audio_codec or "aac",
        audio_sample_rate=declared.audio_sample_rate or 48000,
        audio_channel_layout=declared.audio_channel_layout or "stereo",
    )
```

Used at **393** (`support` vs `_render_declared_profile(canonical)`) and **504** (`render`: `_render_declared_profile(request.profile or canonical)`).

### Semantically identical? **Field transform yes; application no.**

Same four fields: force `time_base=(1, 90000)`; `audio_codec or "aac"`; `audio_sample_rate or 48000`; `audio_channel_layout or "stereo"`.

Differences:
| Site | Applied to | Shape |
|---|---|---|
| Remotion `support` | `canonical` only, and only if `request.profile is not None` (mismatch check) | **one** `replace()` |
| Remotion `render` | `request.profile or canonical` (overwrites caller `time_base`) | **two** `replace()` |
| Three.js helper | same as remotion render when called from render; same as remotion support when called from support | two `replace()`, factored |

Support **rejects** a non-90kHz requested profile. Render **rewrites** it to 90kHz.

### Every `90000` / `video_track_timescale` / `settb` hit

**Literal `90000` (3, all production):**
- `astrid/packs/rendering/backends/threejs/run.py:315`
- `astrid/packs/rendering/backends/remotion/run.py:1020`
- `astrid/packs/rendering/backends/remotion/run.py:1099`

**Unrelated false positive:** `docs/architecture/timeline-event-sourcing/m6-reigh-sync.md:126` — migration timestamp `20260325090000_…`

**`video_track_timescale`:**
- `astrid/packs/rendering/finalizers/ffmpeg/run.py:648, 688` — `str(_mp4_timescale(target_profile))` (canonical FPS doubling, **not** 90000)
- `tests/core/rendering/test_threejs_hybrid.py:590` — **`"12288"`**
- `tests/packs/rendering/test_hyperframes_backend.py:492` — **`"12288"`**
- `tests/packs/rendering/test_ffmpeg_finalizer.py:715`

**`settb`:**
- `astrid/packs/rendering/finalizers/ffmpeg/run.py:581` — `filters.append(f"settb=expr={time_base}")`
- `tests/packs/rendering/test_ffmpeg_finalizer.py:397` — `assert f"settb=expr={target.time_base[0]}/{target.time_base[1]}" in filters`

### Tests vs 90000

**Zero tests contain `90000`.**  
Hybrid real-render asserts `video["time_base"] == "1/12288"` (`test_threejs_hybrid.py:828`). Three.js real-render never asserts `time_base`. Remotion unit test uses `time_base=(1, 15360)` (`test_remotion_backend.py:272`). Docs mention “90 kHz” at `docs/reference/threejs-renderer.md:117` without the integer.

---

## B. Remotion package versions

### `remotion/package.json` — all `@remotion/*` + `remotion`

Pinned **`4.0.455`**:
- deps: `@remotion/cli`, `@remotion/google-fonts`, `@remotion/layout-utils`, `@remotion/media`, `@remotion/renderer`, `@remotion/three`, `remotion`
- devDeps: `@remotion/bundler`

Also: `@react-three/fiber` `8.18.0`, `three` `0.185.1`, `@types/three` `0.185.4`.

### Root `package.json`

**No remotion deps.** Workspace marker only (`name: astrid-workspace`).

### `remotion/package-lock.json`

- `node_modules/@remotion/renderer`: **`4.0.455`** (`resolved` `…/renderer-4.0.455.tgz`)
- its dep **`extract-zip`: `2.0.1`** (lock `node_modules/extract-zip` version `2.0.1`)
- lockfile root + every other `@remotion/*` also **`4.0.455`**

### Chrome `VERSION` workaround

**No code.** Repo-wide search for `chrome-headless-shell`, `mac-arm64`, `mac-arm64/VERSION`, writing a `VERSION` marker: **no hits**.

Only mention — `docs/reference/threejs-renderer.md:63-65`:

> 2. **Chrome Headless Shell** — `@remotion/renderer` downloads its bundled Chrome Headless Shell into `remotion/node_modules/.remotion/`. Do not depend on system Chrome or Playwright caches.

---

## C. Test helpers

**`tests/packs/rendering/_helpers.py` does not exist.**

### `_missing_environment` — only in threejs backend (hybrid imports it)

```62:80:tests/packs/rendering/test_threejs_backend.py
def _missing_environment() -> list[str]:
    missing = [
        f"{binary} executable"
        for binary in ("node", "npx", "ffprobe")
        if shutil.which(binary) is None
    ]
    node_modules = REMOTION_PROJECT / "node_modules"
    if not node_modules.is_dir():
        missing.append("remotion/node_modules")
    for package in ("three", "@remotion/three", "@react-three/fiber"):
        if not (node_modules / package).is_dir():
            missing.append(f"remotion/node_modules/{package}")
    # The transport spawns `python3` from PATH; the active interpreter must
    # carry the banodoco timeline schema or timeline serialization is refused.
    try:
        import banodoco_timeline_schema  # noqa: F401
    except ImportError:
        missing.append("banodoco_timeline_schema for the active python3")
    return missing
```

Remotion **drifted name + thinner check** (`test_remotion_backend.py:945-954`): same `node`/`npx`/`ffprobe` + `remotion/node_modules` only; **no** `three` / `@remotion/three` / `@react-three/fiber` / `banodoco_timeline_schema`.

Hybrid: `from tests.packs.rendering.test_threejs_backend import _missing_environment` (`test_threejs_hybrid.py:663`).

### `_execution_env`

Threejs (`106-114`) wraps `_child_path_on_front`:

```105:114:tests/packs/rendering/test_threejs_backend.py
@contextmanager
def _execution_env():
    node_bin = (
        str(Path(shutil.which("node")).resolve().parent)
        if shutil.which("node")
        else ""
    )
    python_bin = str(Path(sys.executable).resolve().parent)
    with _child_path_on_front(*[d for d in (python_bin, node_bin) if d]):
        yield
```

Hybrid (`673-690`) and remotion `_remotion_execution_env` (`966-983`) **inline the same PATH join**; remotion is rename-only vs hybrid. Threejs is **not** byte-identical (uses `_child_path_on_front`).

### `_probe` — **drifted**

Threejs (`566-584`): no `-count_frames`; entries `stream=codec_name,codec_type,width,height,pix_fmt,avg_frame_rate,duration` (no `time_base` / `nb_read_frames`).

Hybrid (`693-712`): `-count_frames`; `stream=…pix_fmt,time_base,avg_frame_rate,nb_read_frames` (no stream `duration`).

Remotion backend: **no `_probe`**.

### `_frame_md5` — **byte-identical** (threejs `587-607` == hybrid `715-735`)

```587:607:tests/packs/rendering/test_threejs_backend.py
def _frame_md5(path: Path, frame: int) -> str:
    out = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            f"select=eq(n\\,{frame})",
            "-frames:v",
            "1",
            "-f",
            "md5",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out.strip().split("=")[-1].strip()
```

### `_source_video` — **not in threejs/remotion backends**; hybrid vs hyperframes **drifted**

Hybrid `561-598`: lavfi color **+** `anullsrc` + `-shortest` + `-c:a aac` + `-video_track_timescale 12288`.

Hyperframes `470-500`: video-only (no audio) + same `12288`.

---

## D. Exact pytest paths

| Suite | Path |
|---|---|
| renderer parity | `tests/packs/test_renderer_parity.py` (`make renderer-parity` → `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py`) |
| legacy characterization | `tests/packs/rendering/test_legacy_renderer_characterization.py` |
| Three.js backend | `tests/packs/rendering/test_threejs_backend.py` |
| Remotion backend | `tests/packs/rendering/test_remotion_backend.py` |
| FFmpeg backend | `tests/packs/rendering/test_ffmpeg_backend.py` |
| related ffmpeg | `tests/packs/rendering/test_ffmpeg_support.py`, `tests/packs/rendering/test_ffmpeg_finalizer.py` |
| Three.js hybrid | `tests/core/rendering/test_threejs_hybrid.py` |
| legacy hybrid | `tests/core/rendering/test_legacy_hybrid.py` |
| hyperframes | `tests/packs/rendering/test_hyperframes_backend.py` |
| core rendering dir | `tests/core/rendering/` (29 test modules: `test_artifacts.py`, `test_assets.py`, `test_attached_render.py`, `test_caller_overrides.py`, `test_cli.py`, `test_cli_contract.py`, `test_conformance.py`, `test_contracts.py`, `test_freeze.py`, `test_generic_code_audit.py`, `test_legacy_hybrid.py`, `test_output_name.py`, `test_package_data.py`, `test_production_callers.py`, `test_profile.py`, `test_provenance.py`, `test_publication.py`, `test_raw_command_fixture.py`, `test_registry.py`, `test_registry_matrix.py`, `test_replay.py`, `test_replay_bundle.py`, `test_scaffold.py`, `test_scaffold_install.py`, `test_schema_roundtrip.py`, `test_service.py`, `test_threejs_hybrid.py`, `test_transport.py`) |

---

## E. Ruff gating

**Not a hard `ruff check` fail.** Count vs baseline **1469**.

- `Makefile:30-32`: `$(PY) scripts/reshape/compare_ruff_baseline.py`
- Script runs: `python -m ruff check . --output-format json` (`scripts/reshape/compare_ruff_baseline.py:12-20`)
- Pass iff `current_count <= baseline_count` (`57-59`)
- Baseline: `scripts/reshape/baselines/ruff_astrid.json` → `"finding_count": 1469`
- CI: same script in `scripts/reshape/run_ci_checks.sh:252` and `:352`
- Pinned tool: `pyproject.toml` `ruff==0.12.0`; lint select `E4,E7,E9,F,I,BLE`; include `astrid/**`, `scripts/reshape/**`, `tests/reshape/**`, two concurrency test files

---

## F. Chrome cache / VERSION file

- `remotion/node_modules` **not present** (renderer package.json missing).
- `remotion/node_modules/.remotion` **does not exist**.
- `remotion/node_modules/.remotion/chrome-headless-shell/mac-arm64/VERSION` **does not exist**.
- No VERSION marker file checked into the repo. No postinstall/workaround script.# Three.js cleanup plan

Goal: remove real duplication/fragility. No re-architecture. Four commits, in this order.

Hard rails: no `astrid/core/` edits, no `pack.yaml`, no `test_production_callers` allowlist, no `tests/test_schema_contract.py`. `_shared` imports **only** `astrid.core`. `make cycles` will not catch a pack cycle — grep it yourself.

---

## C0 — Extract backend-neutral helpers (F2 + F4 production)

**Why:** `threejs/run.py:56-67` imports remotion’s whole `run` module for 7 names. 6 are core-only. `_canonical_profile` is typed on remotion’s private `_RenderSettings` and only reads `.theme_path`; threejs duck-types `_ThreeSettings`. `_profile_mismatches` is byte-identical (`threejs:298-311` = `remotion:904-917`).

**Create** `astrid/packs/rendering/backends/_shared/__init__.py` (no `backends/__init__.py`). Move these as a literal cut, no behavior change:

| Move | From | Notes |
|---|---|---|
| `_input_path` | remotion:817 | 3 lines |
| `_load_registry_mapping` | remotion:878 | |
| `_serialize_timeline` | remotion:126 | |
| `_duration_frames` | remotion:1051 | path+profile form; do **not** unify with ffmpeg’s probe-form |
| `_canonical_profile` | remotion:887 | **retype** 3rd arg `settings: _RenderSettings` → `theme_path: Path \| None`. Body already only reads `settings.theme_path` |
| `_render_provenance_payload` | remotion:483 | **payload keys unchanged** |
| deps: `_resolve_theme_path`, `_theme_for_props`, `_theme_slug_for_render_default`, `_resolved_theme_for_render` | remotion:134-195 | needed by `_canonical_profile` |
| deps: `_active_pack_order_for_provenance`, `_active_theme_for_provenance` | remotion:460, 472 | needed by provenance |
| `_profile_mismatches` | remotion:904 / threejs:298 | delete threejs copy |
| `_parse_min_free_gb(value) -> float \| None` | **new**, body = remotion:860-868 = threejs:268-276 | |
| `_reject_unknown_config(config, allowed, backend_id)` | **new**, body = remotion:836-838 = threejs:251-253 | remotion+threejs settings only |

**Call-site rewires**

- `remotion/run.py`: `from astrid.packs.rendering.backends._shared import …` and keep the same private names bound in-module (legacy_engine + tests patch `remotion._X`). Call `_canonical_profile(..., settings.theme_path)`. Use the two new config helpers inside `_settings_from_request`.
- `threejs/run.py`: import the 6 neutrals + `_profile_mismatches` + config helpers from `_shared`. Keep **only** `_execute_remotion = remotion_backend._execute_remotion`. Delete local `_profile_mismatches`. `_canonical_profile(..., settings.theme_path)` at :388 and :503. Identity assert at `test_threejs_backend.py:790` stays valid.
- `legacy_engine.py`: **do not touch** (26 remotion aliases keep working via re-export).
- `ffmpeg/run.py`: **do not retarget** `_render_provenance_payload` — `test_ffmpeg_support.py:478` patches `ffmpeg.remotion_backend._render_provenance_payload`; ffmpeg still needs remotion for `_effective_registry_state`, `_effect_registry_for_assets`, `_source_pack_id`, `_render_provenance_sidecar_path`.

**Verify C0**

```bash
# _shared must not import any pack
rg -n "from astrid\.packs|import astrid\.packs" astrid/packs/rendering/backends/_shared
# must be empty

pytest -q \
  tests/packs/rendering/test_threejs_backend.py \
  tests/packs/rendering/test_remotion_backend.py \
  tests/packs/rendering/test_remotion_locking.py \
  tests/packs/rendering/test_ffmpeg_backend.py \
  tests/packs/rendering/test_ffmpeg_support.py \
  tests/packs/rendering/test_legacy_renderer_characterization.py \
  tests/packs/test_renderer_parity.py \
  tests/core/rendering
python3 scripts/reshape/compare_ruff_baseline.py   # count must stay ≤ 1469
```

---

## C1 — Dedup the 90 kHz + AAC mux profile (F3)

**Depends on C0.** Do **not** delete anything until the probe.

**Why:** same four-field transform in three places:

- remotion support `:1017-1024` (one `replace` on `canonical`, mismatch check)
- remotion render `:1095-1109` (two `replace`s on `request.profile or canonical`)
- threejs `_render_declared_profile` `:314-321` (used at support `:393` and render `:504`)

Zero tests assert `90000`. `artifacts.py:279,386` **does** compare `time_base` — a wrong declared profile fails strict validation.

**C1a — extract only**

Add to `_shared`:

```python
def _remotion_mux_profile(profile: RenderProfile) -> RenderProfile:
    return replace(
        profile,
        time_base=(1, 90000),
        audio_codec=profile.audio_codec or "aac",
        audio_sample_rate=profile.audio_sample_rate or 48000,
        audio_channel_layout=profile.audio_channel_layout or "stereo",
    )
```

Replace the three sites. Delete threejs `_render_declared_profile`. Remotion re-exports the name. Re-run the C0 pytest block.

**C1b — probe a RAW backend artifact** (not hybrid, not finalized)

Hybrid `:828` asserting `1/12288` is the **finalizer** output (`-video_track_timescale` / `settb` in `finalizers/ffmpeg/run.py:581,648,688`). Source fixtures also bake `12288`. That is not Remotion’s mux.

```bash
# use an existing real-render test output, or one-shot:
#   backend="rendering.remotion"  or  backend="rendering.threejs"
ffprobe -v error -show_entries stream=codec_type,codec_name,time_base,sample_rate,channel_layout -of json <raw.mp4>
```

| Video `time_base` | Audio | Action |
|---|---|---|
| `1/90000` | aac 48k stereo | **KEEP** helper as-is |
| `1/12288` | aac 48k stereo | delete **only** `time_base=(1, 90000)`; keep AAC defaults |
| `1/90000` | none | delete AAC defaults; keep time_base (unlikely) |
| `1/12288` | none | delete the whole helper |

If you delete `time_base` force, also edit `docs/reference/threejs-renderer.md:117` (“90 kHz declared timescale”). If you keep it, leave the doc.

**Verify C1:** same C0 pytest block. If a real-render env is present, also:

```bash
pytest -q \
  tests/packs/rendering/test_remotion_backend.py::test_remotion_real_render_under_global_angle_keeps_identity \
  tests/packs/rendering/test_threejs_backend.py::test_threejs_real_render_text_timeline_through_public_service \
  tests/core/rendering/test_threejs_hybrid.py
```

---

## C2 — Test helper collapse (F4 tests)

**Independent of C0/C1.** New `tests/packs/rendering/_helpers.py`.

| Helper | Action |
|---|---|
| `_execution_env` | one PATH prepend (python bin + node bin). Replaces threejs `:106`, remotion `_remotion_execution_env` `:967`, hybrid `:674`. Inline threejs `_child_path_on_front` into it; delete that helper |
| `_frame_md5` | verbatim ×2 (threejs `:587` = hybrid `:715`) → share |
| `_probe` | drifted; ship the **hybrid superset** (`-count_frames` + `time_base,nb_read_frames`). threejs extra `duration` keys are unused |
| `_source_video(tmp_path, *, audio=False)` | hyperframes `:470` video-only vs hybrid `:561` +aac. `audio=True` is the hybrid body |

Rewire: `test_threejs_backend.py`, `test_remotion_backend.py`, `tests/core/rendering/test_threejs_hybrid.py`, `test_hyperframes_backend.py`. Hybrid already does `from tests.packs.rendering.test_threejs_backend import _missing_environment` — keep that (env-skip stays put).

**Verify C2**

```bash
pytest -q \
  tests/packs/rendering/test_threejs_backend.py \
  tests/packs/rendering/test_remotion_backend.py \
  tests/packs/rendering/test_hyperframes_backend.py \
  tests/core/rendering/test_threejs_hybrid.py
python3 scripts/reshape/compare_ruff_baseline.py
```

---

## C3 — Pin `@remotion/*` to 4.0.509 (F1)

**Independent. Last, so a bad bump reverts in one commit.**

Root cause is upstream: `@remotion/renderer@4.0.455` → `extract-zip@2.0.1`, broken on Node ≥26 (remotion#7409). Fixed in 4.0.509 (PR #7420). CI is Node 20 + typecheck only — it will not catch a render regression.

**Change**

- `remotion/package.json`: pin all eight to `4.0.509` — `@remotion/cli`, `google-fonts`, `layout-utils`, `media`, `renderer`, `three`, `remotion`, `@remotion/bundler`
- regenerate `remotion/package-lock.json` via `cd remotion && npm install` (not `npm ci`)
- confirm lock no longer depends on `extract-zip`
- `docs/reference/threejs-renderer.md:51` table: `@remotion/three` `4.0.509`
- `astrid/packs/rendering/skill/SKILL.md:123`: “Requires Remotion 4.0.509 (pinned)”

Do **not** add/remove a `chrome-headless-shell/VERSION` marker — none exists in the repo; the epic workaround was a local cache file. Existing local shells stay valid. Fresh checkouts get a working extract from 4.0.509.

**Verify C3**

```bash
cd remotion && npm run typecheck
pytest -q \
  tests/packs/rendering/test_remotion_locking.py \
  tests/packs/rendering/test_remotion_backend.py::test_remotion_real_render_under_global_angle_keeps_identity \
  tests/packs/rendering/test_threejs_backend.py::test_threejs_real_render_text_timeline_through_public_service \
  tests/packs/rendering/test_threejs_backend.py::test_threejs_real_render_empty_timeline_through_public_service \
  tests/packs/test_renderer_parity.py
make remotion-typecheck
make renderer-parity
```

---

## Explicit LEAVE

| Item | Why |
|---|---|
| `_execute_remotion` in remotion | lock + `npx remotion render`. The one honest remotion helper threejs should keep |
| ffmpeg → remotion import (4 remotion-specific helpers + provenance patch target) | retarget adds test churn, does not shrink a cycle |
| `legacy_engine.py` remotion aliases | re-exports preserve them; 26-name retarget is YAGNI |
| Extra `_input_path` copies (ffmpeg/run.py:67, ffmpeg/command.py:90, planners, finalizer) | 3-line fn; not the coupling problem |
| ffmpeg `_duration_frames(probe, profile)` | different signature |
| Planner/finalizer unknown-config 3-liners | raise vs reasons; different key sets |
| Full settings parsers | `composition_id` / theme-slug logic is backend-specific |
| Env-skip trio (`_missing_environment` vs `_remotion_missing_environment`) | genuinely divergent (three-package scan vs node_modules-only vs nvm) |
| Inline per-backend assertions | not duplication |
| Dead-code hunt | none remains |
| Chrome `VERSION` marker | not in repo; bump kills the root cause |
| `html_canvas_effect` `remotion_min_version: 4.0.455` | minimum for `HtmlInCanvas`, still true |
| ffmpeg 90000 | never hardcodes; probes |
| `tests/test_schema_contract.py` | pre-existing failures |
| `astrid/core/**`, `pack.yaml`, production-callers allowlist | constraints. `_shared` sits under `backends/` → auto-exempt via `_BACKEND_IMPL_PREFIX` |
| Shared settings dataclass / new abstraction layer | more machinery than it removes |

---

## Final gate (after C3)

```bash
pytest -q \
  tests/packs/test_renderer_parity.py \
  tests/packs/rendering/test_legacy_renderer_characterization.py \
  tests/packs/rendering/test_threejs_backend.py \
  tests/packs/rendering/test_remotion_backend.py \
  tests/packs/rendering/test_ffmpeg_backend.py \
  tests/core/rendering
make ruff
make remotion-typecheck
make renderer-parity
rg -n "from astrid\.packs|import astrid\.packs" astrid/packs/rendering/backends/_shared   # empty
```

---

## Risks

- **90000 delete without a raw probe** is the one way to silently break validation. `artifacts.py` compares `time_base`. Hybrid `1/12288` is the wrong signal. Sequence C1a → probe → C1b.
- **Provenance shape:** `_render_provenance_payload` must be a literal move. Catch: `test_legacy_renderer_characterization.py` (`test_render_provenance_v1_key_set`, hybrid segment keys), remotion registry provenance tests, threejs/remotion sidecar asserts.
- **`_canonical_profile` signature:** only remotion/threejs call it (plus a remotion mock). No other callers.
- **Patch targets:** remotion re-exports keep `patch.object(remotion, "_canonical_profile")` etc. working. Do not make threejs import remotion for those names or identity asserts will lie.
- **4.0.509 CLI drift** in `_execute_remotion` (`npx remotion render` flags). Catch with `test_remotion_locking.py` + the two real-render tests. Typecheck will not catch it.
- **Ruff:** new `_shared/__init__.py` and `_helpers.py` must be clean (`I,F,E4,E7,E9,BLE`). Gate is `current ≤ 1469`, not zero.
- **Wheel:** `_shared/__init__.py` auto-packs. No packaging edit.
