"""Installed-package resource contract for the M1 rendering deliverable."""

from __future__ import annotations

import importlib
from importlib import resources

from astrid.core.rendering.registry import load_default_registries


SCHEMAS = {
    "request.json",
    "support.json",
    "plan.json",
    "finalize.json",
    "result.json",
    "renderer-manifest.json",
    "planner-manifest.json",
    "finalizer-manifest.json",
}
FIXTURES = {
    "assets.json",
    "audio-reactive-colour.timeline.json",
    "effect-clip.timeline.json",
    "empty.timeline.json",
    "media-only.timeline.json",
    "remotion_backend_wrapper.py",
    "text-card.timeline.json",
    "theme-overrides.json",
    "transition-windows.timeline.json",
}
RENDERING_MANIFESTS = {
    "packs/rendering/pack.yaml",
    "packs/rendering/backends/ffmpeg/renderer.yaml",
    "packs/rendering/backends/remotion/renderer.yaml",
    "packs/rendering/elements/animations/fade-up/element.yaml",
    "packs/rendering/elements/animations/fade/element.yaml",
    "packs/rendering/elements/animations/scale-in/element.yaml",
    "packs/rendering/elements/animations/slide-left/element.yaml",
    "packs/rendering/elements/animations/slide-up/element.yaml",
    "packs/rendering/elements/animations/type-on/element.yaml",
    "packs/rendering/elements/effects/audio-reactive-colour/element.yaml",
    "packs/rendering/elements/effects/text-card/element.yaml",
    "packs/rendering/elements/transitions/cross-fade/element.yaml",
    "packs/rendering/elements/transitions/fade/element.yaml",
    "packs/rendering/executors/html_canvas_effect/executor.yaml",
    "packs/rendering/executors/render/executor.yaml",
    "packs/rendering/executors/sprite_sheet/executor.yaml",
    "packs/rendering/executors/timeline_storyboard/executor.yaml",
    "packs/rendering/planners/legacy_hybrid/planner.yaml",
    "packs/rendering/finalizers/ffmpeg/finalizer.yaml",
}


def test_rendering_schemas_and_parity_fixtures_are_package_resources() -> None:
    schemas = importlib.import_module("astrid.core.rendering.schemas")
    assert schemas.__spec__ is not None

    root = resources.files("astrid")
    schema_root = root.joinpath("core", "rendering", "schemas", "v1")
    fixture_root = root.joinpath("core", "rendering", "fixtures", "renderer_parity")

    assert {item.name for item in schema_root.iterdir()} >= SCHEMAS
    assert {item.name for item in fixture_root.iterdir()} >= FIXTURES


def test_rendering_manifests_are_package_resources_and_discoverable() -> None:
    root = resources.files("astrid")
    missing = [
        path
        for path in sorted(RENDERING_MANIFESTS)
        if not root.joinpath(*path.split("/")).is_file()
    ]
    assert not missing

    renderers, planners, finalizers = load_default_registries(include_installed=False)
    assert {candidate.id for candidate in renderers.list()} >= {
        "rendering.remotion",
        "rendering.ffmpeg",
    }
    assert {candidate.id for candidate in planners.list()} >= {"rendering.legacy_hybrid"}
    assert {candidate.id for candidate in finalizers.list()} >= {
        "rendering.ffmpeg-finalizer"
    }
