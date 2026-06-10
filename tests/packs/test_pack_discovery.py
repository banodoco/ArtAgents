from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from astrid.core.element.registry import load_pack_elements
from astrid.core.execution.executor.registry import ExecutorRegistry, load_default_registry as load_executor_registry, load_pack_executors
from astrid.core.execution.orchestrator.registry import load_default_registry as load_orchestrator_registry, load_pack_orchestrators
from astrid.core.pack import PackValidationError, discover_packs, qualified_id_pack_id
from astrid.core.pack.discovery import ASTRID_PACKS_PATH_ENV, discover_packs_ordered


def write_pack(root: Path, pack_id: str, *, folder: str | None = None) -> Path:
    pack_root = root / (folder or pack_id)
    pack_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "\n".join(
            [
                f"id: {pack_id}",
                f"name: {pack_id.title()} Pack",
                "version: '1.0'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return pack_root


def write_executor(root: Path, folder: str, executor_id: str) -> Path:
    executor_root = root / folder
    executor_root.mkdir()
    kind = "external" if executor_id.startswith("external.") else "built_in"
    (executor_root / "executor.yaml").write_text(
        json.dumps(
            {
                "id": executor_id,
                "name": executor_id,
                "kind": kind,
                "version": "1.0",
                "command": {"argv": ["echo", executor_id]},
                "cache": {"mode": "none"},
            }
        ),
        encoding="utf-8",
    )
    return executor_root


def write_orchestrator(root: Path, folder: str, orchestrator_id: str) -> Path:
    orchestrator_root = root / folder
    orchestrator_root.mkdir()
    (orchestrator_root / "orchestrator.yaml").write_text(
        json.dumps(
            {
                "id": orchestrator_id,
                "name": orchestrator_id,
                "kind": "built_in",
                "version": "1.0",
                "runtime": {
                    "kind": "command",
                    "command": {"argv": ["echo", orchestrator_id]},
                },
            }
        ),
        encoding="utf-8",
    )
    return orchestrator_root


def write_element(root: Path, kind: str, element_id: str, *, pack_id: str) -> Path:
    element_root = root / "elements" / kind / element_id
    element_root.mkdir(parents=True)
    (element_root / "component.tsx").write_text("export default function Element() { return null; }\n", encoding="utf-8")
    singular = {"effects": "effect", "animations": "animation", "transitions": "transition"}[kind]
    (element_root / "element.yaml").write_text(
        json.dumps(
            {
                "id": element_id,
                "kind": singular,
                "pack_id": pack_id,
                "metadata": {"label": element_id},
                "schema": {"type": "object"},
                "defaults": {},
                "dependencies": {"js_packages": [], "python_requirements": []},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return element_root


class PackDiscoveryTest(unittest.TestCase):
    def test_valid_pack_discovery_and_content_loaders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = write_pack(packs_root, "builtin")
            write_executor(pack_root, "sample_executor", "builtin.sample_executor")
            write_orchestrator(pack_root, "sample_orchestrator", "builtin.sample_orchestrator")
            write_element(pack_root, "effects", "stamp", pack_id="builtin")

            packs = discover_packs(packs_root)
            self.assertEqual([pack.id for pack in packs], ["builtin"])

            with mock.patch("astrid.core.execution.executor.registry.discover_packs", return_value=packs):
                executors = load_pack_executors()
            with mock.patch("astrid.core.execution.orchestrator.registry.discover_packs", return_value=packs):
                orchestrators = load_pack_orchestrators()
            with mock.patch("astrid.core.element.registry.discover_packs", return_value=packs):
                elements = load_pack_elements()

        self.assertEqual([executor.id for executor in executors], ["builtin.sample_executor"])
        self.assertEqual(executors[0].metadata["source_pack"], "builtin")
        self.assertEqual(executors[0].metadata["source"], "pack")
        self.assertEqual([orchestrator.id for orchestrator in orchestrators], ["builtin.sample_orchestrator"])
        self.assertEqual(orchestrators[0].metadata["source_pack"], "builtin")
        self.assertEqual([(element.kind, element.id, element.source) for element in elements], [("effects", "stamp", "pack:builtin")])

    def test_default_registries_remain_populated_from_legacy_scans(self) -> None:
        executor_registry = load_executor_registry()
        orchestrator_registry = load_orchestrator_registry(executor_registry=executor_registry)

        self.assertGreaterEqual(len(executor_registry.list()), 51)
        self.assertGreaterEqual(len(orchestrator_registry.list()), 5)
        self.assertIn("video_editing.cut", executor_registry.as_mapping())
        self.assertIn("moirae.moirae", executor_registry.as_mapping())
        self.assertIn("media.clip_extract", executor_registry.as_mapping())
        self.assertEqual(
            sorted(executor.id for executor in executor_registry.list() if "clip_extract" in executor.id),
            ["media.clip_extract"],
        )
        self.assertIn("video_editing.hype", orchestrator_registry.as_mapping())

    def test_canonical_content_roots_are_used_for_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            pack_root = write_pack(packs_root, "builtin")
            (pack_root / "pack.yaml").write_text(
                "\n".join(
                    [
                        "schema_version: 1",
                        "id: builtin",
                        "name: Builtin Pack",
                        "version: '1.0'",
                        "content:",
                        "  executors: executors",
                        "  orchestrators: orchestrators",
                        "  elements: ui_elements",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (pack_root / "executors").mkdir()
            (pack_root / "orchestrators").mkdir()
            write_executor(pack_root / "executors", "sample_executor", "builtin.sample_executor")
            write_orchestrator(pack_root / "orchestrators", "sample_orchestrator", "builtin.sample_orchestrator")
            element_root = pack_root / "ui_elements" / "effects" / "stamp"
            element_root.mkdir(parents=True)
            (element_root / "component.tsx").write_text("export default function Element() { return null; }\n")
            (element_root / "element.yaml").write_text(
                json.dumps(
                    {
                        "id": "stamp",
                        "kind": "effect",
                        "pack_id": "builtin",
                        "metadata": {"label": "stamp"},
                        "schema": {"type": "object"},
                        "defaults": {},
                        "dependencies": {"js_packages": [], "python_requirements": []},
                    }
                )
            )
            packs = discover_packs(packs_root)
            with mock.patch("astrid.core.execution.executor.registry.discover_packs", return_value=packs):
                executors = load_pack_executors()
            with mock.patch("astrid.core.execution.orchestrator.registry.discover_packs", return_value=packs):
                orchestrators = load_pack_orchestrators()
            with mock.patch("astrid.core.element.registry.discover_packs", return_value=packs):
                elements = load_pack_elements()
            self.assertEqual([executor.id for executor in executors], ["builtin.sample_executor"])
            self.assertEqual([orchestrator.id for orchestrator in orchestrators], ["builtin.sample_orchestrator"])
            self.assertEqual([(element.kind, element.id) for element in elements], [("effects", "stamp")])

    def test_hidden_pack_is_excluded_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            write_pack(packs_root, "builtin")
            hidden_root = write_pack(packs_root, "external")
            hidden_root.joinpath("pack.yaml").write_text(
                "schema_version: 1\nid: external\nname: External\nversion: '1.0'\nvisibility: hidden\n",
                encoding="utf-8",
            )
            self.assertEqual([pack.id for pack in discover_packs(packs_root)], ["builtin"])
            self.assertEqual([pack.id for pack in discover_packs(packs_root, include_hidden=True)], ["builtin", "external"])

    def test_duplicate_executor_id_uses_priority_based_shadowing(self) -> None:
        """After M4, duplicate executor ids no longer raise — they are
        accepted and shadowed by priority (lower number wins)."""
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = write_pack(Path(tmp) / "packs", "builtin")
            write_executor(pack_root, "first", "builtin.duplicate")
            write_executor(pack_root, "second", "builtin.duplicate")
            packs = discover_packs(Path(tmp) / "packs")

            with mock.patch("astrid.core.execution.executor.registry.discover_packs", return_value=packs):
                load_result = load_pack_executors()
            # Duplicates are accepted — no error raised.
            registry = ExecutorRegistry(load_result)
            winner = registry.get("builtin.duplicate")
            self.assertIsNotNone(winner)
            self.assertEqual(winner.id, "builtin.duplicate")
            # The registry contains the id.
            self.assertIn("builtin.duplicate", registry.as_mapping())

    def test_pack_folder_must_match_pack_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packs_root = Path(tmp) / "packs"
            write_pack(packs_root, "builtin", folder="external")

            with self.assertRaisesRegex(PackValidationError, "must match folder name"):
                discover_packs(packs_root)

    def test_misplaced_executor_id_fails_pack_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = write_pack(Path(tmp) / "packs", "builtin")
            write_executor(pack_root, "moirae", "moirae.moirae")
            packs = discover_packs(Path(tmp) / "packs")

            with mock.patch("astrid.core.execution.executor.registry.discover_packs", return_value=packs):
                with self.assertRaisesRegex(PackValidationError, "found in pack 'builtin'"):
                    load_pack_executors()

    def test_misplaced_orchestrator_id_fails_pack_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = write_pack(Path(tmp) / "packs", "external")
            write_orchestrator(pack_root, "hype", "video_editing.hype")
            packs = discover_packs(Path(tmp) / "packs")

            with mock.patch("astrid.core.execution.orchestrator.registry.discover_packs", return_value=packs):
                with self.assertRaisesRegex(PackValidationError, "found in pack 'external'"):
                    load_pack_orchestrators()

    def test_misplaced_element_pack_id_fails_pack_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = write_pack(Path(tmp) / "packs", "builtin")
            write_element(pack_root, "effects", "stamp", pack_id="external")
            packs = discover_packs(Path(tmp) / "packs")

            with mock.patch("astrid.core.element.registry.discover_packs", return_value=packs):
                with self.assertRaisesRegex(PackValidationError, "declares pack_id 'external'"):
                    load_pack_elements()

    def test_qualified_id_pack_segment_helper_rejects_bare_ids(self) -> None:
        self.assertEqual(qualified_id_pack_id("video_editing.cut"), "video_editing")
        with self.assertRaisesRegex(PackValidationError, "must be qualified"):
            qualified_id_pack_id("cut")

    # ------------------------------------------------------------------
    # T2: env-only packs discovered through registry default loaders
    # ------------------------------------------------------------------

    @staticmethod
    def _make_multi_layer_scan(source_packs, **layer_packs):
        """Return a callable that returns the appropriate pack tuple for each
        layer root.  ``layer_packs`` keys are resolved Paths and values are
        the pack tuples returned when ``scan(key)`` is called.
        """
        layer_map: dict[Path, tuple] = {}
        for raw_root, packs in layer_packs.items():
            layer_map[Path(raw_root).resolve()] = packs

        def scan(arg=None):
            if arg is None:
                return source_packs
            resolved = Path(arg).resolve()
            return layer_map.get(resolved, ())

        return scan

    def test_env_only_pack_discovered_through_executor_registry(self) -> None:
        """Env-sourced packs with executor content are discovered through
        ``load_pack_executors``, even when no source-tree packs exist."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            # Create an env-only pack with executor content.
            env_root = tmp_root / "env_packs"
            env_root.mkdir()
            pack_root = write_pack(env_root, "env_test")
            write_executor(pack_root, "env_exec", "env_test.env_exec")

            env_packs = discover_packs(env_root)
            scan = self._make_multi_layer_scan((), **{str(env_root): env_packs})

            with mock.patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: str(env_root)}, clear=False):
                with mock.patch("astrid.core.execution.executor.registry.discover_packs", side_effect=scan):
                    executors = load_pack_executors(include_installed=False)

            self.assertEqual([e.id for e in executors], ["env_test.env_exec"])
            self.assertEqual(executors[0].metadata["source_pack"], "env_test")
            self.assertEqual(executors[0].metadata["source"], "pack")

    def test_env_only_pack_discovered_through_orchestrator_registry(self) -> None:
        """Env-sourced packs with orchestrator content are discovered through
        ``load_pack_orchestrators``, even when no source-tree packs exist."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            env_root = tmp_root / "env_packs"
            env_root.mkdir()
            pack_root = write_pack(env_root, "env_orch")
            write_orchestrator(pack_root, "env_orch", "env_orch.env_orch")

            env_packs = discover_packs(env_root)
            scan = self._make_multi_layer_scan((), **{str(env_root): env_packs})

            with mock.patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: str(env_root)}, clear=False):
                with mock.patch("astrid.core.execution.orchestrator.registry.discover_packs", side_effect=scan):
                    orchestrators = load_pack_orchestrators(include_installed=False)

            self.assertEqual([o.id for o in orchestrators], ["env_orch.env_orch"])
            self.assertEqual(orchestrators[0].metadata["source_pack"], "env_orch")
            self.assertEqual(orchestrators[0].metadata["source"], "pack")

    def test_env_only_pack_discovered_through_element_registry(self) -> None:
        """Env-sourced packs with element content are discovered through
        ``load_pack_elements``, even when no source-tree packs exist."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            env_root = tmp_root / "env_packs"
            env_root.mkdir()
            pack_root = write_pack(env_root, "env_elem")
            write_element(pack_root, "effects", "env_stamp", pack_id="env_elem")

            env_packs = discover_packs(env_root)
            scan = self._make_multi_layer_scan((), **{str(env_root): env_packs})

            with mock.patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: str(env_root)}, clear=False):
                with mock.patch("astrid.core.element.registry.discover_packs", side_effect=scan):
                    elements = load_pack_elements(include_installed=False)

            self.assertEqual([(e.kind, e.id, e.source) for e in elements],
                             [("effects", "env_stamp", "pack:env_elem")])

    def test_env_pack_discovers_all_content_kinds(self) -> None:
        """A single env-sourced pack with executor, orchestrator, and element
        content is discovered through all three registries."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            env_root = tmp_root / "env_packs"
            env_root.mkdir()
            pack_root = write_pack(env_root, "env_full")
            write_executor(pack_root, "exec1", "env_full.exec1")
            write_orchestrator(pack_root, "orch1", "env_full.orch1")
            write_element(pack_root, "animations", "slide", pack_id="env_full")

            env_packs = discover_packs(env_root)
            scan = self._make_multi_layer_scan((), **{str(env_root): env_packs})

            with mock.patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: str(env_root)}, clear=False):
                with mock.patch("astrid.core.execution.executor.registry.discover_packs", side_effect=scan), \
                     mock.patch("astrid.core.execution.orchestrator.registry.discover_packs", side_effect=scan), \
                     mock.patch("astrid.core.element.registry.discover_packs", side_effect=scan):
                    executors = load_pack_executors(include_installed=False)
                    orchestrators = load_pack_orchestrators(include_installed=False)
                    elements = load_pack_elements(include_installed=False)

            self.assertEqual([e.id for e in executors], ["env_full.exec1"])
            self.assertEqual([o.id for o in orchestrators], ["env_full.orch1"])
            self.assertEqual([(e.kind, e.id) for e in elements], [("animations", "slide")])

    def test_env_layer_ordered_after_extra_before_installed(self) -> None:
        """Precedence across source/extra/env/installed is observable through
        executor discovery.  The test uses distinct executor ids per layer so
        layer provenance is unambiguous; it also asserts that the executor
        registry prefers the first-seen (source) entry when duplicates exist."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)

            # Source pack.
            src_root = tmp_root / "src_packs"
            src_root.mkdir()
            src_pack_root = write_pack(src_root, "alpha")
            write_executor(src_pack_root, "exec1", "alpha.exec1")
            src_packs = discover_packs(src_root)

            # Extra pack.
            extra_root = tmp_root / "extra_packs"
            extra_root.mkdir()
            extra_pack_root = write_pack(extra_root, "beta")
            write_executor(extra_pack_root, "exec1", "beta.exec1")
            extra_packs = discover_packs(extra_root)

            # Env pack.
            env_root = tmp_root / "env_packs"
            env_root.mkdir()
            env_pack_root = write_pack(env_root, "gamma")
            write_executor(env_pack_root, "exec1", "gamma.exec1")
            env_packs = discover_packs(env_root)

            # Installed pack.
            installed_root = write_pack(tmp_root / "installed", "delta")
            write_executor(installed_root, "exec1", "delta.exec1")

            scan = self._make_multi_layer_scan(
                src_packs,
                **{
                    str(extra_root): extra_packs,
                    str(env_root): env_packs,
                },
            )

            with mock.patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: str(env_root)}, clear=False):
                with mock.patch("astrid.core.execution.executor.registry.discover_packs", side_effect=scan):
                    with mock.patch(
                        "astrid.core.pack.store.installed_pack_roots",
                        return_value=[installed_root],
                    ):
                        executors = load_pack_executors(
                            extra_pack_roots=(str(extra_root),),
                            include_installed=True,
                        )

            ids = [e.id for e in executors]
            # source (alpha), extra (beta), env (gamma), installed (delta).
            self.assertEqual(ids, ["alpha.exec1", "beta.exec1", "gamma.exec1", "delta.exec1"])

            registry = ExecutorRegistry(executors)
            winner = registry.get("alpha.exec1")
            self.assertIsNotNone(winner)
            self.assertEqual(winner.id, "alpha.exec1")

    def test_no_env_var_falls_through_gracefully(self) -> None:
        """When ASTRID_PACKS_PATH is empty, registry discovery proceeds
        through source/extra/installed without error."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            src_root = tmp_root / "src_packs"
            src_root.mkdir()
            pack_root = write_pack(src_root, "alpha")
            write_executor(pack_root, "exec1", "alpha.exec1")
            src_packs = discover_packs(src_root)

            def scan(arg=None):
                if arg is None:
                    return src_packs
                return ()

            with mock.patch.dict(os.environ, {ASTRID_PACKS_PATH_ENV: ""}, clear=False):
                with mock.patch("astrid.core.execution.executor.registry.discover_packs", side_effect=scan):
                    executors = load_pack_executors(include_installed=False)

            self.assertEqual([e.id for e in executors], ["alpha.exec1"])


if __name__ == "__main__":
    unittest.main()
