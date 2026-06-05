from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from astrid.packs.understanding.executors.visual_understand.run import main


def test_visual_understand_builds_numbered_contact_sheet(capsys, tmp_path):
    images = []
    for index, color in enumerate(((255, 0, 0), (0, 255, 0), (0, 0, 255)), start=1):
        path = tmp_path / f"image-{index}.jpg"
        Image.new("RGB", (320, 180), color).save(path)
        images.extend(["--image", str(path)])

    sheet = tmp_path / "sheet.jpg"
    code = main(
        [
            "--query",
            "What should be removed?",
            *images,
            "--contact-sheet",
            str(sheet),
            "--cols",
            "2",
            "--tile-width",
            "200",
            "--dry-run",
        ]
    )

    assert code == 0
    assert sheet.is_file()
    with Image.open(sheet) as rendered:
        assert rendered.size == (400, 324)
    payload = json.loads(capsys.readouterr().out)
    assert payload["image"] == str(sheet)
    assert [frame["index"] for frame in payload["frames"]] == [1, 2, 3]
    assert payload["detail"] == "low"
    assert payload["models"] == ["gpt-4o-mini"]


def test_visual_understand_single_image_dry_run_does_not_make_sheet(capsys, tmp_path):
    image = tmp_path / "single.jpg"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(image)

    code = main(["--query", "What is here?", "--image", str(image), "--dry-run"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["image"] == str(image)
    assert len(payload["frames"]) == 1


def test_visual_understand_best_mode_dry_run(capsys, tmp_path):
    image = tmp_path / "single.jpg"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(image)

    code = main(["--query", "What is here?", "--image", str(image), "--mode", "best", "--dry-run"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["models"] == ["gpt-5.4"]


def test_visual_understand_crop_variants_contact_sheet(capsys, tmp_path):
    image = tmp_path / "wide.jpg"
    Image.new("RGB", (1600, 900), (10, 20, 30)).save(image)
    sheet = tmp_path / "crops.jpg"

    code = main(
        [
            "--query",
            "Which crop works best?",
            "--image",
            str(image),
            "--crop-aspect",
            "9:16",
            "--crop-position",
            "left,center,right",
            "--contact-sheet",
            str(sheet),
            "--dry-run",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["image"] == str(sheet)
    assert [frame["label"].split()[:2] for frame in payload["frames"]] == [["9:16", "left"], ["9:16", "center"], ["9:16", "right"]]
    assert sheet.is_file()


def test_visual_understand_writes_universal_result_manifest(capsys, tmp_path):
    image = tmp_path / "single.jpg"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(image)
    out_dir = tmp_path / "out"
    out_path = out_dir / "result.json"

    with patch(
        "astrid.packs.understanding.executors.visual_understand.run.load_api_key",
        return_value="test-key",
    ), patch(
        "astrid.packs.understanding.executors.visual_understand.run._call_responses_api",
        return_value={"output_text": "Minimal composition with centered subject.", "usage": {"total_tokens": 9}},
    ):
        code = main(
            [
                "--query",
                "What is here?",
                "--image",
                str(image),
                "--out-dir",
                str(out_dir),
                "--out",
                str(out_path),
            ]
        )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert out_path.is_file()
    assert payload["manifest_path"] == str(manifest_path)
    assert payload["kind"] == "understanding.visual_understand"
    assert manifest["kind"] == "understanding.visual_understand"
    assert manifest["inputs"]["images"] == [str(image)]
    assert manifest["outputs"][-1]["path"] == str(out_path)
    assert manifest["outputs"][-1]["type"] == "file"
    assert "content_hash" in manifest["outputs"][-1]
    assert any(Path(item["path"]).name == "single.jpg" for item in manifest["outputs"])
