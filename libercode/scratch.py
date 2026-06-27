from typing import Optional


class ScratchNotes:
    def __init__(self, store):
        self._store = store

    def write(self, title: str, content: str = "", tags: str = "") -> int:
        return self._store.scratch_create(title, content, tags)

    def append(self, note_id: int, content: str):
        note = self._store.scratch_get(note_id)
        if note:
            new_content = note["content"] + "\n" + content
            self._store.scratch_update(note_id, content=new_content)

    def update(self, note_id: int, **kwargs):
        self._store.scratch_update(note_id, **kwargs)

    def get(self, note_id: int) -> Optional[dict]:
        return self._store.scratch_get(note_id)

    def list(self, tag: Optional[str] = None) -> list:
        return self._store.scratch_list(tag)

    def search(self, query: str) -> list:
        if hasattr(self._store, "scratch_search"):
            return self._store.scratch_search(query)
        results = []
        for note in self._store.scratch_list():
            if (
                query.lower() in note.get("title", "").lower()
                or query.lower() in note.get("content", "").lower()
            ):
                results.append(note)
        return results
