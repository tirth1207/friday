"""Deterministic Tier-0 reflex layer for FRIDAY."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from core.github_oauth import connection_status
from core.github_context import get_active_repository
from core.memory import memory_store
from core.runtime.executor import tool_executor
from providers.nvidia.health import snapshot as nvidia_health_snapshot

_INDIA_TZ = ZoneInfo("Asia/Kolkata")


def _now() -> datetime:
    return datetime.now(_INDIA_TZ)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _format_list(items: list[Any]) -> str:
    if not items:
        return "Nothing found."
    lines: list[str] = []
    for item in items[:10]:
        if isinstance(item, dict):
            name = item.get("name") or item.get("path") or item.get("title")
            lines.append(f"- {name}" if name else f"- {item}")
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)


def _time_response(now: datetime) -> str:
    return f"It's {now.strftime('%I:%M %p')} on {now.strftime('%A, %d %B %Y')} (IST)."


def _date_response(now: datetime) -> str:
    return f"Today is {now.strftime('%A, %d %B %Y')}."


async def handle(message: str) -> str | None:
    """Answer only high-confidence deterministic requests; None means use the supervisor."""
    text = _clean(message)
    if not text:
        return None

    if re.fullmatch(r"(what(?:'s| is) the )?time(?: is it)?(?: right now| now)?[?!.]*", text):
        return _time_response(_now())

    if re.fullmatch(r"(what(?:'s| is) )?(today'?s )?date(?: is it)?(?: today)?[?!.]*", text):
        return _date_response(_now())

    if text in {"what can you do", "what can you do?", "capabilities", "help", "help?"}:
        return (
            "I can handle instant requests without using the AI provider: "
            "time/date, provider health, GitHub connection/repository status, "
            "saved memory recall, and local system information."
        )

    if text in {
        "provider status", "provider health", "ai provider status",
        "is nvidia up", "is nvidia working", "is the ai provider working",
    }:
        health = nvidia_health_snapshot()
        if health["status"] == "ready":
            return "NVIDIA provider status: ready. No consecutive provider failures are currently recorded."
        return (
            f"NVIDIA provider status: {health['status']}. "
            f"Consecutive failures: {health['consecutive_failures']}. "
            f"Last error: {health['last_error'] or 'unknown'}"
        )

    if text in {"github status", "is github connected", "github connection", "what github account is connected"}:
        status = connection_status()
        if not status.get("connected"):
            return "GitHub is not connected."
        login = status.get("login") or status.get("username") or "connected account"
        repo = get_active_repository()
        suffix = f" Active repository: {repo}." if repo else ""
        return f"GitHub is connected as {login}.{suffix}"

    if text in {"active repository", "what repository am i in", "what repo am i in", "current repository"}:
        repo = get_active_repository()
        return f"Active repository: {repo}." if repo else "There is no active repository selected."

    memory_match = re.fullmatch(
        r"(?:what do you remember about me|what do you remember|show my memories|my memories)(?:\s+about\s+(.+))?[?!.]*",
        text,
    )
    if memory_match:
        query = (memory_match.group(1) or "").strip()
        memories = memory_store.search_experiences(query, 8)
        if not memories:
            return "I don't have any matching saved memories."
        lines = ["Here are the saved memories I found:"]
        for item in memories:
            title = item.get("title") or item.get("kind") or "Memory"
            lesson = item.get("lesson") or item.get("context") or ""
            lines.append(f"- {title}: {lesson}".strip())
        return "\n".join(lines)

    if text in {"system info", "system information", "computer info", "pc info", "laptop info"}:
        result = await tool_executor.execute("os.system_info", {}, agent="Tier-0 Reflex")
        if isinstance(result, dict):
            parts = [
                f"{key.replace('_', ' ').title()}: {result[key]}"
                for key in ("platform", "os", "cpu", "memory", "python_version")
                if result.get(key)
            ]
            return "System information:\n" + ("\n".join(f"- {item}" for item in parts) or str(result))
        return f"System information: {result}"

    if text in {"disk usage", "disk space", "storage", "how much storage do i have"}:
        result = await tool_executor.execute("os.disk_usage", {}, agent="Tier-0 Reflex")
        if isinstance(result, dict):
            return "Disk usage:\n" + "\n".join(
                f"- {key.replace('_', ' ').title()}: {value}" for key, value in result.items()
            )
        return f"Disk usage: {result}"

    if text in {"running processes", "what is running", "show running processes"}:
        result = await tool_executor.execute("os.list_processes", {}, agent="Tier-0 Reflex")
        return "Running processes:\n" + _format_list(result)

    return None
