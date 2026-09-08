import json
import sqlite3
from typing import Any, Optional

from core.runtime.permissions import get_workspace_root


class MemoryStore:
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            db_dir = get_workspace_root() / ".friday"
            db_dir.mkdir(exist_ok=True)
            self.db_path = str(db_dir / "friday_memory.db")
        else:
            self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                fact TEXT NOT NULL,
                source_message TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )""")
            cursor.execute("""CREATE INDEX IF NOT EXISTS idx_user_profile_category ON user_profile(category)""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT, tool TEXT, status TEXT,
                details TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, title TEXT NOT NULL,
                lesson TEXT NOT NULL, context TEXT DEFAULT '', timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
            conn.commit()

    def add_message(self, role: str, content: str):
        with self._get_connection() as conn:
            conn.execute("INSERT INTO conversation_history (role, content) VALUES (?, ?)", (role, content))
            conn.commit()

    def get_recent_messages(self, limit: int = 20) -> list[dict[str, str]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT role, content FROM conversation_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

    def get_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, role, content, timestamp FROM conversation_history ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [{"id": row[0], "role": row[1], "content": row[2], "timestamp": row[3]} for row in rows]

    def set_preference(self, key: str, value: Any):
        serialized = value if isinstance(value, str) else json.dumps(value)
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO user_preferences (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, serialized),
            )
            conn.commit()

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM user_preferences WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return row[0]

    def remember_profile(self, category: str, fact: str, source_message: str = "") -> dict[str, Any]:
        category = category.strip().lower()
        fact = fact.strip()
        if not category or not fact:
            raise ValueError("Both category and fact are required.")
        with self._get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM user_profile WHERE category = ? AND lower(fact) = lower(?) ORDER BY id DESC LIMIT 1",
                (category, fact),
            ).fetchone()
            if existing:
                return {"id": existing[0], "category": category, "fact": fact, "source_message": source_message, "existing": True}
            cursor = conn.execute(
                "INSERT INTO user_profile (category, fact, source_message) VALUES (?, ?, ?)",
                (category, fact, source_message[:2000]),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "category": category, "fact": fact, "source_message": source_message, "existing": False}

    def recall_profile(self, query: str = "", limit: int = 8) -> list[dict[str, Any]]:
        query = (query or "").strip().lower()
        limit = max(1, min(limit, 20))
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, category, fact, source_message, created_at FROM user_profile ORDER BY id DESC LIMIT 500"
            ).fetchall()
        items = [
            {"id": row[0], "category": row[1], "fact": row[2], "source_message": row[3], "created_at": row[4]}
            for row in rows
        ]
        if not query:
            return items[:limit]
        tokens = {token for token in query.split() if len(token) > 2}
        scored: list[tuple[int, dict[str, Any]]] = []
        for item in items:
            haystack = " ".join(str(item[key]).lower() for key in ("category", "fact"))
            score = sum(1 for token in tokens if token in haystack)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], -int(pair[1]["id"])))
        return [item for _, item in scored[:limit]]

    def profile_digest(self, query: str = "", limit: int = 8) -> str:
        items = self.recall_profile(query=query, limit=limit)
        if not items:
            return "No saved user preferences or behavior facts are available."
        return "\n".join(f"- [{item['category']}] {item['fact']}" for item in items)

    def add_experience(self, experience: dict[str, Any]):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO experiences (kind, title, lesson, context, timestamp) VALUES (?, ?, ?, ?, ?)",
                (
                    str(experience.get("kind", "lesson")),
                    str(experience.get("title", "Untitled")),
                    str(experience.get("lesson", "")),
                    str(experience.get("context", "")),
                    str(experience.get("timestamp", "")),
                ),
            )
            conn.commit()

    def search_experiences(self, query: str = "", limit: int = 8) -> list[dict[str, Any]]:
        query = (query or "").strip().lower()
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, kind, title, lesson, context, timestamp FROM experiences ORDER BY id DESC LIMIT 200"
            ).fetchall()
        items = [
            {"id": row[0], "kind": row[1], "title": row[2], "lesson": row[3], "context": row[4], "timestamp": row[5]}
            for row in rows
        ]
        if not query:
            return items[:limit]
        tokens = {token for token in query.split() if len(token) > 2}
        scored = []
        for item in items:
            haystack = " ".join(str(item[key]).lower() for key in ("kind", "title", "lesson", "context"))
            score = sum(1 for token in tokens if token in haystack)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], -int(pair[1]["id"])))
        return [item for _, item in scored[:limit]]

    def log_execution(self, agent: str, tool: str, status: str, details: Optional[dict[str, Any]] = None):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO execution_logs (agent, tool, status, details) VALUES (?, ?, ?, ?)",
                (agent, tool, status, json.dumps(details or {})),
            )
            conn.commit()


memory_store = MemoryStore()
