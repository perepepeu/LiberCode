import json
import time
from pathlib import Path
from typing import Optional


class Checkpointer:
    def __init__(self, store, project_root: str):
        self._store = store
        self._project_root = Path(project_root)

    def save(self, task_id: Optional[int] = None, summary: str = "checkpoint") -> str:
        cid = f"cp_{int(time.time())}_{summary[:20].replace(' ', '_')}"
        snapshot = self._take_snapshot()
        self._store.checkpoint_save(cid, task_id, summary, snapshot)
        return cid

    def restore(self, checkpoint_id: str) -> Optional[dict]:
        return self._store.checkpoint_get(checkpoint_id)

    def list(self, task_id: Optional[int] = None) -> list:
        return self._store.checkpoint_list(task_id)

    def _take_snapshot(self) -> dict:
        snapshot = {
            "timestamp": time.time(),
            "git_status": self._git_snapshot(),
            "files": {},
        }
        py_files = list(self._project_root.rglob("*.py"))[:50]
        for f in py_files:
            try:
                rel = f.relative_to(self._project_root)
                snapshot["files"][str(rel)] = f.read_text(
                    encoding="utf-8", errors="replace"
                )
            except Exception:
                pass
        return snapshot

    def _git_snapshot(self) -> str:
        import subprocess

        try:
            result = subprocess.run(
                ["git", "diff", "--stat"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self._project_root),
            )
            return result.stdout.strip()
        except Exception:
            return ""
