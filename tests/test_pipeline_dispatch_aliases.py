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
                with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                    pipeline.main([token, "list"])
                self.assertEqual(raised.exception.code, 2)

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

    def test_unknown_command_exits_2_with_message(self) -> None:
        """T7: unknown non-flag command prints to stderr and exits 2."""
        with (
            mock.patch(
                "astrid.core.session.binding.resolve_current_session_with_fs_fallback",
                return_value=object(),
            ),
        ):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                pipeline.main(["boguscmd"])
            self.assertEqual(raised.exception.code, 2)
            self.assertIn("astrid: unknown command 'boguscmd'", stderr.getvalue())

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


if __name__ == "__main__":
    unittest.main()
