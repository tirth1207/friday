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


def _is_repo_ranking(text: str) -> bool:
    clean = _clean(text)
    return (
        re.search(r"\b(?:repo|repos|repository|repositories)\b", clean) is not None
        and re.search(r"\b(?:rank|ranking|top|best)\b", clean) is not None
    )


def resolve_request(message: str) -> dict[str, Any]:
    """Resolve the current message against persistent conversation/task context."""
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

    # Make critical GitHub data requirements explicit to the planner. This is
    # intentionally deterministic: fetching repository data must not depend on
    # whether the NVIDIA planner happens to emit a tool call.
    if _is_repo_ranking(resolved):
        resolved = (
            f"{resolved}\n\nMANDATORY EXECUTION REQUIREMENT: before ranking, fetch the user's "
            "GitHub repositories with the registered tool github.repositories. "
            "Do not answer from memory and do not claim the repository list is empty "
            "unless that tool actually returns an empty list or a real API error occurs."
        )
        platform = "github"

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
