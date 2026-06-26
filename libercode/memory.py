from typing import Optional
from libercode.storage.sqlite_store import SqliteStore
from libercode.storage.file_store import FileStore


class ProjectMemory:
    def __init__(self, store):
        self._store = store

    def remember(self, key: str, value: str, category: str = "general"):
        self._store.memory_set(key, value, category)

    def recall(self, key: str) -> Optional[str]:
        return self._store.memory_get(key)

    def search(self, query: str, category: Optional[str] = None) -> list:
        return self._store.memory_search(query, category)

    def forget(self, key: str):
        self._store.memory_delete(key)

    def all(self, category: Optional[str] = None) -> list:
        return self._store.memory_all(category)

    def auto_store_context(self, key: str, content: str):
        summary = content[:500] if len(content) > 500 else content
        self.remember(key, summary, "auto_context")

    def summarize_project(self, store) -> str:
        memories = self.all("auto_context")
        if not memories:
            return ""
        parts = [f"- {m['key']}: {m['value'][:200]}" for m in memories[-20:]]
        return "Project knowledge:\n" + "\n".join(parts)
