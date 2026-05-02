from pathlib import Path
import tomllib

import banodoco_social
from banodoco_social.cli import main


def test_package_exposes_version():
    assert banodoco_social.__version__ == "0.1.0"


def test_console_script_entry_point_is_declared():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text())

    assert (
        pyproject["project"]["scripts"]["banodoco-social"]
        == "banodoco_social.cli:main"
    )


def test_cli_main_accepts_youtube_subcommand():
    assert callable(main)
