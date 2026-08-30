"""Golden parity test for the storyboard→timeline compiler (plan v8 B2 / brief E2).

Asserts the frozen astrid-intro parity invariants on a 25-section fixture
built programmatically from ``tests/fixtures/storyboard-minimal.json`` (the
committed intro fixture ``build/fixtures/storyboard-intro.json`` is a build
artifact and is not present in the checkout): 25 image imports + 25 audio
imports → 50 registry assets, EXACTLY 3 clips per section + 1 brand wordmark
→ 76 clips, and a total duration ≥177 s within ±0.5 s of the plan sum. The
timing numbers are the real astrid-intro ``build/segments/plan.json`` values
(25 segments, total 177.53 s), so the compiled total reproduces the golden
build's 177.53 s.

The kernel SDK import path is monkeypatched with temp-file-backed fake
receipts (bytes hashed, files copied into a temp CAS directory), so the
compile runs without touching the kernel database, the network, or any paid
call.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from astrid.core.storyboard import StoryboardError
from astrid.core.timeline.banodoco_schema import canonical_timeline_config
from astrid.core.timeline.validators.registry import validate_registry
from scripts import build_storyboard as bs

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MINIMAL = FIXTURES / "storyboard-minimal.json"
ASSET_DIR = FIXTURES / "storyboard-assets"

# Real astrid-intro plan.json segments (slug, start seconds, duration seconds).
# Section ids hyphenate the slugs (the loader's id grammar is ^[a-z0-9-]+$).
_PLAN_SEGMENTS: tuple[tuple[str, float, float], ...] = (
    ("open", 0.0, 5.314),
    ("two_ideas", 5.664, 1.611),
    ("recap1", 7.625, 5.297),
    ("recap2", 13.271, 4.995),
    ("idea1_intro", 18.617, 6.761),
    ("idea1_os", 25.727, 3.335),
    ("idea1_vc", 29.413, 7.525),
    ("idea1_more", 37.287, 6.734),
    ("idea1_mm", 44.371, 12.565),
    ("idea1_data", 57.286, 8.495),
    ("idea1_defaults", 66.131, 6.503),
    ("idea2_intro", 72.984, 4.749),
    ("idea2_bestprac", 78.083, 8.698),
    ("idea2_contribute", 87.13, 14.701),
    ("example_intro", 102.181, 2.464),
    ("ex_desert", 104.995, 5.418),
    ("ex_flux", 110.763, 4.954),
    ("ex_gpt", 116.067, 5.699),
    ("ex_minimax", 122.116, 3.296),
    ("ex_glitch", 125.761, 4.705),
    ("ex_match", 130.816, 9.726),
    ("ex_map", 140.892, 9.072),
    ("ex_prompts", 150.314, 7.649),
    ("cta_agents", 158.313, 9.418),
    ("cta", 168.081, 9.099),
)
_PLAN_TOTAL = 177.53
_SHA256_RE = re.compile(r"[0-9a-f]{64}")

# Probed wav durations for the cumulative (no-plan) timing test.
_PROBE_DURATIONS = {"open.wav": 2.0, "idea-1.wav": 1.5}


def _section_id(slug: str) -> str:
    return slug.replace("_", "-")


def _plan() -> dict[str, Any]:
    return {
        "segments": [
            {
                "index": index,
                "slug": _section_id(slug),
                "text": f"VO for {_section_id(slug)}.",
                "start": start,
                "duration": duration,
            }
            for index, (slug, start, duration) in enumerate(_PLAN_SEGMENTS)
        ],
        "total": _PLAN_TOTAL,
    }


def _story_fixture(root: Path, count: int = 25) -> Path:
    """Write a *count*-section storyboard under ``root/build`` with assets beside it.

    Sections alternate between the minimal fixture's two shapes: the ``open``
    template (single asset variant, active) and the ``idea-1`` template
    (asset + gen variant with ``active_index`` on the gen one), so both
    variant sources are exercised across the golden run.
    """
    minimal = json.loads(MINIMAL.read_text(encoding="utf-8"))
    open_section, idea_section = minimal["sections"]
    assets_dir = root / "build" / "storyboard-assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for source in ASSET_DIR.iterdir():
        if source.is_file():
            shutil.copy2(source, assets_dir / source.name)
    sections = []
    for index in range(count):
        slug = _section_id(_PLAN_SEGMENTS[index % len(_PLAN_SEGMENTS)][0])
        template = json.loads(json.dumps(open_section if index % 2 == 0 else idea_section))
        template["id"] = slug
        template["vo"] = {
            "text": f"VO for {slug}.",
            "audio": {
                "asset": "storyboard-assets/open.wav"
                if index % 2 == 0
                else "storyboard-assets/idea-1.wav"
            },
        }
        sections.append(template)
    story = {**minimal, "sections": sections}
    path = root / "build" / "storyboard.json"
    path.write_text(json.dumps(story, indent=2) + "\n", encoding="utf-8")
    return path


class _FakeKernelImports:
    """Monkeypatch stand-in for ``sdk_import_asset``: temp files, real hashes.

    Copies each imported file into a temp CAS directory and returns a receipt
    with the genuine sha256 of its bytes — no kernel, no network.
    """

    def __init__(self, cas_dir: Path) -> None:
        self.cas_dir = cas_dir
        self.calls: list[tuple[Path, str]] = []

    def __call__(self, path: Path, *, project: str = bs.DEFAULT_PROJECT) -> bs.AssetImport:
        self.calls.append((Path(path), project))
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        staged = self.cas_dir / f"{len(self.calls):03d}_{Path(path).name}"
        self.cas_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, staged)
        return bs.AssetImport(
            file=str(staged), content_sha256=digest, media_id=f"media-{digest[:12]}"
        )


def _fake_probe(path: Path) -> float:
    return _PROBE_DURATIONS[Path(path).name]


@pytest.fixture()
def fake_kernel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _FakeKernelImports:
    fake = _FakeKernelImports(tmp_path / "cas")
    monkeypatch.setattr(bs, "sdk_import_asset", fake)
    return fake


def _by_track(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for clip in config["clips"]:
        grouped.setdefault(clip["track"], []).append(clip)
    return grouped


# ---------------------------------------------------------------------------
# Golden parity: 25 sections → 50 assets / 76 clips / 177.53 s
# ---------------------------------------------------------------------------

def test_golden_parity_counts_and_timing(
    tmp_path: Path, fake_kernel: _FakeKernelImports
) -> None:
    story_path = _story_fixture(tmp_path)
    original_bytes = story_path.read_bytes()
    story = json.loads(original_bytes)
    config, registry, report = bs.compile_storyboard(
        story, base_dir=story_path.parent, plan=_plan()
    )

    # --- tracks and clip counts -------------------------------------------
    assert [track["id"] for track in config["tracks"]] == [
        "brand",
        "captions",
        "broll",
        "a1",
    ]
    assert {track["id"]: track["kind"] for track in config["tracks"]} == {
        "brand": "visual",
        "captions": "visual",
        "broll": "visual",
        "a1": "audio",
    }
    clips = config["clips"]
    assert len(clips) == 76  # 25×3 + 1 brand
    grouped = _by_track(config)
    assert {track: len(items) for track, items in grouped.items()} == {
        "brand": 1,
        "captions": 25,
        "broll": 25,
        "a1": 25,
    }

    # --- managed imports: 25 images + 25 audio, no kernel fallback ---------
    assert len(fake_kernel.calls) == 50
    assert sum(1 for path, _ in fake_kernel.calls if path.suffix == ".png") == 25
    assert sum(1 for path, _ in fake_kernel.calls if path.suffix == ".wav") == 25
    assert {project for _, project in fake_kernel.calls} == {bs.DEFAULT_PROJECT}

    # --- registry: 50 assets with CAS file + sdk-returned digest ----------
    assets = registry["assets"]
    assert len(assets) == 50
    assert sum(1 for key in assets if key.startswith("img_")) == 25
    assert sum(1 for key in assets if key.startswith("vo_")) == 25
    for key, entry in assets.items():
        assert Path(entry["file"]).is_file(), key
        assert _SHA256_RE.fullmatch(entry["content_sha256"]), key
        assert entry["type"] == ("image" if key.startswith("img_") else "audio")
        assert entry["origin"] in {
            "immutable-public",
            "refreshable-from-generation",
        }

    # --- per-section clip semantics (verbatim caption, frozen styling) ----
    for index, (slug, start, duration) in enumerate(_PLAN_SEGMENTS):
        sid = _section_id(slug)
        vo_clip = grouped["a1"][index]
        cap = grouped["captions"][index]
        broll = grouped["broll"][index]
        assert vo_clip["id"] == f"vo_{sid}"
        assert vo_clip["asset"] == f"vo_{sid}"
        assert vo_clip["at"] == pytest.approx(start)
        assert vo_clip["from"] == 0.0
        assert vo_clip["to"] == pytest.approx(duration)
        assert cap["id"] == f"cap_{sid}"
        assert cap["text"]["content"] == story["sections"][index]["vo"]["text"]
        assert cap["text"]["fontSize"] == 30
        assert cap["params"]["weight"] == 500
        assert cap["params"]["anchor"] == "bottom-center"
        assert cap["params"]["offsetY"] == 56
        assert cap["params"]["maxWidth"] == 1500
        assert cap["effects"] == {"fade_in": 0.2, "fade_out": 0.2}
        assert cap["hold"] == pytest.approx(duration + bs.GAP)
        assert cap["at"] == pytest.approx(start)
        assert broll["id"] == f"broll_{sid}"
        assert broll["asset"] == f"img_{sid}"
        # FFmpeg media clips use bounded source windows; ``hold`` is not a
        # valid still-image duration semantic at the renderer boundary.
        assert broll["from"] == 0.0
        assert broll["to"] == pytest.approx(duration + bs.GAP)
        assert "hold" not in broll
        assert broll["at"] == pytest.approx(start)
        # Gen-variant sections carry generative provenance; baked ones do not.
        if index % 2 == 1:
            assert broll["generation"]["prompt"] == story["sections"][index]["image"][
                "variants"
            ][1]["prompt"]
            assert broll["generation"]["generator"] == "flux-schnell"
        else:
            assert "generation" not in broll

    # --- clip order: brand first, then per-section vo/cap/broll ------------
    assert clips[0]["id"] == "brand_wordmark"
    assert [clip["id"] for clip in clips[1:4]] == ["vo_open", "cap_open", "broll_open"]

    # --- brand wordmark: one clip at the head, held for the total ----------
    brand = grouped["brand"][0]
    assert brand["at"] == 0.0
    assert brand["text"]["content"] == "ASTRID"
    assert brand["params"]["anchor"] == "top-right"
    total = brand["hold"]
    assert total >= 177.0
    assert abs(total - _PLAN_TOTAL) <= 0.5

    # --- frozen contracts hold on the compiled output ----------------------
    assert canonical_timeline_config(config) is not None
    validate_registry(registry)

    # --- resolution report: slug → resolved variants, stdout-only ----------
    assert set(report["sections"]) == {_section_id(slug) for slug, _, _ in _PLAN_SEGMENTS}
    assert report["clips"] == 76
    assert report["assets"] == 50
    assert abs(report["total_duration"] - _PLAN_TOTAL) <= 0.5
    for slug, _, _ in _PLAN_SEGMENTS:
        sid = _section_id(slug)
        section_report = report["sections"][sid]
        assert section_report["image"]["asset_key"] == f"img_{sid}"
        assert _SHA256_RE.fullmatch(section_report["image"]["content_sha256"])
        assert section_report["vo"] is not None
        assert section_report["vo"]["asset_key"] == f"vo_{sid}"
        assert section_report["vo"]["origin"]["prompt"] == f"VO for {sid}."
        assert section_report["vo"]["duration"] == pytest.approx(
            dict(((s, d) for s, _, d in _PLAN_SEGMENTS))[slug]
        )

    # --- the storyboard file is never written back --------------------------
    assert story_path.read_bytes() == original_bytes


def test_cumulative_timing_without_plan(
    tmp_path: Path, fake_kernel: _FakeKernelImports, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bs, "probe_wav_duration", _fake_probe)
    story_path = _story_fixture(tmp_path, count=3)
    story = json.loads(story_path.read_text())
    config, registry, report = bs.compile_storyboard(
        story, base_dir=story_path.parent
    )

    # 3 sections × 3 clips + brand = 10 clips; durations from the probe.
    assert len(config["clips"]) == 10
    grouped = _by_track(config)
    durations = [2.0, 1.5, 2.0]
    starts = [0.0]
    for duration in durations[:-1]:
        starts.append(round(starts[-1] + duration + bs.GAP, 3))
    for index, (start, duration) in enumerate(zip(starts, durations)):
        assert grouped["a1"][index]["at"] == pytest.approx(start)
        assert grouped["a1"][index]["to"] == pytest.approx(duration)
        assert grouped["broll"][index]["at"] == pytest.approx(start)
        assert grouped["broll"][index]["from"] == 0.0
        assert grouped["broll"][index]["to"] == pytest.approx(duration + bs.GAP)
        assert "hold" not in grouped["broll"][index]
    expected_total = round(starts[-1] + durations[-1] + bs.GAP, 3)
    assert grouped["brand"][0]["hold"] == pytest.approx(expected_total)
    assert report["total_duration"] == pytest.approx(expected_total)
    # Probed durations land on the VO registry entries, in section order.
    for index, section in enumerate(story["sections"]):
        entry = registry["assets"][f"vo_{section['id']}"]
        assert entry["duration"] == pytest.approx(durations[index])


def test_section_without_vo_compiles_broll_plate_only(
    tmp_path: Path, fake_kernel: _FakeKernelImports
) -> None:
    story_path = _story_fixture(tmp_path, count=1)
    story = json.loads(story_path.read_text())
    del story["sections"][0]["vo"]
    config, registry, report = bs.compile_storyboard(
        story, base_dir=story_path.parent
    )

    assert len(config["clips"]) == 2  # brand + lone broll plate
    broll = [clip for clip in config["clips"] if clip["track"] == "broll"]
    assert len(broll) == 1
    assert broll[0]["from"] == 0.0
    assert broll[0]["to"] == pytest.approx(story["meta"]["timing"]["default_hold"])
    assert "hold" not in broll[0]
    assert "captions" not in _by_track(config)
    assert "a1" not in _by_track(config)
    assert len(registry["assets"]) == 1  # image only
    assert report["sections"]["open"]["vo"] is None


def test_plan_missing_section_fails_closed(
    tmp_path: Path, fake_kernel: _FakeKernelImports
) -> None:
    story_path = _story_fixture(tmp_path, count=3)
    story = json.loads(story_path.read_text())
    plan = _plan()
    plan["segments"] = plan["segments"][:2]  # drops the third section's segment
    with pytest.raises(StoryboardError) as exc_info:
        bs.compile_storyboard(story, base_dir=story_path.parent, plan=plan)
    assert "no segment for section 'recap1'" in str(exc_info.value)


def test_import_failure_has_no_file_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    story_path = _story_fixture(tmp_path, count=1)
    story = json.loads(story_path.read_text())

    def failing_import(path: Path, *, project: str = "x") -> bs.AssetImport:
        raise StoryboardError([f"managed import failed for {path}: unavailable: locked"])

    monkeypatch.setattr(bs, "sdk_import_asset", failing_import)
    with pytest.raises(StoryboardError, match="managed import failed"):
        bs.compile_storyboard(story, base_dir=story_path.parent)

def test_cli_probe_failure_reports_clean_error(
    tmp_path: Path,
    fake_kernel: _FakeKernelImports,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An undecodable wav (no plan) exits 2 with one error line, not a traceback."""
    story_path = _story_fixture(tmp_path, count=1)

    def failing_probe(path: Path) -> float:
        raise subprocess.CalledProcessError(
            1, ["ffprobe", str(path)], stderr="Invalid data found"
        )

    monkeypatch.setattr(bs, "probe_wav_duration", failing_probe)
    exit_code = bs.main(
        ["compile", "--story", str(story_path), "--out", str(tmp_path / "out")]
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("error: ")
    assert "ffprobe" in captured.err
    assert not (tmp_path / "out" / "timeline.json").exists()


def test_cli_compile_writes_sidecars_and_report(
    tmp_path: Path,
    fake_kernel: _FakeKernelImports,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    story_path = _story_fixture(tmp_path)
    # The fixture wavs are 0-byte placeholders: probe durations deterministically
    # (the compile runs without a plan, so the wav probe path is live).
    monkeypatch.setattr(bs, "probe_wav_duration", _fake_probe)
    out_dir = tmp_path / "out"

    exit_code = bs.main(
        ["compile", "--story", str(story_path), "--out", str(out_dir)]
    )
    assert exit_code == 0
    timeline = json.loads((out_dir / "timeline.json").read_text(encoding="utf-8"))
    registry = json.loads((out_dir / "assets.json").read_text(encoding="utf-8"))
    assert len(timeline["clips"]) == 76
    assert len(registry["assets"]) == 50
    report = json.loads(capsys.readouterr().out)
    assert report["clips"] == 76
    assert report["assets"] == 50

    # Default output dir is <story dir>/../timeline; relative story paths work.
    monkeypatch.chdir(tmp_path)
    exit_code = bs.main(["compile", "--story", "build/storyboard.json"])
    assert exit_code == 0
    default_out = tmp_path / "timeline"  # <story dir>/../timeline = tmp/timeline
    assert (default_out / "timeline.json").is_file()
    assert (default_out / "assets.json").is_file()


def test_render_passthrough_invokes_sdk_capability() -> None:
    recorded: dict[str, Any] = {}

    class _StubClient:
        def invoke_result(self, capability_id: str, **kwargs: Any) -> Any:
            recorded["capability_id"] = capability_id
            recorded.update(kwargs)

            class _Result:
                ok = False
                run_id = None
                kernel_run_id = None
                outputs = None
                error = {"code": "ownership", "message": "not project-owned"}

            return _Result()

    exit_code = bs._invoke_render(
        _StubClient(),
        project="astrid-intro",
        timeline_path=Path("/tmp/timeline.json"),
        assets_path=Path("/tmp/assets.json"),
        output_name="storyboard.mp4",
    )
    assert exit_code == 1  # render failures report, not crash
    assert recorded["capability_id"] == "rendering.render"
    assert recorded["kind"] == "executor"
    assert recorded["project"] == "astrid-intro"
    assert recorded["inputs"] == {
        "timeline": "/tmp/timeline.json",
        "assets_registry": "/tmp/assets.json",
        "output_name": "storyboard.mp4",
    }
