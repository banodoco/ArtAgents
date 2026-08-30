from __future__ import annotations

import subprocess
import sys
from pathlib import Path


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


def test_reigh_package_root_does_not_load_runtime_storage_authority() -> None:
    """Importing lightweight Reigh helpers must not install heavy bindings."""

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid.core.integrations.reigh; "
                "print('sqlite3' in sys.modules); "
                "print(any(name.startswith('astrid.core.store') or "
                "name.startswith('astrid.core.repositories') or "
                "name.startswith('astrid.core.migrations') or "
                "name.startswith('astrid.core.threads') "
                "for name in sys.modules))"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["False", "False"]


def test_reigh_binding_resolution_is_lazy_and_explicit() -> None:
    """The runtime resolver still loads exactly the requested binding."""

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid.core.integrations.reigh; "
                "from astrid.core.task_executor.service import resolve_task_handler; "
                "resolve_task_handler('wgp'); "
                "print('astrid.core.integrations.reigh.wgp_binding' in sys.modules); "
                "print('astrid.core.integrations.reigh.vibecomfy_binding' in sys.modules)"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["True", "False"]


def test_generic_host_import_does_not_load_execution_storage_authority() -> None:
    """The pack host loads runner dependencies only when executing a definition."""

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid.core.execution.generic_host; "
                "print('sqlite3' in sys.modules); "
                "print(any(name.startswith('astrid.core.store') or "
                "name.startswith('astrid.core.repositories') or "
                "name.startswith('astrid.core.threads') or "
                "name.startswith('astrid.core.project.run') "
                "for name in sys.modules))"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["False", "False"]
