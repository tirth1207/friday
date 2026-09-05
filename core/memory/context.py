import re
from typing import Any

from core.memory.memory import memory_store


CONTEXT_KEY = "active_conversation_context"


def _clean(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _is_greeting(text: str) -> bool:
    return bool(re.fullmatch(r"(?:hi|hello|hey|yo|good morning|good afternoon|good evening)[!. ]*", _clean(text)))


def _is_short_followup(text: str) -> bool:
    clean = _clean(text)
    words = clean.split()
    if len(words) <= 6:
        return True
    return any(
        re.search(pattern, clean)
        for pattern in (
            r"^(yes|yeah|yep|no|nope|okay|ok|sure|continue|go ahead|do it)$",
            r"^(github|gitlab|git)$",
            r"^(top \d+|only \w+|just \w+)$",
            r"^(this|that|those|these|it|them|same|again)$",
        )
    )


def resolve_request(message: str) -> dict[str, Any]:
    """Resolve the current message against persistent conversation/task context.

    This is intentionally deterministic. It provides a reliable fallback even
    when the model provider is unavailable and keeps the planner from losing
    the active task on short follow-ups such as 'github' or 'top 5'.
    """
    recent = memory_store.get_recent_messages(limit=12)
    previous_user_messages = [m["content"] for m in recent if m["role"] == "user"]
    previous_user = previous_user_messages[-2] if len(previous_user_messages) >= 2 else (
        previous_user_messages[-1] if previous_user_messages else ""
    )
    context = memory_store.get_preference(CONTEXT_KEY, {}) or {}
    active_task = str(context.get("active_task", ""))
    active_platform = str(context.get("platform", ""))
    clean = _clean(message)

    resolved = message.strip()
    platform = active_platform

    if not _is_greeting(message) and _is_short_followup(message):
        if clean in {"github", "gitlab", "git"}:
            platform = clean
            base = active_task or previous_user
            if base:
                resolved = f"Continue the previous task: {base}. Use {platform} as the platform/context."
        elif active_task:
            resolved = f"Continue the previous task: {active_task}. The user's follow-up is: {message.strip()}"
        elif previous_user:
            resolved = f"Continue the previous request: {previous_user}. The user's follow-up is: {message.strip()}"

    # A substantive new request becomes the new active task. Short follow-ups
    # inherit the existing task instead of replacing it.
    if not _is_short_followup(message) and not _is_greeting(message):
        active_task = message.strip()
    elif not active_task and previous_user and not _is_greeting(previous_user):
        active_task = previous_user

    if platform:
        memory_store.set_preference(CONTEXT_KEY, {"active_task": active_task, "platform": platform})
    elif active_task:
        memory_store.set_preference(CONTEXT_KEY, {"active_task": active_task})

    return {
        "message": message.strip(),
        "resolved_request": resolved,
        "recent_messages": recent,
        "active_task": active_task,
        "platform": platform,
    }
