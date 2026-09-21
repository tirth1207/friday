from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from core.proactive.attention import AttentionManager
from core.proactive.interests import Interest, interest_store
from core.proactive.models import ProactiveSignal
from tools.osiris.osiris_tools import osiris_news


def _flatten_items(value: Any) -> list[dict[str, Any]]:
    """Find article/post-like dictionaries in an arbitrary OSIRIS JSON response."""
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if any(k in value for k in ("title", "headline", "name")) and any(
            k in value for k in ("url", "link", "description", "summary", "published_at", "timestamp", "date")
        ):
            found.append(value)
        for child in value.values():
            found.extend(_flatten_items(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_flatten_items(child))
    return found


def _text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _matches(item: dict[str, Any], interest: Interest) -> bool:
    haystack = " ".join(
        _text(item, "title", "headline", "name"),
        _text(item, "description", "summary", "text"),
    ).lower()
    return any(keyword.lower() in haystack for keyword in interest.keywords)


async def poll_interest(interest: Interest, attention: AttentionManager) -> list[ProactiveSignal]:
    result = await osiris_news(query=" ".join(interest.keywords))
    items = _flatten_items(result.get("data"))
    signals: list[ProactiveSignal] = []

    for item in items[:30]:
        if not _matches(item, interest):
            continue
        title = _text(item, "title", "headline", "name") or interest.topic
        summary = _text(item, "description", "summary", "text") or title
        url = _text(item, "url", "link")
        published = _text(item, "published_at", "published", "timestamp", "date")
        fingerprint = hashlib.sha256(
            f"{interest.topic}|{title}|{url}|{published}".encode("utf-8")
        ).hexdigest()

        signals.append(
            ProactiveSignal(
                source="OSIRIS",
                kind="interest_news",
                title=f"{interest.topic}: {title}",
                summary=f"{summary}{f' ({published})' if published else ''}{f' — {url}' if url else ''}",
                importance=0.78,
                urgency=0.30,
                relevance=0.92,
                confidence=0.78,
                dedupe_key=f"osiris-news:{fingerprint}",
                payload={"interest": interest.topic, "url": url, "published": published, "item": item},
            )
        )
    return signals


async def poll_due_interests(attention: AttentionManager) -> list[ProactiveSignal]:
    signals: list[ProactiveSignal] = []
    for interest in interest_store.due():
        try:
            signals.extend(await poll_interest(interest, attention))
        finally:
            interest_store.mark_checked(interest.topic)
    return signals
