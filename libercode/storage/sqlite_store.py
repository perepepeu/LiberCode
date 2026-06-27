import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


class SqliteStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(
            db_path
        ) else None
        self._conn = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, timeout=30)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER REFERENCES tasks(id),
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium',
                    mode TEXT DEFAULT 'build',
                    progress REAL DEFAULT 0.0,
                    checkpoint_id TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id TEXT PRIMARY KEY,
                    task_id INTEGER REFERENCES tasks(id),
                    summary TEXT DEFAULT '',
                    snapshot TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS scratch_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    tags TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_root TEXT NOT NULL,
                    mode TEXT DEFAULT 'build',
                    turn_count INTEGER DEFAULT 0,
                    summary TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    started_at TEXT DEFAULT (datetime('now')),
                    ended_at TEXT
                );
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER REFERENCES sessions(id),
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    mode TEXT,
                    timestamp TEXT DEFAULT (datetime('now'))
                );
            """)

    def memory_set(self, key: str, value: str, category: str = "general"):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO memory (key, value, category, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    updated_at = datetime('now')
            """,
                (key, value, category),
            )

    def memory_get(self, key: str) -> Optional[str]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM memory WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def memory_search(self, query: str, category: Optional[str] = None) -> list:
        with self._get_conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT key, value, category FROM memory WHERE (key LIKE ? OR value LIKE ?) AND category = ?",
                    (f"%{query}%", f"%{query}%", category),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key, value, category FROM memory WHERE key LIKE ? OR value LIKE ?",
                    (f"%{query}%", f"%{query}%"),
                ).fetchall()
            return [dict(r) for r in rows]

    def memory_delete(self, key: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM memory WHERE key = ?", (key,))

    def memory_all(self, category: Optional[str] = None) -> list:
        with self._get_conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT key, value, category FROM memory WHERE category = ?",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key, value, category FROM memory"
                ).fetchall()
            return [dict(r) for r in rows]

    def task_create(
        self,
        title: str,
        description: str = "",
        parent_id: Optional[int] = None,
        mode: str = "build",
        priority: str = "medium",
    ) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, description, parent_id, mode, priority) VALUES (?, ?, ?, ?, ?)",
                (title, description, parent_id, mode, priority),
            )
            return cur.lastrowid

    def task_update(self, task_id: int, **kwargs):
        allowed = {
            "status",
            "progress",
            "checkpoint_id",
            "title",
            "description",
            "priority",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = "datetime('now')"
        set_clause = ", ".join(f"{k} = ?" for k in fields if k != "updated_at")
        set_clause += ", updated_at = datetime('now')"
        values = [v for k, v in fields.items() if k != "updated_at"]
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?", (*values, task_id)
            )

    def task_get(self, task_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    def task_list(
        self, status: Optional[str] = None, mode: Optional[str] = None
    ) -> list:
        with self._get_conn() as conn:
            query = "SELECT * FROM tasks WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if mode:
                query += " AND mode = ?"
                params.append(mode)
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def task_tree(self, parent_id: Optional[int] = None, indent: int = 0) -> list:
        with self._get_conn() as conn:
            if parent_id is None:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE parent_id IS NULL ORDER BY created_at"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE parent_id = ? ORDER BY created_at",
                    (parent_id,),
                ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["_indent"] = indent
                result.append(d)
                children = self.task_tree(d["id"], indent + 1)
                result.extend(children)
            return result

    def checkpoint_save(
        self, checkpoint_id: str, task_id: Optional[int], summary: str, snapshot: dict
    ):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO checkpoints (id, task_id, summary, snapshot) VALUES (?, ?, ?, ?)",
                (checkpoint_id, task_id, summary, json.dumps(snapshot)),
            )

    def checkpoint_get(self, checkpoint_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE id = ?", (checkpoint_id,)
            ).fetchone()
            if row:
                d = dict(row)
                d["snapshot"] = json.loads(d["snapshot"]) if d["snapshot"] else {}
                return d
            return None

    def checkpoint_list(self, task_id: Optional[int] = None) -> list:
        with self._get_conn() as conn:
            if task_id:
                rows = conn.execute(
                    "SELECT * FROM checkpoints WHERE task_id = ? ORDER BY created_at DESC",
                    (task_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM checkpoints ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def scratch_create(self, title: str, content: str = "", tags: str = "") -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO scratch_notes (title, content, tags) VALUES (?, ?, ?)",
                (title, content, tags),
            )
            return cur.lastrowid

    def scratch_update(self, note_id: int, **kwargs):
        allowed = {"title", "content", "tags"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        set_clause += ", updated_at = datetime('now')"
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE scratch_notes SET {set_clause} WHERE id = ?",
                (*fields.values(), note_id),
            )

    def scratch_get(self, note_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM scratch_notes WHERE id = ?", (note_id,)
            ).fetchone()
            return dict(row) if row else None

    def scratch_list(self, tag: Optional[str] = None) -> list:
        with self._get_conn() as conn:
            if tag:
                rows = conn.execute(
                    "SELECT * FROM scratch_notes WHERE tags LIKE ? ORDER BY updated_at DESC",
                    (f"%{tag}%",),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM scratch_notes ORDER BY updated_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def session_start(self, project_root: str, mode: str = "build") -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO sessions (project_root, mode) VALUES (?, ?)",
                (project_root, mode),
            )
            return cur.lastrowid

    def session_end(self, session_id: int, summary: str = ""):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE sessions SET is_active = 0, ended_at = datetime('now'), summary = ? WHERE id = ?",
                (summary, session_id),
            )

    def session_update_mode(self, session_id: int, mode: str):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE sessions SET mode = ? WHERE id = ?",
                (mode, session_id),
            )

    def session_get(self, session_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def session_get_active(self, project_root: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE project_root = ? AND is_active = 1 ORDER BY started_at DESC LIMIT 1",
                (project_root,),
            ).fetchone()
            return dict(row) if row else None

    def session_list(self, project_root: Optional[str] = None) -> list:
        with self._get_conn() as conn:
            if project_root:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE project_root = ? ORDER BY started_at DESC LIMIT 20",
                    (project_root,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY started_at DESC LIMIT 20"
                ).fetchall()
            return [dict(r) for r in rows]

    def history_append(
        self, session_id: int, role: str, content: str, mode: Optional[str] = None
    ):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO conversation_history (session_id, role, content, mode) VALUES (?, ?, ?, ?)",
                (session_id, role, content, mode),
            )

    def history_get(self, session_id: int, limit: int = 50) -> list:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM conversation_history WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
