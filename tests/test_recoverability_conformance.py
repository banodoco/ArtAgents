"""Recoverability conformance scanner — final zero mode.

The scanner enforces that every user-facing parser surface uses the shared
recoverability contracts:

* ``--kind`` arguments must use ``add_kind_arg()`` (``kind_arg_findings``)
* Enum-choice arguments must use ``RegistryChoices`` or ``StaticChoices``
  (``non_kind_enum_findings``)
* No user-facing bare ``ValueError`` / ``RuntimeError`` raises
  (``ast_findings`` → ``bare_raise``)
* No bespoke user-facing ``sys.stderr`` renderers
  (``ast_findings`` → ``direct_stderr``)
* Every expected parser surface must be importable and scannable
  (``skipped_parser_surface_count`` → 0)

The allowlists (``ALLOWED_BARE_RAISES`` / ``ALLOWED_STDERR_SITES``) are
the only mechanism for exempting a finding — every exempted site must
carry an explicit reason so reviewers can audit it.

The single test ``test_recoverability_conformance_zero_mode`` runs the
scanner live and asserts zero findings across all categories.  Any
non-zero finding causes a test failure with a detailed breakdown.

Import safety
-------------
This module imports only stdlib packages at module level.  The scanner
script (``_PARSER_SURFACE_SCRIPT``) is executed in isolated subprocesses
so import failures there are recorded as skipped surfaces, not module-level
crashes.  The module is safe to import even when optional dependencies are
absent.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASTRID_ROOT = ROOT / "astrid"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "recoverability_conformance_worklist.json"


AST_EXTRA_PATHS = {
    "astrid/pipeline.py",
    "astrid/core/timeline/projection.py",
}

ALLOWED_BARE_RAISES: dict[tuple[str, int], str] = {
    ('astrid/core/element/cli.py', 282): 'wrapped by element.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 546): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 605): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 607): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 612): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 614): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 748): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 752): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 770): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 775): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 778): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 782): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 800): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/executor/cli.py', 805): 'wrapped by executor.main() into AstridError before operator output',
    ('astrid/core/orchestrator/cli.py', 602): 'wrapped by orchestrator.main() into AstridError before operator output',
    ('astrid/core/orchestrator/cli.py', 625): 'wrapped by orchestrator.main() into AstridError before operator output',
    ('astrid/core/orchestrator/cli.py', 656): 'wrapped by orchestrator.main() into AstridError before operator output',
    ('astrid/core/orchestrator/cli.py', 660): 'wrapped by orchestrator.main() into AstridError before operator output',
    ('astrid/core/orchestrator/cli.py', 667): 'wrapped by orchestrator.main() into AstridError before operator output',
    ('astrid/core/project/cli.py', 244): 'wrapped by project.main() into AstridError before operator output',
    ('astrid/core/project/cli.py', 432): 'wrapped by project.main() into AstridError before operator output',
    ('astrid/core/project/cli.py', 434): 'wrapped by project.main() into AstridError before operator output',
    ('astrid/core/project/cli.py', 443): 'wrapped by project.main() into AstridError before operator output',
    ('astrid/core/session/cli.py', 94): 'caught by cmd_attach() and rendered as attach guidance nearby',
    ('astrid/doctor.py', 285): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 294): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 303): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 312): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 329): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 331): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 333): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 335): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 347): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 365): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 452): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 456): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 460): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 463): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 525): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 529): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 533): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 536): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 627): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/doctor.py', 649): 'captured by doctor._capture_check and rendered as a structured check result',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 56): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 58): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 60): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 61): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 63): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 64): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 66): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 68): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 70): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 72): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 73): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 75): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 76): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 78): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 79): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 81): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 82): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 84): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 88): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 90): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 114): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/editorial/executors/quote_scout/run.py', 116): 'wrapped by quote_scout.main() via run_pack_main before agent-facing output',
    ('astrid/packs/reigh/executors/reigh_data/run.py', 67): 'wrapped by reigh_data.main() into AstridError before agent-facing output',
    ('astrid/packs/reigh/executors/reigh_data/run.py', 69): 'wrapped by reigh_data.main() into AstridError before agent-facing output',
    ('astrid/packs/training/executors/pool_build/run.py', 41): 'wrapped by pool_build.main() via run_pack_main before agent-facing output',
    ('astrid/packs/training/executors/pool_build/run.py', 55): 'wrapped by pool_build.main() via run_pack_main before agent-facing output',
    ('astrid/packs/training/executors/pool_build/run.py', 78): 'wrapped by pool_build.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 56): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 58): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 60): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 61): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 63): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 64): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 66): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 69): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 71): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 82): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 84): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 85): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 87): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 89): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 90): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 92): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 93): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 95): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 96): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 98): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 100): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 102): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 103): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 105): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 109): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 111): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 205): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
    ('astrid/packs/understanding/executors/scene_describe/run.py', 207): 'wrapped by scene_describe.main() via run_pack_main before agent-facing output',
}
ALLOWED_STDERR_SITES: dict[tuple[str, int], str] = {
    ('astrid/core/element/cli.py', 31): 'shared stderr helper for override diagnostics',
    ('astrid/core/executor/cli.py', 37): 'shared stderr helper for command previews and override diagnostics',
    ('astrid/core/orchestrator/cli.py', 38): 'shared stderr helper for command previews and override diagnostics',
    ('astrid/packs/cli.py', 40): 'shared stderr helper for non-fatal warnings and diagnostics',
    ('astrid/packs/cli.py', 1676): 'empty search query diagnostic',
    ('astrid/packs/editorial/executors/refine/run.py', 711): 'informational managed-mode diagnostic, not a user-facing error path',
    ('astrid/packs/editorial/executors/script_pipeline/run.py', 133): 'retry progress logging inside DeepSeekClient.complete(); not a user-facing error exit',
    ('astrid/packs/generation/executors/generate_video/run.py', 879): 'non-fatal warning: skipping row in batch loop due to model/backend mismatch',
    ('astrid/packs/generation/executors/generate_video/run.py', 899): 'non-fatal warning: skipping row in batch loop due to missing required features',
    ('astrid/packs/iteration/executors/assemble/run.py', 133): 'managed-mode informational diagnostic printed before success-path execution proceeds',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 441): 'progress message: FAL upscaling frame X/Y — informational batch-loop status, not an error exit',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 444): 'progress message: FAL upscaling frame X/Y — informational batch-loop status, not an error exit',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 1150): 'non-fatal warning: animated WebP export failed — program continues with null animated_webp_path',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 1153): 'non-fatal warning: animated WebP export failed — program continues with null animated_webp_path',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 1261): 'progress message: Calling model for size — informational pre-API-call status, not an error exit',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 1264): 'progress message: Calling model for size — informational pre-API-call status, not an error exit',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 1269): 'progress message: Sprite sheet completed in Xs — informational post-API-call summary, not an error exit',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 1272): 'progress message: Post-processing existing sprite sheet — informational mode indicator, not an error exit',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 1275): 'progress message: Post-processing existing sprite sheet — informational mode indicator, not an error exit',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 1302): 'non-fatal warning: frame(s) touch safety edge — program continues to assemble outputs',
    ('astrid/packs/rendering/executors/sprite_sheet/run.py', 1305): 'non-fatal warning: frame(s) touch safety edge — program continues to assemble outputs',
    ('astrid/packs/understanding/executors/video_understand/run.py', 274): 'progress message: querying model/window/video during batch loop — informational status, not an error exit',
    ('astrid/packs/understanding/executors/video_understand/run.py', 319): 'success confirmation: wrote output path — informational post-write summary, not an error exit',
    ('astrid/packs/understanding/executors/visual_understand/run.py', 429): 'progress message: querying model/image during batch loop — informational status, not an error exit',
    ('astrid/packs/understanding/executors/visual_understand/run.py', 476): 'success confirmation: wrote output path — informational post-write summary, not an error exit',
    ('astrid/packs/youtube/executors/youtube_audio/run.py', 99): 'intentional command preview for pack subprocess diagnostics',
    ('astrid/packs/youtube/executors/youtube_audio/run.py', 115): 'intentional success summary for pack subprocess diagnostics',
    ('astrid/pipeline.py', 152): 'auto-resolved session hint is an intentional shared advisory',
    ('astrid/pipeline.py', 215): 'canonical AstridError renderer',
    ('astrid/pipeline.py', 216): 'canonical AstridError renderer',
    ('astrid/pipeline.py', 218): 'canonical AstridError renderer',
    ('astrid/pipeline.py', 220): 'canonical AstridError renderer',
    ('astrid/pipeline.py', 222): 'canonical AstridError renderer',
    ('astrid/pipeline.py', 257): 'documented unbound-session recovery hint',
    ('astrid/pipeline.py', 258): 'documented unbound-session recovery hint',
}


_PARSER_SURFACE_SCRIPT = r"""
from __future__ import annotations

import argparse
import importlib
import json
import sys

from astrid.core.cli_choices import RegistryChoices, StaticChoices


def _action_payload(
    action: argparse.Action,
    *,
    parser_path: tuple[str, ...],
) -> dict[str, object] | None:
    if isinstance(action, argparse._SubParsersAction):
        return None
    choices = getattr(action, "choices", None)
    if choices is None:
        return None
    if isinstance(choices, (RegistryChoices, StaticChoices)):
        valid_options = list(choices.valid_options)
    else:
        valid_options = [str(value) for value in choices]
    return {
        "parser_path": list(parser_path),
        "dest": action.dest,
        "option_strings": list(action.option_strings),
        "choices_class": type(choices).__name__,
        "catalog": getattr(choices, "catalog", None),
        "valid_options": valid_options,
    }


def _collect_enum_args(
    parser: argparse.ArgumentParser,
    *,
    parser_path: tuple[str, ...],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for action in parser._actions:
        payload = _action_payload(action, parser_path=parser_path)
        if payload is not None:
            rows.append(payload)
        if isinstance(action, argparse._SubParsersAction):
            for name, child in sorted(action.choices.items()):
                rows.extend(_collect_enum_args(child, parser_path=(*parser_path, name)))
    return rows


module_name, builder_name = sys.argv[1], sys.argv[2]
module = importlib.import_module(module_name)
parser = getattr(module, builder_name)()
print(
    json.dumps(
        {
            "prog": getattr(parser, "prog", None),
            "enum_args": _collect_enum_args(parser, parser_path=()),
        },
        sort_keys=True,
    )
)
"""


def _module_name(path: Path) -> str:
    return path.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".")


def _iter_parser_surface_files() -> list[tuple[Path, str]]:
    surfaces: list[tuple[Path, str]] = []
    for path in sorted(ASTRID_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        builders = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {"build_parser", "_build_parser"}
        ]
        if not builders:
            continue
        builder_name = "_build_parser" if "_build_parser" in builders else "build_parser"
        relative = path.relative_to(ASTRID_ROOT).as_posix()
        if (
            relative.endswith("/cli.py")
            or relative in {"doctor.py", "setup_cli.py"}
            or relative.startswith("packs/")
        ):
            surfaces.append((path, builder_name))
    return surfaces


def _normalize_skip_reason(stderr: str, stdout: str, returncode: int) -> str:
    text = (stderr or stdout).strip()
    if not text:
        return f"builder subprocess exited {returncode}"
    first_line = text.splitlines()[0].strip()
    if "not meant to be invoked directly" in text:
        return "direct pack entrypoint guard exits before parser construction"
    return first_line


def _scan_parser_surfaces() -> dict[str, object]:
    expected_surfaces: list[dict[str, str]] = []
    scanned_surfaces: list[dict[str, object]] = []
    skipped_surfaces: list[dict[str, str]] = []
    enum_choice_findings: list[dict[str, object]] = []
    subprocess_env = dict(os.environ)
    subprocess_env["ASTRID_INTERNAL_INVOCATION"] = "1"

    for path, builder_name in _iter_parser_surface_files():
        module_name = _module_name(path)
        surface = {
            "module": module_name,
            "builder": builder_name,
            "path": path.relative_to(ROOT).as_posix(),
        }
        expected_surfaces.append(surface)

        completed = subprocess.run(
            [sys.executable, "-c", _PARSER_SURFACE_SCRIPT, module_name, builder_name],
            cwd=ROOT,
            capture_output=True,
            env=subprocess_env,
            text=True,
        )
        if completed.returncode != 0:
            skipped_surfaces.append(
                {
                    **surface,
                    "reason": _normalize_skip_reason(
                        completed.stderr,
                        completed.stdout,
                        completed.returncode,
                    ),
                }
            )
            continue

        payload = json.loads(completed.stdout)
        enum_args = payload["enum_args"]
        scanned_surfaces.append(
            {
                **surface,
                "prog": payload["prog"],
                "enum_arg_count": len(enum_args),
            }
        )

        for enum_arg in enum_args:
            choices_class = enum_arg["choices_class"]
            if choices_class in {"RegistryChoices", "StaticChoices"}:
                continue
            enum_choice_findings.append(
                {
                    "module": module_name,
                    "path": surface["path"],
                    "parser_path": enum_arg["parser_path"],
                    "option_strings": enum_arg["option_strings"],
                    "dest": enum_arg["dest"],
                    "choices_class": choices_class,
                    "valid_options": enum_arg["valid_options"],
                }
            )

    return {
        "expected_parser_surfaces": expected_surfaces,
        "scanned_parser_surfaces": scanned_surfaces,
        "skipped_parser_surfaces": skipped_surfaces,
        "non_kind_enum_findings": enum_choice_findings,
    }


def _iter_kind_arg_findings() -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []

    for path, _builder_name in _iter_parser_surface_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            flags: list[str] = []
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    flags.append(arg.value)
            if "--kind" not in flags:
                continue

            if isinstance(node.func, ast.Name) and node.func.id == "add_kind_arg":
                continue

            choices_expr = None
            for keyword in node.keywords:
                if keyword.arg == "choices":
                    choices_expr = ast.get_source_segment(source, keyword.value)
                    break

            call_target = ast.get_source_segment(source, node.func) or ""
            parser_hint = call_target.lower()
            choices_hint = (choices_expr or "").lower()
            if not any(token in parser_hint or token in choices_hint for token in ("clip", "track", "transition")):
                continue

            findings.append(
                {
                    "path": rel,
                    "line": node.lineno,
                    "flags": flags,
                    "call": ast.get_source_segment(source, node.func) or "<unknown>",
                    "choices_expr": choices_expr,
                }
            )
    return findings


def _ast_scan_paths() -> list[Path]:
    parser_paths = {path for path, _builder_name in _iter_parser_surface_files()}
    extra_paths = {ROOT / relative for relative in AST_EXTRA_PATHS}
    return sorted(parser_paths | extra_paths)


def _direct_stderr_kind(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name) and node.func.id == "print":
        for keyword in node.keywords:
            if (
                keyword.arg == "file"
                and isinstance(keyword.value, ast.Attribute)
                and isinstance(keyword.value.value, ast.Name)
                and keyword.value.value.id == "sys"
                and keyword.value.attr == "stderr"
            ):
                return "print"
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "write"
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "sys"
        and node.func.value.attr == "stderr"
    ):
        return "write"
    return None


def _iter_ast_findings() -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in _ast_scan_paths():
        rel = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Raise)
                and isinstance(node.exc, ast.Call)
                and isinstance(node.exc.func, ast.Name)
                and node.exc.func.id in {"ValueError", "RuntimeError"}
            ):
                key = (rel, node.lineno)
                if key in ALLOWED_BARE_RAISES:
                    continue
                findings.append(
                    {
                        "kind": "bare_raise",
                        "path": rel,
                        "line": node.lineno,
                        "exception": node.exc.func.id,
                        "source": ast.get_source_segment(source, node) or "",
                    }
                )
            if not isinstance(node, ast.Call):
                continue
            stderr_kind = _direct_stderr_kind(node)
            if stderr_kind is None:
                continue
            key = (rel, node.lineno)
            if key in ALLOWED_STDERR_SITES:
                continue
            findings.append(
                {
                    "kind": "direct_stderr",
                    "path": rel,
                    "line": node.lineno,
                    "stderr_kind": stderr_kind,
                    "source": ast.get_source_segment(source, node) or "",
                }
            )
    return sorted(findings, key=lambda item: (item["path"], item["line"], item["kind"]))


def collect_recoverability_conformance_worklist() -> dict[str, object]:
    parser_scan = _scan_parser_surfaces()
    return {
        "mode": "zero",
        "expected_parser_surface_count": len(parser_scan["expected_parser_surfaces"]),
        "scanned_parser_surface_count": len(parser_scan["scanned_parser_surfaces"]),
        "skipped_parser_surface_count": len(parser_scan["skipped_parser_surfaces"]),
        "expected_parser_surfaces": parser_scan["expected_parser_surfaces"],
        "scanned_parser_surfaces": parser_scan["scanned_parser_surfaces"],
        "skipped_parser_surfaces": parser_scan["skipped_parser_surfaces"],
        "kind_arg_findings": _iter_kind_arg_findings(),
        "non_kind_enum_findings": parser_scan["non_kind_enum_findings"],
        "ast_findings": _iter_ast_findings(),
    }


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_recoverability_conformance_zero_mode() -> None:
    """Final zero mode: the scanner must produce zero findings across ALL categories.

    Rejects:
    * Inline enum choices outside ``RegistryChoices`` / ``StaticChoices``
    * User-facing bare ``ValueError`` / ``RuntimeError`` raises
    * Bespoke user-facing ``sys.stderr`` renderers (print/write)
    * Unscanned expected parser surfaces

    The allowlists (``ALLOWED_BARE_RAISES`` / ``ALLOWED_STDERR_SITES``) are the
    only mechanism for exempting a finding — every exempted site must carry an
    explicit reason in the allowlist so reviewers can audit it.
    """
    payload = collect_recoverability_conformance_worklist()

    kind_findings: list[dict[str, object]] = payload["kind_arg_findings"]
    enum_findings: list[dict[str, object]] = payload["non_kind_enum_findings"]
    ast_findings: list[dict[str, object]] = payload["ast_findings"]
    skipped_count: int = payload["skipped_parser_surface_count"]

    failure_msgs: list[str] = []

    if kind_findings:
        failure_msgs.append(
            f"{len(kind_findings)} --kind argument(s) not using add_kind_arg(): "
            + "; ".join(
                f"{f['path']}:{f['line']} ({f.get('call', '?')})"
                for f in kind_findings
            )
        )

    if enum_findings:
        failure_msgs.append(
            f"{len(enum_findings)} enum-choice argument(s) outside "
            f"RegistryChoices/StaticChoices: "
            + "; ".join(
                f"{f['path']} [{f.get('dest', '?')}] ({f.get('choices_class', '?')})"
                for f in enum_findings
            )
        )

    if ast_findings:
        failure_msgs.append(
            f"{len(ast_findings)} AST finding(s) (bare raises / direct stderr): "
            + "; ".join(
                f"{f['path']}:{f['line']} ({f['kind']})"
                for f in ast_findings[:20]
            )
            + (" ..." if len(ast_findings) > 20 else "")
        )

    if skipped_count > 0:
        skipped_surfaces = payload.get("skipped_parser_surfaces", [])
        failure_msgs.append(
            f"{skipped_count} unscanned expected parser surface(s): "
            + "; ".join(
                f"{s['path']} ({s.get('reason', '?')})"
                for s in skipped_surfaces[:10]
            )
            + (" ..." if skipped_count > 10 else "")
        )

    assert not failure_msgs, (
        "Recoverability conformance scanner found findings that must be addressed:\n\n"
        + "\n\n".join(failure_msgs)
        + "\n\n"
        + "See ALLOWED_BARE_RAISES / ALLOWED_STDERR_SITES in this module for the "
        + "exemption mechanism.  Every exempted site must carry an explicit reason."
    )
