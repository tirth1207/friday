from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from core.config import settings


@dataclass(frozen=True)
class Interest:
    topic: str
    keywords: tuple[str, ...]
    enabled: bool = True
    interval_seconds: int = 900


class InterestStore:
    """Persistent local watch list for proactive intelligence."""

    def __init__(self, db_path: str | None = None):
        root = Path(settings.friday_workspace).expanduser().resolve() / "data"
        root.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or str(root / "proactive.db")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS proactive_interests (
                    topic TEXT PRIMARY KEY,
                    keywords TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    interval_seconds INTEGER NOT NULL DEFAULT 900,
                    last_checked_at TEXT
                )"""
            )
            conn.commit()

    def add(self, topic: str, keywords: Iterable[str] | None = None, interval_seconds: int = 900) -> Interest:
        topic = topic.strip()
        if not topic:
            raise ValueError("Interest topic cannot be empty.")
        words = [x.strip() for x in (keywords or [topic]) if x and x.strip()]
        interval = max(300, int(interval_seconds))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO proactive_interests(topic, keywords, enabled, interval_seconds)
                   VALUES (?, ?, 1, ?)
                   ON CONFLICT(topic) DO UPDATE SET keywords=excluded.keywords,
                   enabled=1, interval_seconds=excluded.interval_seconds""",
                (topic, "|".join(dict.fromkeys(words)), interval),
            )
            conn.commit()
        return Interest(topic, tuple(dict.fromkeys(words)), True, interval)

    def remove(self, topic: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM proactive_interests WHERE topic = ?", (topic.strip(),))
            conn.commit()

    def list(self) -> list[Interest]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT topic, keywords, enabled, interval_seconds FROM proactive_interests ORDER BY topic"
            ).fetchall()
        return [Interest(r[0], tuple(filter(None, r[1].split("|"))), bool(r[2]), int(r[3])) for r in rows]

    def due(self, now: datetime | None = None) -> list[Interest]:
        now = now or datetime.now(timezone.utc)
        due: list[Interest] = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT topic, keywords, enabled, interval_seconds, last_checked_at
                   FROM proactive_interests WHERE enabled = 1"""
            ).fetchall()
        for topic, raw_keywords, enabled, interval, last_checked in rows:
            if not enabled:
                continue
            if not last_checked:
                due.append(Interest(topic, tuple(filter(None, raw_keywords.split("|"))), True, int(interval)))
                continue
            try:
                previous = datetime.fromisoformat(last_checked)
                if (now - previous).total_seconds() >= int(interval):
                    due.append(Interest(topic, tuple(filter(None, raw_keywords.split("|"))), True, int(interval)))
            except ValueError:
                due.append(Interest(topic, tuple(filter(None, raw_keywords.split("|"))), True, int(interval)))
        return due

    def mark_checked(self, topic: str, when: datetime | None = None) -> None:
        stamp = (when or datetime.now(timezone.utc)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE proactive_interests SET last_checked_at = ? WHERE topic = ?",
                (stamp, topic.strip()),
            )
            conn.commit()


interest_store = InterestStore()
