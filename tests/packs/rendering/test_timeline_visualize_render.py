from __future__ import annotations

import hashlib
import inspect
import io
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from astrid.core.timeline.snapshot import TimelineSnapshot, acquire_snapshot
from astrid.packs.rendering.executors.timeline_visualize.layout import (
    PAGE_H,
    PAGE_W,
    LayoutPage,
    layout_timeline,
)
from astrid.packs.rendering.executors.timeline_visualize.model import (
    ClipModel,
    IntervalFrames,
    IntervalSeconds,
    ModelExtents,
    TimelineInspectionModel,
    TrackModel,
    build_model,
)
from astrid.packs.rendering.executors.timeline_visualize.navigation import (
    IdentityMap,
    build_identity_map,
)
from astrid.packs.rendering.executors.timeline_visualize.render_png import (
    _BUNDLED_FONT_PATH,
    render_page_png,
)
from astrid.packs.rendering.executors.timeline_visualize.render_svg import (
    render_page_svg,
    render_page_svg_bytes,
)
from astrid.packs.rendering.executors.timeline_visualize.scope import Scope, select_scope

TESTS_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = TESTS_ROOT / "fixtures" / "timeline_visualize"
SLICE_DIR = FIXTURE_ROOT / "desert_slice"
PROJECT_SLUG = "desert-plant-growth"
TIMELINE_UUID = "ed70ef66-43da-4182-9f14-69361c6c5e10"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"

BG = (20, 20, 25)  # must mirror render_png._BG

# Committed golden renders of the deterministic desert page (PG001).  The PNG
# golden is byte-exact only under the pinned Pillow runtime (.venv); the SVG
# golden is runtime-independent.
GOLDEN_DIR = FIXTURE_ROOT / "golden"

# sha256 of the DECODED raw RGB buffer (image.tobytes()) of the scale-1 desert
# page under the CURRENT runtime.  Alternate runtimes (e.g. Python 3.11 +
# Pillow 12.3.0 vs Python 3.14 + Pillow 12.2.0) may produce different PNG
# bytes but must decode to exactly these pixels.
_PIXEL_SHA256 = (
    "8b340b38eea96c5ff7a31c1184ede174d84458078bda182ba9a3eac5dde74a06"
)

# Subprocess probe run under the alternate interpreter (python3.11): rebuilds
# the same desert page and prints sha256 of its decoded RGB buffer.  No
# datetime/random anywhere; fully deterministic.
_ALT_RUNTIME_PROBE = r"""
import hashlib
import io
import shutil
import tempfile
from pathlib import Path

from PIL import Image

from astrid.core.timeline.snapshot import acquire_snapshot
from astrid.packs.rendering.executors.timeline_visualize.layout import layout_timeline
from astrid.packs.rendering.executors.timeline_visualize.model import build_model
from astrid.packs.rendering.executors.timeline_visualize.navigation import (
    build_identity_map,
)
from astrid.packs.rendering.executors.timeline_visualize.render_png import (
    render_page_png,
)
from astrid.packs.rendering.executors.timeline_visualize.scope import select_scope

slice_dir = Path({slice_dir!r})
with tempfile.TemporaryDirectory() as td:
    timeline_dir = Path(td) / "timeline"
    shutil.copytree(slice_dir, timeline_dir)
    snapshot = acquire_snapshot(timeline_dir, project_slug="desert-plant-growth")
    model = build_model(snapshot)
    identity_map = build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )
    scope = select_scope(model, kind="timeline")
    page = layout_timeline(model, identity_map, scope, layout="time-scaled")[0]
    png = render_page_png(page, scale=1)
    image = Image.open(io.BytesIO(png))
    image.load()
    print(hashlib.sha256(image.tobytes()).hexdigest())
"""


@pytest.fixture
def desert(
    tmp_path: Path,
) -> tuple[TimelineInspectionModel, IdentityMap, TimelineSnapshot, Scope]:
    timeline_dir = tmp_path / "timeline"
    shutil.copytree(SLICE_DIR, timeline_dir)
    snapshot = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)
    model = build_model(snapshot)
    identity_map = build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )
    scope = select_scope(model, kind="timeline")
    return model, identity_map, snapshot, scope


@pytest.fixture
def synthetic_page() -> LayoutPage:
    tracks = (
        TrackModel("visual", "visual", 0, 0, "Visual"),
        TrackModel("audio", "audio", 1, 1, "Audio"),
    )
    clips = tuple(
        ClipModel(
            clip_id=f"clip-{index + 1}",
            track_id=track_id,
            authored=IntervalSeconds(start / 30, end / 30),
            frames=IntervalFrames(start, end, 30),
            effective=IntervalSeconds(start / 30, end / 30),
            speed=1.0,
            transition=None,
            source=None,
            kind="media",
        )
        for index, (start, end, track_id) in enumerate(
            [(0, 30, "visual"), (30, 60, "visual"), (15, 45, "audio")]
        )
    )
    model = TimelineInspectionModel(
        timeline_uuid=TIMELINE_UUID,
        timeline_ulid=TIMELINE_ULID,
        slug="synthetic-render",
        fps=30,
        tracks=tracks,
        clips=clips,
        extents=ModelExtents(
            composition_frames=60,
            composition_seconds=2.0,
            visual_frames=60,
            visual_seconds=2.0,
            audible_frames=45,
            fps=30,
        ),
        compositor_version="0.0.6",
        transition_default_frames=12,
        registry_keys=frozenset(),
        media_integrity={},
        snapshot_sns="SNS:" + "b" * 64,
    )
    identity_map = build_identity_map(
        model,
        root_sns=model.snapshot_sns,
        timeline_uuid=model.timeline_uuid,
        timeline_ulid=model.timeline_ulid,
    )
    scope = Scope(
        kind="timeline",
        ref=None,
        start_frame=0,
        end_frame=60,
        clip_ids=tuple(clip.clip_id for clip in clips),
        emphasized_clip_ids=(),
        context_frames=0,
    )
    pages = layout_timeline(model, identity_map, scope, layout="time-scaled")
    assert len(pages) == 1
    return pages[0]


@pytest.fixture
def desert_page(desert) -> LayoutPage:
    model, identity_map, _snapshot, scope = desert
    return layout_timeline(model, identity_map, scope, layout="time-scaled")[0]


def _printed_labels(page: LayoutPage) -> list[str]:
    return [
        item.label
        for item in page.objects
        if item.label is not None and item.omitted_reason is None
    ]


def test_svg_is_valid_xml_contains_labels_and_is_byte_stable(
    synthetic_page: LayoutPage,
    desert_page: LayoutPage,
) -> None:
    for page in (synthetic_page, desert_page):
        svg = render_page_svg(page)
        root = ET.fromstring(svg)  # must parse as well-formed XML
        text = "".join(root.itertext())

        for label in _printed_labels(page):
            assert label in text

        # Identity-bearing clip/continuation labels embed their qualified ref.
        identity_bearing = [
            item
            for item in page.objects
            if item.kind in ("clip", "continuation") and item.omitted_reason is None
        ]
        assert identity_bearing
        assert all(item.display_id in text for item in identity_bearing)

        # Byte-stable: two calls produce identical strings and bytes.
        assert render_page_svg(page) == svg
        assert render_page_svg_bytes(page) == svg.encode("utf-8")
        assert render_page_svg_bytes(page) == render_page_svg_bytes(page)


def test_png_two_renders_are_byte_identical(
    synthetic_page: LayoutPage,
    desert_page: LayoutPage,
) -> None:
    for page in (synthetic_page, desert_page):
        first = render_page_png(page)
        second = render_page_png(page)
        assert first == second
        assert len(first) > 0


def test_png_geometry_matches_layout_boxes(
    synthetic_page: LayoutPage,
    desert_page: LayoutPage,
) -> None:
    for page in (synthetic_page, desert_page):
        image = Image.open(io.BytesIO(render_page_png(page)))
        image.load()
        assert image.size == (PAGE_W, PAGE_H)

        # Background corners stay untouched.
        assert image.getpixel((5, 5)) == BG
        assert image.getpixel((PAGE_W - 5, PAGE_H - 5)) == BG

        # Every clip box center is painted (clip fill or its label).
        clips = [item for item in page.objects if item.kind == "clip"]
        assert clips
        for item in clips:
            cx = int(item.box.x + item.box.w / 2)
            cy = int(item.box.y + item.box.h / 2)
            assert image.getpixel((cx, cy)) != BG


def test_no_system_fonts_and_no_svg_rasterizer(
    synthetic_page: LayoutPage,
) -> None:
    svg_src = Path(inspect.getsourcefile(render_page_svg))
    png_src = Path(inspect.getsourcefile(render_page_png))
    for src in (svg_src, png_src):
        source = src.read_text(encoding="utf-8")
        assert "subprocess" not in source
        assert "Popen" not in source
        assert "inkscape" not in source
        assert "rsvg" not in source
        assert "cairosvg" not in source
        assert "os.system" not in source
        # V2: named system font faces (Menlo, Consolas, ...) are forbidden in
        # both renderers; only generic CSS keywords may appear.
        assert "Menlo" not in source
        assert "Consolas" not in source
        assert "Courier" not in source

    # The PNG font is the repo-bundled TTF, not a system lookup.
    assert _BUNDLED_FONT_PATH.is_file()
    assert "fonts" in _BUNDLED_FONT_PATH.parts
    assert "PowerGrotesk-Regular.ttf" == _BUNDLED_FONT_PATH.name

    # V2: every font-family attribute in the rendered SVG is composed only of
    # generic CSS keywords — no named font token may survive into the markup.
    svg = render_page_svg(synthetic_page)
    generic_keywords = frozenset(
        {
            "ui-monospace",
            "monospace",
            "sans-serif",
            "serif",
            "system-ui",
            "cursive",
            "fantasy",
        }
    )
    namespaces = {"s": "http://www.w3.org/2000/svg"}
    for node in ET.fromstring(svg).findall(".//s:text", namespaces):
        family = node.get("font-family", "")
        tokens = {token.strip() for token in family.split(",") if token.strip()}
        assert tokens, "empty font-family"
        assert tokens <= generic_keywords, f"named font token in {family!r}"
    assert "/System" not in svg and "/usr/share" not in svg


def test_svg_label_text_anchored_at_layout_label_boxes(
    synthetic_page: LayoutPage,
    desert_page: LayoutPage,
) -> None:
    """V1: the SVG consumes the LayoutPage-provided label boxes; there is no
    invented label geometry (the old hard-coded 320x30 ruler label box)."""

    svg_src = Path(inspect.getsourcefile(render_page_svg)).read_text(
        encoding="utf-8"
    )
    assert "label_box" not in svg_src
    assert "320.0" not in svg_src

    namespaces = {"s": "http://www.w3.org/2000/svg"}
    for page in (synthetic_page, desert_page):
        labels = {
            item.label: item
            for item in page.objects
            if item.kind == "label" and item.label is not None
        }
        assert labels
        root = ET.fromstring(render_page_svg(page))
        anchored = 0
        for node in root.findall(".//s:text", namespaces):
            content = "".join(node.itertext())
            if content not in labels:
                continue
            item = labels[content]
            # _text() places the label at box.x + pad_x (4.0) with
            # baseline_ratio 0.8 -> box.y + box.h * 0.8.
            assert float(node.get("x")) == pytest.approx(item.box.x + 4.0)
            assert float(node.get("y")) == pytest.approx(
                item.box.y + item.box.h * 0.8
            )
            anchored += 1
        assert anchored == len(labels)


def test_desert_page_renders_with_expected_pixel_math(desert_page: LayoutPage) -> None:
    for scale in (1, 2):
        png = render_page_png(desert_page, scale=scale)
        image = Image.open(io.BytesIO(png))
        image.load()
        assert image.size == (PAGE_W * scale, PAGE_H * scale)
        assert image.mode == "RGB"
        assert len(image.tobytes()) == PAGE_W * scale * PAGE_H * scale * 3


def test_no_datetime_or_random_in_modules() -> None:
    for module in (render_page_svg, render_page_png):
        source = Path(inspect.getsourcefile(module)).read_text(encoding="utf-8")
        assert "datetime" not in source
        assert "random" not in source
        assert "time.time" not in source
        assert "uuid" not in source


def test_pinned_svg_golden(desert_page: LayoutPage) -> None:
    """V3: the desert page (PG001) must reproduce its committed SVG golden
    byte-for-byte — the golden pins cross-process determinism."""

    golden = GOLDEN_DIR / "desert_pg001.svg"
    assert golden.is_file(), f"missing golden {golden}"
    assert render_page_svg_bytes(desert_page) == golden.read_bytes()


def test_pinned_png_golden(desert_page: LayoutPage) -> None:
    """V3: byte-exact PNG golden at scale 1 under the pinned Pillow runtime.

    The scale-1 golden is 61 KB (flat fill regions compress well), so no
    downscaling is needed to stay comfortably under a 1 MB commit budget.
    Full-resolution byte determinism is additionally covered by the
    in-process and cross-process render tests; this golden proves pinning.
    """

    golden = GOLDEN_DIR / "desert_pg001.png"
    assert golden.is_file(), f"missing golden {golden}"
    assert golden.stat().st_size <= 1_000_000
    assert render_page_png(desert_page, scale=1) == golden.read_bytes()


def test_decoded_pixel_hash_matches_committed(desert_page: LayoutPage) -> None:
    """V3: decoded-pixel pinning under the CURRENT runtime.

    Alternate runtimes (e.g. Python 3.11 + Pillow 12.3.0 vs Python 3.14 +
    Pillow 12.2.0) may serialize PNG bytes differently; the contract that
    must hold everywhere is that the DECODED RGB buffer is identical.
    """

    image = Image.open(io.BytesIO(render_page_png(desert_page, scale=1)))
    image.load()
    assert image.size == (PAGE_W, PAGE_H)
    assert image.mode == "RGB"
    assert hashlib.sha256(image.tobytes()).hexdigest() == _PIXEL_SHA256


def test_alt_runtime_decoded_pixels_match_committed_hash(
    desert_page: LayoutPage,
) -> None:
    """V3: real cross-interpreter pixel comparison against python3.11.

    Renders the same desert page under the alternate interpreter (with its
    own Pillow) and asserts its decoded RGB sha256 equals the committed hash
    computed under the pinned runtime.  Skipped where python3.11 (or Pillow
    for it) is unavailable — the committed hash still pins decoded pixels.
    """

    alt = shutil.which("python3.11")
    if alt is None:
        pytest.skip("python3.11 not on PATH; decoded-pixel hash remains pinned")
    probe = subprocess.run(
        [alt, "-c", "import PIL"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if probe.returncode != 0:
        pytest.skip("python3.11 has no Pillow; decoded-pixel hash remains pinned")

    repo_root = Path(__file__).resolve().parents[3]
    code = _ALT_RUNTIME_PROBE.format(slice_dir=str(SLICE_DIR))
    result = subprocess.run(
        [alt, "-c", code],
        cwd=repo_root,  # `astrid` is importable from the repo root
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"alt-runtime probe failed:\n{result.stderr}"
    pixel_hash = result.stdout.strip().splitlines()[-1]
    assert pixel_hash == _PIXEL_SHA256
