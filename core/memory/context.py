import re
from typing import Any

from core.memory.memory import memory_store


CONTEXT_KEY = "active_conversation_context"


def _clean(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _is_greeting(text: str) -> bool:
    return bool(re.fullmatch(r"(?:hi|hello|hey|yo|good morning|good afternoon|good evening)[!. ]*", _clean(text)))


def _looks_like_followup(text: str) -> bool:
    """Identify messages that normally modify/continue an existing task."""
    clean = _clean(text)
    return bool(
        re.fullmatch(
            r"(?:github|gitlab|git|yes|yeah|yep|no|nope|okay|ok|sure|continue|go ahead|"
            r"top \d+|only \w+(?: \w+)?|just \w+(?: \w+)?|this|that|those|these|it|them|"
            r"same|again|do it|compare|why|how about that)[!. ]*",
            clean,
        )
    )


def resolve_request(message: str) -> dict[str, Any]:
    """Resolve the current message against persistent conversation/task context.

    The resolver is deterministic so short follow-ups continue to work even if
    the model provider is unavailable. Substantive requests become the new
    active task; context-only replies inherit the existing task.
    """
    recent = memory_store.get_recent_messages(limit=12)
    previous_user_messages = [m["content"] for m in recent if m["role"] == "user"]
    previous_user = previous_user_messages[-1] if previous_user_messages else ""
    context = memory_store.get_preference(CONTEXT_KEY, {}) or {}
    active_task = str(context.get("active_task", ""))
    active_platform = str(context.get("platform", ""))
    clean = _clean(message)

    is_greeting = _is_greeting(message)
    is_followup = _looks_like_followup(message) and bool(active_task or previous_user)
    resolved = message.strip()
    platform = active_platform

    if not is_greeting and is_followup:
        if clean in {"github", "gitlab", "git"}:
            platform = clean
            base = active_task or previous_user
            resolved = f"Continue the previous task: {base}. Use {platform} as the platform/context."
        elif active_task:
            resolved = f"Continue the previous task: {active_task}. The user's follow-up is: {message.strip()}"
        elif previous_user:
            resolved = f"Continue the previous request: {previous_user}. The user's follow-up is: {message.strip()}"

    # Any substantive request becomes the active task. Greetings and pure
    # follow-ups do not replace the task that is currently in progress.
    if not is_greeting and not is_followup:
        active_task = message.strip()

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
