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


def test_task_executor_import_does_not_load_legacy_project_runtime() -> None:
    """Importing the kernel task boundary must not pull project-run/thread code."""

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid.core.task_executor.service; "
                "print('astrid.core.project.run' in sys.modules); "
                "print(any(name.startswith('astrid.core.threads') for name in sys.modules)); "
                "print('astrid.core.execution.executor.runner' in sys.modules)"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["False", "False", "False"]


def test_normal_gateway_sdk_host_backup_timeline_imports_exclude_retired_bridge() -> None:
    """The deleted local bridge chain is unreachable from Stage1 surfaces."""

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid; import astrid.sdk; "
                "import astrid.core.gateway; "
                "import astrid.core.execution.generic_host; "
                "import astrid.core.backup; import astrid.core.timeline; "
                "retired = ('bridge_service', 'local_bridge_server', "
                "'task_bridge', 'local_bridge', 'orchestrator_runner', "
                "'asset_registry_edits', 'core.doctor', 'backup.operations', "
                "'backup.cli', 'model_setup.repair'); "
                "print([name for name in sys.modules if any(token in name "
                "for token in retired)])"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "[]"


def test_normal_pack_graph_excludes_installed_store_and_install_modules() -> None:
    """Manifest-ledger discovery must not load the retired mutation authority."""

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid; import astrid.sdk; "
                "import astrid.core.gateway; import astrid.core.pack; "
                "import astrid.core.pack.discovery; "
                "import astrid.core.pack.agent_index; "
                "import astrid.core.execution.executor.registry; "
                "import astrid.core.execution.orchestrator.registry; "
                "import astrid.core.rendering.registry; "
                "legacy = ('sqlite3', 'astrid.core.pack.store', "
                "'astrid.core.pack.install', 'astrid.core.pack.install_cli', "
                "'astrid.core.pack.install_git', 'astrid.core.pack.install_local', "
                "'astrid.core.pack.install_trust'); "
                "print([name for name in sys.modules if any(name == item or "
                "name.startswith(item + '.') for item in legacy)])"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "[]"


def test_pack_cli_rejects_retired_mutation_commands() -> None:
    """The pack CLI exposes read/validate/discovery commands only."""

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "astrid.core.pack.cli", "install", "demo"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "invalid choice" in result.stderr
