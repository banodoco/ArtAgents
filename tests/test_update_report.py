"""Tests for update_check() and update_apply().

Covers update check/apply, safety escalation detection, report file.

All tests use tempfile.TemporaryDirectory for fixture content.
No real LLM calls, no real network calls, no real git ops on actual repo.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from astrid.core.update import update_check, update_apply
from astrid.core.executor.registry import ExecutorRegistry
from astrid.core.executor.schema import ExecutorDefinition
from astrid.contracts.schema import IsolationMetadata, SafetyDeclaration


def _make_exec_def(id: str, **overrides) -> ExecutorDefinition:
    kwargs: dict = dict(
        id=id,
        name=id.split(".")[-1],
        kind="built_in",
        version="1.0.0",
        description=f"Description for {id}",
        short_description=f"Short {id}",
        keywords=(id.split(".")[-1],),
        isolation=IsolationMetadata(network=False),
        metadata={"source": "pack", "source_pack": id.split(".")[0]},
    )
    kwargs.update(overrides)
    return ExecutorDefinition(**kwargs)


class TestUpdateCheck:
    """update_check() returns correct report dicts."""

    def test_not_forked_returns_error(self):
        """Not-forked capability returns error='not_forked'."""
        registry = ExecutorRegistry()
        registry.register(_make_exec_def("builtin.shots"))

        result = update_check("builtin.shots", registry, capability_type="executor")
        assert result["error"] == "not_forked"
        assert "not forked" in result["report"]

    def test_upstream_not_found_returns_error(self):
        """Forked capability whose upstream doesn't exist returns error."""
        registry = ExecutorRegistry()
        registry.register(
            _make_exec_def(
                "local.shots",
                version="1.0.0",
                metadata={
                    "source": "pack",
                    "source_pack": "local",
                    "forked_from": "builtin.shots",
                },
            )
        )

        result = update_check("local.shots", registry, capability_type="executor")
        assert result.get("error") == "upstream_not_found"
        assert "not found" in result["report"]

    def test_up_to_date_when_identical(self):
        """When local and upstream are identical, recommendation is up_to_date."""
        common = {
            "description": "Shots executor",
            "short_description": "Shots",
            "keywords": ("shots",),
        }
        registry = ExecutorRegistry()
        registry.register(
            _make_exec_def(
                "builtin.shots",
                version="1.0.0",
                **common,
                metadata={"source": "pack", "source_pack": "builtin"},
            )
        )
        registry.register(
            _make_exec_def(
                "local.shots",
                version="1.0.0",
                **common,
                metadata={
                    "source": "pack",
                    "source_pack": "local",
                    "forked_from": "builtin.shots",
                },
            )
        )

        result = update_check("local.shots", registry, capability_type="executor")
        assert result["recommendation"] == "up_to_date"
        assert result["forked_from"] == "builtin.shots"

    def test_version_difference_detected(self):
        """Version difference between local and upstream is flagged."""
        registry = ExecutorRegistry()
        registry.register(
            _make_exec_def(
                "builtin.shots",
                version="2.0.0",
                metadata={"source": "pack", "source_pack": "builtin"},
            )
        )
        registry.register(
            _make_exec_def(
                "local.shots",
                version="1.0.0",
                metadata={
                    "source": "pack",
                    "source_pack": "local",
                    "forked_from": "builtin.shots",
                },
            )
        )

        result = update_check("local.shots", registry, capability_type="executor")
        assert result["recommendation"] == "safe_to_update"
        assert result["forked_from"] == "builtin.shots"
        assert result["upstream_version"] == "2.0.0"
        assert result["local_version"] == "1.0.0"

    def test_description_change_detected(self):
        """Description change is detected as metadata_diff."""
        registry = ExecutorRegistry()
        registry.register(
            _make_exec_def(
                "builtin.shots",
                version="1.0.0",
                description="New improved description",
                metadata={"source": "pack", "source_pack": "builtin"},
            )
        )
        registry.register(
            _make_exec_def(
                "local.shots",
                version="1.0.0",
                description="Old description",
                metadata={
                    "source": "pack",
                    "source_pack": "local",
                    "forked_from": "builtin.shots",
                },
            )
        )

        result = update_check("local.shots", registry, capability_type="executor")
        assert "description" in result.get("metadata_diff", {})
        assert result["recommendation"] == "safe_to_update"

    def test_network_escalation_detected(self):
        """When upstream has network=false and local fork has network=true,
        safety escalation is detected (the fork introduces network access)."""
        registry = ExecutorRegistry()
        registry.register(
            _make_exec_def(
                "builtin.shots",
                version="1.0.0",
                isolation=IsolationMetadata(network=False),
                metadata={"source": "pack", "source_pack": "builtin"},
            )
        )
        registry.register(
            _make_exec_def(
                "local.shots",
                version="1.0.0",
                isolation=IsolationMetadata(network=True),
                metadata={
                    "source": "pack",
                    "source_pack": "local",
                    "forked_from": "builtin.shots",
                },
            )
        )

        result = update_check("local.shots", registry, capability_type="executor")
        assert len(result["safety_escalations"]) >= 1
        assert any("network" in esc.lower() for esc in result["safety_escalations"])
        assert result["recommendation"] == "blocked"


class TestUpdateApply:
    """update_apply() applies updates and writes report files."""

    def test_apply_not_forked_returns_error(self):
        """Not-forked capability cannot be updated."""
        registry = ExecutorRegistry()
        registry.register(_make_exec_def("builtin.shots"))

        result = update_apply("builtin.shots", registry, capability_type="executor")
        assert result.get("error") == "not_forked"
        assert result.get("applied") is False

    def test_apply_up_to_date_noop(self):
        """Up-to-date fork is not re-applied."""
        registry = ExecutorRegistry()
        registry.register(
            _make_exec_def(
                "builtin.shots",
                version="1.0.0",
                metadata={"source": "pack", "source_pack": "builtin"},
            )
        )
        registry.register(
            _make_exec_def(
                "local.shots",
                version="1.0.0",
                metadata={
                    "source": "pack",
                    "source_pack": "local",
                    "forked_from": "builtin.shots",
                },
            )
        )

        result = update_apply("local.shots", registry, capability_type="executor")
        assert result.get("applied") is False

    def test_apply_blocked_by_safety(self):
        """Safety escalation blocks update without force flag."""
        registry = ExecutorRegistry()
        registry.register(
            _make_exec_def(
                "builtin.shots",
                version="1.0.0",
                isolation=IsolationMetadata(network=False),
                metadata={"source": "pack", "source_pack": "builtin"},
            )
        )
        registry.register(
            _make_exec_def(
                "local.shots",
                version="1.0.0",
                isolation=IsolationMetadata(network=True),
                metadata={
                    "source": "pack",
                    "source_pack": "local",
                    "forked_from": "builtin.shots",
                },
            )
        )

        result = update_apply("local.shots", registry, capability_type="executor")
        assert result.get("applied") is False
        assert "blocked" in result.get("report", "").lower() or result.get("recommendation") == "blocked"

    def test_apply_with_content_roots(self):
        """When both local and upstream have content roots, update_apply
        copies files and writes .astrid_update_report.json."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create upstream content root
            upstream_root = Path(tmp) / "upstream"
            upstream_root.mkdir()
            (upstream_root / "executor.yaml").write_text(
                json.dumps({
                    "id": "builtin.shots",
                    "name": "shots",
                    "kind": "built_in",
                    "version": "2.0.0",
                    "command": {"argv": ["echo", "hello"]},
                    "cache": {"mode": "none"},
                }) + "\n",
                encoding="utf-8",
            )
            (upstream_root / "run.py").write_text("# upstream run\n", encoding="utf-8")

            # Create local fork content root
            local_root = Path(tmp) / "local_fork"
            local_root.mkdir()
            (local_root / "executor.yaml").write_text(
                json.dumps({
                    "id": "local.shots",
                    "name": "shots",
                    "kind": "built_in",
                    "version": "1.0.0",
                    "command": {"argv": ["echo", "hello"]},
                    "cache": {"mode": "none"},
                    "metadata": {"forked_from": "builtin.shots"},
                }) + "\n",
                encoding="utf-8",
            )
            (local_root / "run.py").write_text("# local run\n", encoding="utf-8")

            registry = ExecutorRegistry()
            registry.register(
                _make_exec_def(
                    "builtin.shots",
                    version="2.0.0",
                    metadata={
                        "source": "pack",
                        "source_pack": "builtin",
                        "content_root": str(upstream_root),
                    },
                )
            )
            registry.register(
                _make_exec_def(
                    "local.shots",
                    version="1.0.0",
                    metadata={
                        "source": "pack",
                        "source_pack": "local",
                        "forked_from": "builtin.shots",
                        "content_root": str(local_root),
                    },
                )
            )

            result = update_apply("local.shots", registry, capability_type="executor")
            assert result.get("applied") is True
            assert result.get("report_path")

            # Verify .astrid_update_report.json was written
            report_path = Path(result["report_path"])
            assert report_path.is_file()
            report_data = json.loads(report_path.read_text(encoding="utf-8"))
            assert report_data["capability_id"] == "local.shots"
            assert report_data["forked_from"] == "builtin.shots"

            # Verify upstream content was copied to local root
            updated_run = (local_root / "run.py").read_text(encoding="utf-8")
            assert updated_run == "# upstream run\n"


class TestUpdateReportSafetyEscalations:
    """Specific safety escalation detection rules."""

    def test_new_binaries_in_upstream(self):
        """New binaries in upstream isolation are detected."""
        registry = ExecutorRegistry()
        registry.register(
            _make_exec_def(
                "builtin.shots",
                version="1.0.0",
                isolation=IsolationMetadata(network=False, binaries=("ffmpeg",)),
                metadata={"source": "pack", "source_pack": "builtin"},
            )
        )
        registry.register(
            _make_exec_def(
                "local.shots",
                version="1.0.0",
                isolation=IsolationMetadata(network=False),
                metadata={
                    "source": "pack",
                    "source_pack": "local",
                    "forked_from": "builtin.shots",
                },
            )
        )

        result = update_check("local.shots", registry, capability_type="executor")
        # Upstream has new binaries — at least one safety escalation
        assert len(result["safety_escalations"]) >= 1
        assert any("binaries" in esc.lower() for esc in result["safety_escalations"])
