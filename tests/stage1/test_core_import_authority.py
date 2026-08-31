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


def test_sdk_error_mapping_failure_path_stays_local_authority_free() -> None:
    """Mapping a writer-shaped failure must not import the retired store graph."""

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from astrid.sdk.exceptions import map_error; "
                "WriterShutdownError = type('WriterShutdownError', (RuntimeError,), "
                "{'__module__': 'astrid.core.store.writer'}); "
                "mapped = map_error(WriterShutdownError('closed')); "
                "print(mapped.code); "
                "print([name for name in sys.modules if name == 'sqlite3' or "
                "name.startswith('astrid.core.store') or "
                "name.startswith('astrid.core.repositories') or "
                "name.startswith('astrid.core.receipts.service') or "
                "name.startswith('astrid.core.events.service')])"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["unavailable", "[]"]


def test_discovery_does_not_load_executor_catalog_runner_or_project_runtime() -> None:
    """Manifest-ledger discovery must stay clear of optional execution code."""

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid; astrid.discover(); "
                "legacy = ('astrid.core.execution.executor.catalog_source', "
                "'astrid.core.execution.executor.install', "
                "'astrid.core.execution.executor.runner', "
                "'astrid.core.execution.orchestrator.runner', "
                "'astrid.core.execution.executor.banodoco_catalog', "
                "'astrid.core.project.run', 'astrid.core.project.guidance'); "
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


def test_explicit_banodoco_catalog_api_loads_optional_catalog_code() -> None:
    """Optional catalog APIs remain available when explicitly requested."""

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid.core.execution.executor.registry; "
                "print('astrid.core.execution.executor.banodoco_catalog' in sys.modules); "
                "from astrid.core.execution.executor.registry import BanodocoCatalogConfig; "
                "print(BanodocoCatalogConfig.__name__); "
                "print('astrid.core.execution.executor.catalog_source' in sys.modules)"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["False", "BanodocoCatalogConfig", "True"]


def test_sdk_dry_run_is_manifest_only_and_does_not_load_runtime_authority(tmp_path: Path) -> None:
    """SDK previews must not import runners or create project/run state."""

    root = Path(__file__).resolve().parents[2]
    preview_root = tmp_path / "preview-out"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid; from pathlib import Path; "
                f"out = Path({str(preview_root)!r}); "
                "preview = astrid.invoke('understanding.understand', kind='executor', "
                "project='not-a-local-project', "
                "inputs={'mode': 'audio', 'audio': 'clip.wav'}, out=out, dry_run=True); "
                "legacy = ('astrid.core.execution.executor.runner', "
                "'astrid.core.execution.orchestrator.runner', 'astrid.core.project.run', "
                "'astrid.core.project.guidance'); "
                "print(preview.ok); print(preview.raw_result['dry_run']); "
                "print([name for name in sys.modules if any(name == item or "
                "name.startswith(item + '.') for item in legacy)]); "
                "print(out.exists())"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["True", "True", "[]", "False"]


def test_sdk_orchestrator_dry_run_is_manifest_only(tmp_path: Path) -> None:
    """Orchestrator previews use the same runtime-free admission boundary."""

    root = Path(__file__).resolve().parents[2]
    preview_root = tmp_path / "orchestrator-out"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid; from pathlib import Path; "
                f"out = Path({str(preview_root)!r}); "
                "preview = astrid.invoke('video_editing.hype', kind='orchestrator', "
                "project='not-a-local-project', "
                "inputs={'video': 'clip.mp4', 'brief': 'brief.md'}, out=out, dry_run=True); "
                "legacy = ('astrid.core.execution.executor.runner', "
                "'astrid.core.execution.orchestrator.runner', 'astrid.core.project.run', "
                "'astrid.core.project.guidance'); "
                "print(preview.ok); print(preview.raw_result['plan']['steps']); "
                "print([name for name in sys.modules if any(name == item or "
                "name.startswith(item + '.') for item in legacy)]); "
                "print(out.exists())"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == ["True", "[]", "[]", "False"]
