from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.config import settings
from core.proactive.models import (
    AttentionDecision,
    AttentionLevel,
    ProactiveMessage,
    ProactiveSignal,
)


class AttentionManager:
    """Small, deterministic attention gate.

    FRIDAY can observe freely, but interruptions require a meaningful score.
    The model can later provide richer scores; this gate remains the final
    noise-control layer.
    """

    def __init__(self, db_path: str | None = None):
        root = Path(settings.friday_workspace).expanduser().resolve() / "data"
        root.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or str(root / "proactive.db")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS delivered_signals (
                    dedupe_key TEXT PRIMARY KEY,
                    delivered_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS proactive_messages (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    level TEXT NOT NULL,
                    signal_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0
                )"""
            )
            conn.commit()

    @staticmethod
    def _score(signal: ProactiveSignal) -> float:
        return min(
            1.0,
            0.35 * signal.importance
            + 0.25 * signal.urgency
            + 0.25 * signal.relevance
            + 0.15 * signal.confidence,
        )

    def evaluate(self, signal: ProactiveSignal) -> AttentionDecision:
        score = self._score(signal)
        if signal.dedupe_key:
            with sqlite3.connect(self.db_path) as conn:
                seen = conn.execute(
                    "SELECT 1 FROM delivered_signals WHERE dedupe_key = ? LIMIT 1",
                    (signal.dedupe_key,),
                ).fetchone()
            if seen:
                return AttentionDecision(
                    signal_id=signal.id,
                    level=AttentionLevel.QUIET,
                    score=score,
                    reason="Duplicate signal already delivered.",
                )

        if score >= 0.82 or signal.urgency >= 0.9:
            level = AttentionLevel.URGENT
        elif score >= 0.62:
            level = AttentionLevel.NOTIFY
        elif score >= 0.40:
            level = AttentionLevel.DIGEST
        else:
            level = AttentionLevel.QUIET

        deliver = level in {AttentionLevel.URGENT, AttentionLevel.NOTIFY}
        queue = level == AttentionLevel.DIGEST

        return AttentionDecision(
            signal_id=signal.id,
            level=level,
            score=score,
            reason=f"attention score={score:.2f}",
            should_deliver=deliver,
            should_queue=queue,
        )

    def record(self, signal: ProactiveSignal, decision: AttentionDecision) -> ProactiveMessage | None:
        if not decision.should_deliver and not decision.should_queue:
            return None

        message = ProactiveMessage(
            title=signal.title,
            message=signal.summary,
            level=decision.level,
            signal_id=signal.id,
            source=signal.source,
            delivered=False,
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO proactive_messages
                (id, title, message, level, signal_id, source, created_at, delivered)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (
                    message.id,
                    message.title,
                    message.message,
                    message.level.value,
                    message.signal_id,
                    message.source,
                    message.created_at.isoformat(),
                ),
            )
            if signal.dedupe_key:
                conn.execute(
                    "INSERT OR REPLACE INTO delivered_signals(dedupe_key, delivered_at) VALUES (?, ?)",
                    (signal.dedupe_key, datetime.now(timezone.utc).isoformat()),
                )
            conn.commit()
        return message

    def recent(self, limit: int = 30) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id,title,message,level,signal_id,source,created_at,delivered
                   FROM proactive_messages ORDER BY created_at DESC LIMIT ?""",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [
            {
                "id": row[0],
                "title": row[1],
                "message": row[2],
                "level": row[3],
                "signal_id": row[4],
                "source": row[5],
                "created_at": row[6],
                "delivered": bool(row[7]),
            }
            for row in rows
        ]

    @staticmethod
    def make_dedupe_key(source: str, kind: str, title: str, summary: str) -> str:
        raw = f"{source}|{kind}|{title}|{summary}".strip().lower()
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
