from __future__ import annotations

from astrid.sdk.remote import RemoteTasks


class _Client:
    def list_capabilities(self):
        return [{"capability_id": "render.basic", "definition_digest": "sha256:" + "a" * 64}]

    def get_project(self, ref):
        assert ref == "cold"
        return {"project_id": "project-1", "slug": "cold"}

    def admit_task(self, **kwargs):
        assert kwargs["project_id"] == "project-1"
        return {"task_id": "task-1", "run_id": "run-1", "state": "queued"}


def test_task_create_resolves_project_slug_before_admission():
    result = RemoteTasks(_Client()).create(
        project_id="cold",
        capability="render.basic",
        spec={"message": "hello"},
        idempotency_key="task-1",
    )
    assert result.ok
