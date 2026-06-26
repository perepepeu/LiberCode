from typing import Optional


class TaskTracker:
    def __init__(self, store):
        self._store = store

    def create(
        self,
        title: str,
        description: str = "",
        parent_id: Optional[int] = None,
        mode: str = "build",
        priority: str = "medium",
    ) -> int:
        return self._store.task_create(title, description, parent_id, mode, priority)

    def update(self, task_id: int, **kwargs):
        self._store.task_update(task_id, **kwargs)

    def start(self, task_id: int):
        self._store.task_update(task_id, status="in_progress")

    def complete(self, task_id: int):
        self._store.task_update(task_id, status="completed", progress=1.0)

    def fail(self, task_id: int, reason: str = ""):
        self._store.task_update(task_id, status="failed", description=reason)

    def pause(self, task_id: int):
        self._store.task_update(task_id, status="paused")

    def resume(self, task_id: int):
        self._store.task_update(task_id, status="in_progress")

    def get(self, task_id: int) -> Optional[dict]:
        return self._store.task_get(task_id)

    def list(self, status: Optional[str] = None, mode: Optional[str] = None) -> list:
        return self._store.task_list(status, mode)

    def tree(self) -> list:
        return self._store.task_tree()

    def find_paused(self) -> list:
        return self._store.task_list(status="paused")

    def pending_tasks(self) -> list:
        return self._store.task_list(status="pending")
