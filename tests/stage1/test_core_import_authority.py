from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_gateway_import_does_not_load_local_storage_authority() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid.core.gateway; "
                "print('sqlite3' in sys.modules); "
                "print(any(name.startswith('astrid.core.store') or "
                "name.startswith('astrid.core.repositories') "
                "for name in sys.modules))"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["False", "False"]


def test_public_sdk_lazy_exports_do_not_load_local_storage_authority() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid; astrid.discover; "
                "astrid.CapabilityValidationError; "
                "print('sqlite3' in sys.modules); "
                "print(any(name.startswith('astrid.core.store') or "
                "name.startswith('astrid.core.repositories') or "
                "name.startswith('astrid.core.migrations') "
                "for name in sys.modules))"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["False", "False"]


def test_checkout_pack_composition_does_not_load_local_storage_authority() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid.packs; "
                "print('sqlite3' in sys.modules); "
                "print(any(name.startswith('astrid.core.store') or "
                "name.startswith('astrid.core.repositories') or "
                "name.startswith('astrid.core.migrations') "
                "for name in sys.modules))"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["False", "False"]
