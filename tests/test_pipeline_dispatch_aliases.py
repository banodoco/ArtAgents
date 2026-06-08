import contextlib
import io
import sys
import unittest
from unittest import mock

from astrid import pipeline


class PipelineDispatchAliasTest(unittest.TestCase):
    def test_root_help_explains_canonical_gateway(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(pipeline.main(["--help"]), 0)

        help_text = stdout.getvalue()
        self.assertIn("Astrid command gateway", help_text)
        self.assertIn("python3 -m astrid orchestrators {list,inspect,validate,fork,run}", help_text)
        self.assertIn("python3 -m astrid executors {new,list,inspect,validate,fork,install,run}", help_text)
        self.assertIn("python3 -m astrid elements {list,inspect,fork,install}", help_text)
        self.assertIn("python3 -m astrid is the package entry point", help_text)
        self.assertNotIn("pipeline.py", help_text)
        self.assertNotIn("conductors", help_text)
        self.assertNotIn("performers", help_text)

    def test_elements_dispatches_before_pipeline_validation(self) -> None:
        from astrid.core.element import cli as elements_cli

        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch.object(elements_cli, "main", return_value=31) as elements_main,
        ):
            self.assertEqual(pipeline.main(["elements", "list"]), 31)
            elements_main.assert_called_once_with(["list"])

    def test_legacy_public_dispatch_tokens_are_rejected(self) -> None:
        for token in ("performers", "instruments", "conductors", "primitives"):
            with self.subTest(token=token):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    exit_code = pipeline.main([token, "list"])
                self.assertEqual(exit_code, 2)
                self.assertIn(f"unknown command '{token}'", stderr.getvalue())

    def test_doctor_and_setup_dispatch_before_legacy_validation(self) -> None:
        from astrid import doctor, setup_cli

        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch.object(doctor, "main", return_value=41) as doctor_main,
        ):
            self.assertEqual(pipeline.main(["doctor", "--help"]), 41)
            doctor_main.assert_called_once_with(["--help"])

        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch.object(setup_cli, "main", return_value=42) as setup_main,
        ):
            self.assertEqual(pipeline.main(["setup", "--help"]), 42)
            setup_main.assert_called_once_with(["--help"])

    def test_publish_style_dispatch_resolves_executor_runtime_from_registry_metadata(self) -> None:
        registry = mock.Mock()
        publish_entrypoint = mock.Mock(return_value=51)
        youtube_entrypoint = mock.Mock(return_value=52)
        reigh_data_entrypoint = mock.Mock(return_value=53)

        registry.get.side_effect = [
            mock.Mock(id="reigh.publish", metadata={"runtime_module": "reigh.publish.module", "runtime_entrypoint": "main"}),
            mock.Mock(id="youtube.upload", metadata={"runtime_module": "youtube.upload.module", "runtime_entrypoint": "main"}),
            mock.Mock(id="youtube.upload", metadata={"runtime_module": "youtube.upload.module", "runtime_entrypoint": "main"}),
            mock.Mock(id="reigh.reigh_data", metadata={"runtime_module": "reigh.reigh_data.module", "runtime_entrypoint": "main"}),
        ]

        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch("astrid.core.executor.registry.load_default_registry", return_value=registry),
            mock.patch(
                "astrid.core.pack_resolver.resolve_callable_from_metadata",
                side_effect=[
                    publish_entrypoint,
                    youtube_entrypoint,
                    youtube_entrypoint,
                    reigh_data_entrypoint,
                ],
            ) as resolve_runtime,
        ):
            self.assertEqual(pipeline.main(["publish", "--help"]), 51)
            self.assertEqual(pipeline.main(["publish-youtube", "--help"]), 52)
            self.assertEqual(pipeline.main(["upload-youtube", "--help"]), 52)
            self.assertEqual(pipeline.main(["reigh-data", "--help"]), 53)

        self.assertEqual(
            [call.args[0] for call in registry.get.call_args_list],
            ["reigh.publish", "youtube.upload", "youtube.upload", "reigh.reigh_data"],
        )
        publish_entrypoint.assert_called_once_with(["--help"])
        self.assertEqual(youtube_entrypoint.call_count, 2)
        reigh_data_entrypoint.assert_called_once_with(["--help"])
        self.assertEqual(
            [call.kwargs["owner_id"] for call in resolve_runtime.call_args_list],
            ["reigh.publish", "youtube.upload", "youtube.upload", "reigh.reigh_data"],
        )

    def test_run_alias_warns_and_delegates_to_runs(self) -> None:
        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch("astrid.core.task.lifecycle.cmd_runs_ls", return_value=57) as runs_ls,
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(pipeline.main(["run", "ls"]), 57)

        warning = stderr.getvalue()
        self.assertIn("'astrid run' is deprecated", warning)
        self.assertIn("'astrid runs'", warning)
        self.assertIn("0.3.0", warning)
        runs_ls.assert_called_once_with([])

    def test_runs_canonical_command_does_not_warn(self) -> None:
        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch("astrid.core.task.lifecycle.cmd_runs_ls", return_value=58) as runs_ls,
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(pipeline.main(["runs", "ls"]), 58)

        self.assertNotIn("deprecated", stderr.getvalue())
        runs_ls.assert_called_once_with([])

    def test_author_alias_warns_and_delegates_to_orchestrate(self) -> None:
        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch("astrid.orchestrate.cli.main", return_value=59) as orchestrate_main,
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(pipeline.main(["author", "describe", "pack.thing"]), 59)

        warning = stderr.getvalue()
        self.assertIn("'astrid author' is deprecated", warning)
        self.assertIn("'astrid orchestrate'", warning)
        self.assertIn("0.3.0", warning)
        orchestrate_main.assert_called_once_with(["describe", "pack.thing"])

    def test_orchestrate_canonical_command_does_not_warn(self) -> None:
        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch("astrid.orchestrate.cli.main", return_value=60) as orchestrate_main,
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(pipeline.main(["orchestrate", "describe", "pack.thing"]), 60)

        self.assertNotIn("deprecated", stderr.getvalue())
        orchestrate_main.assert_called_once_with(["describe", "pack.thing"])

    def test_unknown_command_exits_2_with_message(self) -> None:
        """T7: unknown non-flag command prints to stderr and exits 2."""
        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = pipeline.main(["boguscmd"])
            self.assertEqual(exit_code, 2)
            self.assertIn("unknown command 'boguscmd'", stderr.getvalue())

    def test_flag_style_invocation_still_passes_through(self) -> None:
        """T7: --prefixed args pass through to default brief orchestrator."""
        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
            mock.patch(
                "astrid.pipeline._run_default_brief_orchestrator",
                return_value=42,
            ) as mock_fallback,
        ):
            exit_code = pipeline.main(["--brief", "some brief text"])
            self.assertEqual(exit_code, 42)
            mock_fallback.assert_called_once_with(["--brief", "some brief text"])

    def test_package_is_executable(self) -> None:
        import runpy

        old_argv = sys.argv
        stdout = io.StringIO()
        try:
            sys.argv = ["python3 -m astrid", "elements", "list", "--kind", "effects"]
            with (
                mock.patch(
                    "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                    return_value=object(),
                ),
                contextlib.redirect_stdout(stdout),
            ):
                with self.assertRaises(SystemExit) as raised:
                    runpy.run_module("astrid", run_name="__main__")
        finally:
            sys.argv = old_argv

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("effects\ttext-card", stdout.getvalue())

    def test_patch_dispatch_seam_through_pipeline_direct_call(self) -> None:
        """Characterize: _dispatch_elements patched through astrid.pipeline
        IS intercepted when called directly (not via main(), which captures
        references in _TOP_LEVEL_HANDLERS at import time)."""
        with mock.patch(
            "astrid.pipeline._dispatch_elements",
            return_value=55,
        ) as patched_dispatch:
            result = pipeline._dispatch_elements(["list"])
            self.assertEqual(result, 55)
            patched_dispatch.assert_called_once_with(["list"])

    def test_dispatch_helpers_captured_in_top_level_handlers(self) -> None:
        """Characterize: _dispatch_elements in _TOP_LEVEL_HANDLERS holds the
        original function reference. Mocking the module attribute does NOT
        intercept calls routed through main() because the handler dict was
        populated at import time. This is a documented compatibility seam:
        legacy patches that need to intercept dispatch must target
        _TOP_LEVEL_HANDLERS or the lower-level CLI module entry points."""
        import astrid.gateway

        original = astrid.gateway._TOP_LEVEL_HANDLERS["elements"]
        self.assertIs(original, astrid.gateway._dispatch_elements)

        with mock.patch(
            "astrid.pipeline._dispatch_elements",
            return_value=999,
        ):
            # The handler dict still holds the original reference
            self.assertIsNot(
                astrid.gateway._TOP_LEVEL_HANDLERS["elements"],
                astrid.gateway._dispatch_elements,
            )
            # Direct call goes through the mock
            self.assertEqual(astrid.gateway._dispatch_elements(["x"]), 999)


if __name__ == "__main__":
    unittest.main()
