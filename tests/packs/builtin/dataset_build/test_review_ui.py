from __future__ import annotations

from pathlib import Path


UI_ROOT = Path("astrid/packs/builtin/dataset_build/review_ui")
APP_JS = UI_ROOT / "app.js"
INDEX_HTML = UI_ROOT / "index.html"


def test_review_ui_declares_generic_paginated_data_loading() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    assert "const PAGE_LIMIT = 50" in js
    assert 'offset: String(state.offset)' in js
    assert 'limit: String(state.limit)' in js
    assert 'params.set("status", state.status)' in js
    assert "fetch(`/data.json?${params.toString()}`)" in js


def test_review_ui_bounds_visible_dom_window() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    assert "const VISIBLE_WINDOW_SIZE = 8" in js
    assert "state.items.slice(windowStart, windowEnd)" in js
    assert "visibleItems.map" in js
    assert "state.items.map" not in js
    assert 'preload="metadata"' in js


def test_review_ui_supports_all_m0_reject_reasons_and_shortcuts() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    for reason in (
        "watermark",
        "wrong_scene",
        "wrong_character",
        "bad_motion",
        "low_quality",
        "wrong_content",
        "rights_concern",
        "other",
    ):
        assert f'"{reason}"' in js
    assert 'event.key.toLowerCase() === "y"' in js
    assert 'event.key.toLowerCase() === "n"' in js
    assert 'event.key === "ArrowRight"' in js
    assert 'event.key === "ArrowLeft"' in js
    assert "/^[1-8]$/.test(event.key)" in js
    assert 'event.key.toLowerCase() === "e"' in js
    assert 'event.key === "Enter"' in js


def test_review_ui_saves_diff_payload_with_base_state_version() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    assert "base_state_version: state.baseStateVersion" in js
    assert "revisions," in js
    assert 'fetch("/save"' in js
    assert "state.revisions.clear()" in js
    assert 'fetch("/state.json"' in js


def test_review_ui_assets_are_generic_and_linked() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (UI_ROOT / "styles.css").read_text(encoding="utf-8")
    assert "./styles.css" in html
    assert "./app.js" in html
    assert "Dataset Review" in html
    assert "seinfeld" not in (html + css + APP_JS.read_text(encoding="utf-8")).lower()
