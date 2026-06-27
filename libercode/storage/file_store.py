import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


@contextmanager
def _file_lock(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.touch(exist_ok=True)
    if sys.platform == "win32":
        import msvcrt
        with open(lock_path, "r+b") as f:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                pass
            try:
                yield
            finally:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
    else:
        import fcntl
        with open(lock_path, "r+b") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FileStore:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._paths = {
            "memory": self.data_dir / "memory.json",
            "tasks": self.data_dir / "tasks.json",
            "checkpoints": self.data_dir / "checkpoints",
            "scratch": self.data_dir / "scratch.json",
            "sessions": self.data_dir / "sessions.json",
            "history": self.data_dir / "history",
        }
        self._ensure_files()

    def _ensure_files(self):
        for p in self._paths.values():
            if p.suffix == ".json":
                if not p.exists():
                    p.write_text("[]")
            elif not p.exists():
                p.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path: Path) -> list:
        if path.exists():
            return json.loads(path.read_text())
        return []

    def _write_json(self, path: Path, data: list):
        with _file_lock(path):
            path.write_text(json.dumps(data, indent=2, default=str))

    def _next_id(self, items: list) -> int:
        if not items:
            return 1
        return max(item.get("id", 0) for item in items) + 1

    def memory_set(self, key: str, value: str, category: str = "general"):
        items = self._read_json(self._paths["memory"])
        for item in items:
            if item["key"] == key:
                item["value"] = value
                item["category"] = category
                item["updated_at"] = _now()
                self._write_json(self._paths["memory"], items)
                return
        items.append(
            {
                "key": key,
                "value": value,
                "category": category,
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
        self._write_json(self._paths["memory"], items)

    def memory_get(self, key: str) -> Optional[str]:
        for item in self._read_json(self._paths["memory"]):
            if item["key"] == key:
                return item["value"]
        return None

    def memory_search(self, query: str, category: Optional[str] = None) -> list:
        results = []
        for item in self._read_json(self._paths["memory"]):
            if category and item.get("category") != category:
                continue
            if (
                query.lower() in item["key"].lower()
                or query.lower() in item["value"].lower()
            ):
                results.append(item)
        return results

    def memory_delete(self, key: str):
        items = self._read_json(self._paths["memory"])
        items = [i for i in items if i["key"] != key]
        self._write_json(self._paths["memory"], items)

    def memory_all(self, category: Optional[str] = None) -> list:
        items = self._read_json(self._paths["memory"])
        if category:
            return [i for i in items if i.get("category") == category]
        return items

    def task_create(
        self,
        title: str,
        description: str = "",
        parent_id: Optional[int] = None,
        mode: str = "build",
        priority: str = "medium",
    ) -> int:
        items = self._read_json(self._paths["tasks"])
        tid = self._next_id(items)
        items.append(
            {
                "id": tid,
                "title": title,
                "description": description,
                "parent_id": parent_id,
                "status": "pending",
                "mode": mode,
                "priority": priority,
                "progress": 0.0,
                "checkpoint_id": None,
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
        self._write_json(self._paths["tasks"], items)
        return tid

    def task_update(self, task_id: int, **kwargs):
        items = self._read_json(self._paths["tasks"])
        allowed = {
            "status",
            "progress",
            "checkpoint_id",
            "title",
            "description",
            "priority",
        }
        for item in items:
            if item["id"] == task_id:
                for k, v in kwargs.items():
                    if k in allowed:
                        item[k] = v
                item["updated_at"] = _now()
                break
        self._write_json(self._paths["tasks"], items)

    def task_get(self, task_id: int) -> Optional[dict]:
        for item in self._read_json(self._paths["tasks"]):
            if item["id"] == task_id:
                return item
        return None

    def task_list(
        self, status: Optional[str] = None, mode: Optional[str] = None
    ) -> list:
        items = self._read_json(self._paths["tasks"])
        if status:
            items = [i for i in items if i["status"] == status]
        if mode:
            items = [i for i in items if i.get("mode") == mode]
        return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)

    def task_tree(self) -> list:
        items = self._read_json(self._paths["tasks"])

        def build_tree(parent_id=None, depth=0):
            result = []
            for item in items:
                if item.get("parent_id") == parent_id:
                    item["_depth"] = depth
                    result.append(item)
                    result.extend(build_tree(item["id"], depth + 1))
            return result

        return build_tree()

    def checkpoint_save(
        self, checkpoint_id: str, task_id: Optional[int], summary: str, snapshot: dict
    ):
        path = self._paths["checkpoints"] / f"{checkpoint_id}.json"
        path.write_text(
            json.dumps(
                {
                    "id": checkpoint_id,
                    "task_id": task_id,
                    "summary": summary,
                    "snapshot": snapshot,
                    "created_at": _now(),
                },
                indent=2,
                default=str,
            )
        )

    def checkpoint_get(self, checkpoint_id: str) -> Optional[dict]:
        path = self._paths["checkpoints"] / f"{checkpoint_id}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    def checkpoint_list(self, task_id: Optional[int] = None) -> list:
        results = []
        for f in sorted(self._paths["checkpoints"].iterdir(), reverse=True):
            if f.suffix == ".json":
                data = json.loads(f.read_text())
                if task_id is None or data.get("task_id") == task_id:
                    results.append(data)
        return results

    def scratch_create(self, title: str, content: str = "", tags: str = "") -> int:
        items = self._read_json(self._paths["scratch"])
        nid = self._next_id(items)
        items.append(
            {
                "id": nid,
                "title": title,
                "content": content,
                "tags": tags,
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
        self._write_json(self._paths["scratch"], items)
        return nid

    def scratch_update(self, note_id: int, **kwargs):
        items = self._read_json(self._paths["scratch"])
        allowed = {"title", "content", "tags"}
        for item in items:
            if item["id"] == note_id:
                for k, v in kwargs.items():
                    if k in allowed:
                        item[k] = v
                item["updated_at"] = _now()
                break
        self._write_json(self._paths["scratch"], items)

    def scratch_get(self, note_id: int) -> Optional[dict]:
        for item in self._read_json(self._paths["scratch"]):
            if item["id"] == note_id:
                return item
        return None

    def scratch_list(self, tag: Optional[str] = None) -> list:
        items = self._read_json(self._paths["scratch"])
        if tag:
            items = [i for i in items if tag in i.get("tags", "")]
        return sorted(items, key=lambda x: x.get("updated_at", ""), reverse=True)

    def session_start(self, project_root: str, mode: str = "build") -> int:
        items = self._read_json(self._paths["sessions"])
        sid = self._next_id(items)
        items.append(
            {
                "id": sid,
                "project_root": project_root,
                "mode": mode,
                "turn_count": 0,
                "summary": "",
                "is_active": True,
                "started_at": _now(),
                "ended_at": None,
            }
        )
        self._write_json(self._paths["sessions"], items)
        return sid

    def session_end(self, session_id: int, summary: str = ""):
        items = self._read_json(self._paths["sessions"])
        for item in items:
            if item["id"] == session_id:
                item["is_active"] = False
                item["ended_at"] = _now()
                item["summary"] = summary
                break
        self._write_json(self._paths["sessions"], items)

    def session_get(self, session_id: int) -> Optional[dict]:
        for item in self._read_json(self._paths["sessions"]):
            if item["id"] == session_id:
                return item
        return None

    def session_get_active(self, project_root: str) -> Optional[dict]:
        for item in reversed(self._read_json(self._paths["sessions"])):
            if item.get("project_root") == project_root and item.get("is_active"):
                return item
        return None

    def session_list(self, project_root: Optional[str] = None) -> list:
        items = self._read_json(self._paths["sessions"])
        if project_root:
            items = [i for i in items if i.get("project_root") == project_root]
        return sorted(items, key=lambda x: x.get("started_at", ""), reverse=True)[:20]

    def history_append(
        self, session_id: int, role: str, content: str, mode: Optional[str] = None
    ):
        history_dir = self._paths["history"]
        file_path = history_dir / f"session_{session_id}.jsonl"
        entry = json.dumps(
            {
                "role": role,
                "content": content,
                "mode": mode,
                "timestamp": _now(),
            }
        )
        with open(file_path, "a") as f:
            f.write(entry + "\n")

    def history_get(self, session_id: int, limit: int = 50) -> list:
        file_path = self._paths["history"] / f"session_{session_id}.jsonl"
        if not file_path.exists():
            return []
        entries = []
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries[-limit:]
