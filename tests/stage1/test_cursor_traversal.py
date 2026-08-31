from __future__ import annotations

from astrid.sdk.remote import RemoteAstridClient, RemoteProjects, RemoteTasks
from astrid.sdk.workspace_client import WorkspaceClient, WorkspaceClientError, paged_rows


def test_paged_rows_traverses_all_pages_with_canonical_arguments() -> None:
    calls: list[tuple[str | None, int]] = []

    def reader(*, cursor: str | None, limit: int):
        calls.append((cursor, limit))
        if cursor is None:
            return [[{"id": 1}], "next-1"]
        assert cursor == "next-1"
        return [[{"id": 2}], None]

    assert paged_rows(reader, limit=1) == [{"id": 1}, {"id": 2}]
    assert calls == [(None, 1), ("next-1", 1)]


def test_paged_rows_rejects_missing_or_malformed_page_pairs() -> None:
    assert paged_rows(lambda *, cursor, limit: [{"id": 1}]) is None
    assert paged_rows(lambda *, cursor, limit: {"items": [], "next_cursor": None}) is None
    assert paged_rows(lambda *, cursor, limit: [[{"id": 1}], "bad cursor"]) is None


def test_paged_rows_rejects_cursor_cycles_and_unbounded_pages() -> None:
    def cycle(*, cursor: str | None, limit: int):
        return [[], "same" if cursor is None else "same"]

    assert paged_rows(cycle) is None

    def endless(*, cursor: str | None, limit: int):
        return [[], f"cursor-{cursor or 0}"]

    assert paged_rows(endless, max_pages=2) is None


def test_remote_projects_exposes_cursor_and_limit() -> None:
    seen: list[tuple[str | None, int]] = []

    class Client:
        def list_projects(self, *, cursor=None, limit=50):
            seen.append((cursor, limit))
            return [[], None]

    result = RemoteProjects(Client()).list(cursor="start", limit=7)
    assert result.ok
    assert seen == [("start", 7)]


def test_remote_task_create_exhausts_capability_pages() -> None:
    calls: list[str | None] = []

    class Client:
        def list_capabilities(self, *, cursor=None, limit=50):
            calls.append(cursor)
            if cursor is None:
                return [[{"capability_id": "other", "definition_digest": "digest-other"}], "cap-2"]
            assert cursor == "cap-2"
            return [[{"capability_id": "target", "definition_digest": "digest-target"}], None]

        def admit_task(self, **kwargs):
            return {"task_id": "task-1", **kwargs}

    result = RemoteTasks(Client()).create(
        project_id="project-1", capability="target", spec={}, idempotency_key="task-1"
    )
    assert result.ok
    assert result.data["task_id"] == "task-1"
    assert calls == [None, "cap-2"]


def test_remote_invoke_fails_closed_on_capability_cursor_cycle() -> None:
    class Client:
        def list_capabilities(self, *, cursor=None, limit=50):
            return [[{"capability_id": "target", "definition_digest": "digest-target"}], "loop"]

    result = RemoteAstridClient(Client()).invoke(
        "target", project_id="project-1", spec={}, idempotency_key="task-1"
    )
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "protocol_error"


def test_workspace_capability_wrapper_rejects_malformed_page() -> None:
    client = WorkspaceClient.__new__(WorkspaceClient)
    client._call_generated = lambda operation, **kwargs: [{"capability_id": "target"}]
    try:
        client.list_capabilities()
    except WorkspaceClientError as exc:
        assert exc.code == "protocol_error"
    else:
        raise AssertionError("malformed capability page was accepted")
