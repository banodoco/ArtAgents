from __future__ import annotations

import json
from pathlib import Path

import pytest


def _base_manifest() -> dict[str, object]:
    return {
        "global_first_frame": "frames/global.png",
        "grid": {"rows": 2, "cols": 2},
        "tiles": [
            {
                "id": "tile_001",
                "row": 0,
                "col": 0,
                "first_frame": "frames/0_0.png",
                "tile_clip": "tiles/0_0.mp4",
            }
        ],
    }


def test_foley_map_stop_after_foley_writes_enriched_manifest_for_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTRID_INTERNAL_INVOCATION", "1")
    from astrid.packs.foley.orchestrators.foley_map import run as foley_map

    base_manifest = _base_manifest()
    enriched_manifest = {
        **base_manifest,
        "global_context": "synthetic ambient bed",
        "tiles": [
            {
                **base_manifest["tiles"][0],
                "prompt": "warm room tone with toy squeak",
                "foley_audio": "audio/0_0.wav",
            }
        ],
    }

    def fake_step_tile(args, out: Path) -> Path:
        manifest_path = out / "tiles.json"
        manifest_path.write_text(json.dumps(base_manifest), encoding="utf-8")
        return manifest_path

    monkeypatch.setattr(foley_map, "step_tile", fake_step_tile)
    monkeypatch.setattr(
        foley_map,
        "step_prompts",
        lambda args, out, manifest: {
            "global_context": "synthetic ambient bed",
            "tile_prompts": {"tile_001": "warm room tone with toy squeak"},
        },
    )
    monkeypatch.setattr(
        foley_map,
        "step_foley",
        lambda args, out, manifest, prompts, retry_ids: enriched_manifest,
    )
    monkeypatch.setattr(
        foley_map,
        "step_review",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("review should not run when --stop-after foley is set")
        ),
    )
    out_dir = tmp_path / "run"
    rc = foley_map.main(
        [
            "--video",
            str(tmp_path / "input.mp4"),
            "--out",
            str(out_dir),
            "--dry-run",
            "--stop-after",
            "foley",
        ]
    )

    assert rc == 0
    written = json.loads((out_dir / "tiles.json").read_text(encoding="utf-8"))
    assert written == enriched_manifest


def test_foley_map_stop_after_review_skips_spatial_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTRID_INTERNAL_INVOCATION", "1")
    from astrid.packs.foley.orchestrators.foley_map import run as foley_map

    base_manifest = _base_manifest()
    review_path = tmp_path / "run" / "review.html"

    def fake_step_tile(args, out: Path) -> Path:
        manifest_path = out / "tiles.json"
        manifest_path.write_text(json.dumps(base_manifest), encoding="utf-8")
        return manifest_path

    monkeypatch.setattr(foley_map, "step_tile", fake_step_tile)
    monkeypatch.setattr(
        foley_map,
        "step_prompts",
        lambda args, out, manifest: {
            "global_context": "synthetic ambient bed",
            "tile_prompts": {"tile_001": "warm room tone with toy squeak"},
        },
    )
    monkeypatch.setattr(
        foley_map,
        "step_foley",
        lambda args, out, manifest, prompts, retry_ids: {
            **base_manifest,
            "global_context": "synthetic ambient bed",
            "tiles": [
                {
                    **base_manifest["tiles"][0],
                    "prompt": "warm room tone with toy squeak",
                    "foley_audio": "audio/0_0.wav",
                }
            ],
        },
    )

    def fake_step_review(out: Path, enriched: dict[str, object]) -> Path:
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text("<html>review</html>", encoding="utf-8")
        return review_path

    monkeypatch.setattr(foley_map, "step_review", fake_step_review)
    rc = foley_map.main(
        [
            "--video",
            str(tmp_path / "input.mp4"),
            "--out",
            str(tmp_path / "run"),
            "--dry-run",
            "--stop-after",
            "review",
        ]
    )

    assert rc == 0
    assert review_path.is_file()
