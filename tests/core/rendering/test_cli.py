"""T7.1 — renderer CLI discovery and smoke verbs.

Locks the internal renderer-authoring verbs ``list``, ``inspect``, ``validate``,
and ``smoke`` alongside the existing ``create``:

* ``list`` prints every discovered renderer/planner/finalizer qualified id
  from the default registries (the four built-ins are always present);
* ``inspect <id>`` prints the candidate's manifest fields (command,
  operations, required_binaries, capabilities, source pack, eligibility);
* ``validate <path>`` runs ``validate_pack`` and exits non-zero on errors;
* ``smoke <id>`` renders a deterministic minimal timeline through the public
  service and prints the output path plus provenance sidecar path;
* unknown ids and bad args exit non-zero with a clear message.

All output is stable plain text — no universal JSON envelope (T7.2 owns the
JSON contract).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.gateway.dispatch import _TOP_LEVEL_HANDLERS
from astrid.core.rendering.cli import main as renderers_cli_main
from astrid.core.rendering.publication import is_render_result_committed
from astrid.core.rendering.scaffold import create_renderer_scaffold

BUILTIN_IDS = (
    "rendering.ffmpeg",
    "rendering.remotion",
    "rendering.threejs",
    "rendering.ffmpeg-finalizer",
)


def _stdout(capsys) -> str:
    return capsys.readouterr().out


def _stderr(capsys) -> str:
    return capsys.readouterr().err


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_shows_the_four_builtin_ids(capsys) -> None:
    assert renderers_cli_main(["list"]) == 0
    lines = [line for line in _stdout(capsys).splitlines() if line.strip()]
    for capability_id in BUILTIN_IDS:
        assert capability_id in lines, f"{capability_id!r} missing from {lines}"


def test_list_with_pack_root_includes_scaffolded_renderer(
    tmp_path: Path,
    capsys,
) -> None:
    create_renderer_scaffold("wave", tmp_path / "wave")
    assert renderers_cli_main(["list", "--pack-root", str(tmp_path)]) == 0
    lines = [line for line in _stdout(capsys).splitlines() if line.strip()]
    assert "wave.wave" in lines


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


def test_inspect_ffmpeg_shows_manifest_fields(capsys) -> None:
    assert renderers_cli_main(["inspect", "rendering.ffmpeg"]) == 0
    text = _stdout(capsys)
    assert "id: rendering.ffmpeg" in text
    assert "kind: renderer" in text
    assert "command: python3 run.py" in text
    assert "operations: render, support" in text
    assert "required_binaries: ffmpeg, ffprobe" in text
    assert "capabilities:" in text
    assert "clip_types: media" in text
    assert "supports_full_timeline: true" in text
    assert "source_pack: rendering" in text
    assert "eligibility: eligible" in text
    assert "trust_method: source_tree" in text


def test_inspect_scaffolded_renderer_via_pack_root(tmp_path: Path, capsys) -> None:
    create_renderer_scaffold("wave", tmp_path / "wave")
    assert (
        renderers_cli_main(
            ["inspect", "wave.wave", "--pack-root", str(tmp_path)]
        )
        == 0
    )
    text = _stdout(capsys)
    assert "id: wave.wave" in text
    assert "kind: renderer" in text
    assert "command: python3 render.py" in text
    assert "source_pack: wave" in text
    assert "source_kind: extra" in text
    assert "eligibility: eligible" in text
    assert "trust_method: explicit_extra_pack_root" in text


def test_inspect_unknown_id_fails_with_message(capsys) -> None:
    assert renderers_cli_main(["inspect", "no.such.renderer"]) == 2
    message = _stderr(capsys)
    assert "unknown renderer/planner/finalizer id 'no.such.renderer'" in message
    assert "astrid.core.rendering.cli list" in message


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_scaffold_passes(tmp_path: Path, capsys) -> None:
    dest = create_renderer_scaffold("wave", tmp_path / "wave")
    assert renderers_cli_main(["validate", str(dest)]) == 0
    assert f"valid: {dest.resolve()}" in _stdout(capsys)


def test_validate_broken_pack_fails_nonzero(tmp_path: Path, capsys) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "pack.yaml").write_text("id: [unclosed\n", encoding="utf-8")

    assert renderers_cli_main(["validate", str(broken)]) == 2
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "pack.yaml" in captured.err
    assert f"invalid: {broken.resolve()}" in captured.out


def test_validate_missing_directory_fails(capsys) -> None:
    assert renderers_cli_main(["validate", "/no/such/pack/dir"]) == 2
    assert "not a directory or does not exist" in _stderr(capsys)


# ---------------------------------------------------------------------------
# smoke
# ---------------------------------------------------------------------------


def test_smoke_scaffolded_pack_produces_output_and_sidecar(
    tmp_path: Path,
    capsys,
) -> None:
    create_renderer_scaffold("wave", tmp_path / "wave")
    out_path = tmp_path / "out.mp4"

    assert (
        renderers_cli_main(
            [
                "smoke",
                "wave.wave",
                "--pack-root",
                str(tmp_path),
                "--out",
                str(out_path),
            ]
        )
        == 0
    )
    text = _stdout(capsys)
    assert "smoke: wave.wave" in text
    assert f"output: {out_path.resolve()}" in text
    assert f"provenance: {Path(f'{out_path.resolve()}.provenance.json')}" in text

    assert out_path.is_file()
    assert out_path.stat().st_size > 0
    sidecar = Path(f"{out_path}.provenance.json")
    assert sidecar.is_file()
    assert is_render_result_committed(out_path, sidecar_path=sidecar)


def test_smoke_default_workspace_prints_usable_paths(tmp_path: Path, capsys) -> None:
    create_renderer_scaffold("wave", tmp_path / "wave")

    assert (
        renderers_cli_main(["smoke", "wave.wave", "--pack-root", str(tmp_path)])
        == 0
    )
    lines = {
        line.partition(": ")[0]: line.partition(": ")[2]
        for line in _stdout(capsys).splitlines()
        if ": " in line
    }
    output = Path(lines["output"])
    sidecar = Path(lines["provenance"])
    assert output.is_file()
    assert output.stat().st_size > 0
    assert sidecar.is_file()
    assert is_render_result_committed(output, sidecar_path=sidecar)


def test_smoke_unknown_id_fails_with_message(capsys) -> None:
    assert renderers_cli_main(["smoke", "no.such.renderer"]) == 2
    assert "unknown renderer id 'no.such.renderer'" in _stderr(capsys)


def test_smoke_removed_planner_id_fails_closed(capsys) -> None:
    assert renderers_cli_main(["smoke", "rendering.legacy_hybrid"]) == 2
    message = _stderr(capsys)
    assert "unknown renderer id 'rendering.legacy_hybrid'" in message


# ---------------------------------------------------------------------------
# bad args / gateway routing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["inspect"],
        ["smoke"],
        ["bogus-verb"],
    ],
)
def test_bad_args_exit_nonzero(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        renderers_cli_main(argv)
    assert excinfo.value.code == 2


def test_internal_renderer_cli_routes_list_and_smoke(
    tmp_path: Path,
    capsys,
) -> None:
    assert "renderers" not in _TOP_LEVEL_HANDLERS

    assert renderers_cli_main(["list"]) == 0
    lines = [line for line in _stdout(capsys).splitlines() if line.strip()]
    for capability_id in BUILTIN_IDS:
        assert capability_id in lines

    create_renderer_scaffold("wave", tmp_path / "wave")
    out_path = tmp_path / "dispatch-out.mp4"
    assert (
        renderers_cli_main(
            [
                "smoke",
                "wave.wave",
                "--pack-root",
                str(tmp_path),
                "--out",
                str(out_path),
            ]
        )
        == 0
    )
    assert out_path.is_file()
    assert Path(f"{out_path}.provenance.json").is_file()
