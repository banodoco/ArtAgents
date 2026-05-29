from __future__ import annotations

from astrid.core.project.paths import PROJECTS_ROOT_ENV
from astrid.core.project.run import PROJECT_RUN_ENV
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.paths import ASTRID_HOME_ENV
from astrid.core.subprocess_env import (
    ASTRID_ACTOR,
    ASTRID_INTERNAL_INVOCATION,
    SubprocessEnvPolicyError,
    TASK_ITEM_ID_ENV,
    TASK_ITERATION_ENV,
    TASK_PROJECT_ENV,
    TASK_RUN_ID_ENV,
    TASK_STEP_ID_ENV,
    build_child_subprocess_env,
)
from astrid.core.task.env import child_subprocess_env

import pytest


def test_canonical_policy_strips_secret_like_and_unknown_host_variables() -> None:
    env = build_child_subprocess_env(
        base={
            "PATH": "/bin",
            "OPENAI_API_KEY": "secret",
            "CUSTOM_TOKEN": "secret",
            "UNRELATED_HOST_VAR": "nope",
        },
        parent={},
    )

    assert env == {"PATH": "/bin"}


def test_canonical_policy_preserves_safe_base_variables() -> None:
    env = build_child_subprocess_env(
        base={
            "HOME": "/tmp/home",
            "LANG": "C.UTF-8",
            "PATH": "/bin",
            "TMPDIR": "/tmp",
            "PYENV_VERSION": "3.11.11",
        },
        parent={},
    )

    assert env == {
        "HOME": "/tmp/home",
        "LANG": "C.UTF-8",
        "PATH": "/bin",
        "TMPDIR": "/tmp",
        "PYENV_VERSION": "3.11.11",
    }


def test_canonical_policy_propagates_task_session_iteration_item_and_project_state() -> None:
    parent = {
        ASTRID_HOME_ENV: "/tmp/astrid-home",
        ASTRID_SESSION_ID_ENV: "S-1",
        PROJECTS_ROOT_ENV: "/tmp/projects",
        PROJECT_RUN_ENV: "project-run-1",
        ASTRID_INTERNAL_INVOCATION: "1",
        TASK_RUN_ID_ENV: "task-run-1",
        TASK_PROJECT_ENV: "demo",
        TASK_STEP_ID_ENV: "group/leaf",
        TASK_ITEM_ID_ENV: "item-a",
        TASK_ITERATION_ENV: "002",
    }

    env = build_child_subprocess_env(base={}, parent=parent)

    for key, value in parent.items():
        assert env[key] == value


def test_child_subprocess_env_delegates_to_canonical_policy_with_parent_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TASK_RUN_ID_ENV, "from-parent")
    monkeypatch.setenv(TASK_PROJECT_ENV, "demo")
    monkeypatch.setenv(TASK_STEP_ID_ENV, "step-1")

    env = child_subprocess_env(base={TASK_RUN_ID_ENV: "from-base", "PATH": "/bin"})

    assert env[TASK_RUN_ID_ENV] == "from-parent"
    assert env[TASK_PROJECT_ENV] == "demo"
    assert env[TASK_STEP_ID_ENV] == "step-1"
    assert env["PATH"] == "/bin"


def test_policy_removes_actor_from_even_safe_or_explicit_base() -> None:
    env = build_child_subprocess_env(
        base={ASTRID_ACTOR: "agent:demo"},
        parent={},
        passthrough=[ASTRID_ACTOR],
        declared_passthrough=[ASTRID_ACTOR],
    )

    assert ASTRID_ACTOR not in env


def test_declared_passthrough_is_preserved_when_requested() -> None:
    env = build_child_subprocess_env(
        base={"CUSTOM_PUBLIC_FLAG": "yes", "PATH": "/bin"},
        parent={},
        passthrough=["CUSTOM_PUBLIC_FLAG"],
        declared_passthrough=["CUSTOM_PUBLIC_FLAG"],
    )

    assert env["CUSTOM_PUBLIC_FLAG"] == "yes"
    assert env["PATH"] == "/bin"


def test_explicit_env_is_preserved_without_host_spread() -> None:
    env = build_child_subprocess_env(
        base={"PATH": "/bin", "UNDECLARED_HOST": "no"},
        parent={},
        explicit_env={"COMMAND_FLAG": "yes"},
    )

    assert env["PATH"] == "/bin"
    assert env["COMMAND_FLAG"] == "yes"
    assert "UNDECLARED_HOST" not in env


def test_undeclared_passthrough_is_rejected_at_policy_level() -> None:
    with pytest.raises(SubprocessEnvPolicyError, match="without declaration"):
        build_child_subprocess_env(
            base={"CUSTOM_PUBLIC_FLAG": "yes"},
            parent={},
            passthrough=["CUSTOM_PUBLIC_FLAG"],
            declared_passthrough=[],
        )


def test_secret_like_declared_passthrough_is_rejected() -> None:
    with pytest.raises(SubprocessEnvPolicyError, match="looks secret-like"):
        build_child_subprocess_env(
            base={"OPENAI_API_KEY": "secret"},
            parent={},
            passthrough=["OPENAI_API_KEY"],
            declared_passthrough=["OPENAI_API_KEY"],
        )
