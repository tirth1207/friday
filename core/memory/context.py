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


def _is_repo_file_read_request(text: str) -> bool:
    clean = _clean(text)
    has_repo_context = re.search(r"\b(?:repo|repository|project|github)\b", clean) is not None
    has_read_intent = re.search(r"\b(?:read|fetch|show|open|get|retrieve|contents?|content)\b", clean) is not None
    has_file_target = re.search(r"\b(?:file|files|path|\.env(?:\.example)?|package\.json|readme(?:\.md)?)\b", clean) is not None
    return has_repo_context and has_read_intent and has_file_target


def _is_repo_structure_request(text: str) -> bool:
    """Identify requests for the tree/structure of one specific repository."""
    clean = _clean(text)
    has_repo_context = re.search(r"\b(?:repo|repository|project|github)\b", clean) is not None
    has_structure_intent = re.search(
        r"\b(?:structure|project structure|directory tree|tree|folder structure|file structure|contents)\b",
        clean,
    ) is not None
    has_list_like_intent = re.search(r"\b(?:list|show|get|fetch|display|see|view)\b", clean) is not None
    has_specific_repo = (
        re.search(r"\b(?:repo|repository)\s+(?:named|called)\s+[A-Za-z0-9_.-]+\b", clean) is not None
        or re.search(r"\b(?:my|the)\s+[A-Za-z0-9_.-]+\s+(?:repo|repository|project)\b", clean) is not None
        or re.search(r"\b[a-z0-9_.-]+/[a-z0-9_.-]+\b", clean) is not None
    )
    return has_repo_context and has_structure_intent and has_list_like_intent and has_specific_repo


def _is_env_key_request(text: str) -> bool:
    clean = _clean(text)
    has_env = re.search(r"\b(?:env|environment|environmental)\b", clean) is not None
    has_key_intent = re.search(r"\b(?:key|keys|variable|variables|config|configuration|needed|required|requirements?)\b", clean) is not None
    return has_env and has_key_intent


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

    # Keep GitHub repository context alive for natural follow-ups such as
    # "what env keys are needed in this project" even when the current message
    # does not repeat the repository name.
    if platform == "github" and (_is_env_key_request(resolved) or _is_repo_file_read_request(resolved)):
        base_context = active_task or previous_user
        resolved = (
            f"{resolved}\n\nThe current task is about the GitHub repository from the recent conversation. "
            f"Previous repository context: {base_context}\n"
        )
        if _is_env_key_request(resolved):
            resolved += (
                "MANDATORY EXECUTION REQUIREMENT: read .env.example with the registered "
                "tool github.file.read before answering. Extract only environment variable "
                "NAMES. Never expose or invent secret values. Do not answer from memory."
            )
        else:
            resolved += (
                "MANDATORY EXECUTION REQUIREMENT: if the user asks for file contents, use "
                "the registered tool github.file.read for the requested repository/path. "
                "Do not substitute a directory listing or file metadata when content was requested."
            )
        platform = "github"

    # Repository structure is a repository-specific GitHub operation, not an
    # account-level repository listing. Make that distinction deterministic so
    # the orchestrator cannot route "my friday repo structure" to github.repositories.
    if _is_repo_structure_request(resolved):
        resolved = (
            f"{resolved}\n\nMANDATORY EXECUTION REQUIREMENT: this is a specific-repository "
            "project-structure request. Resolve the named repository and use the registered "
            "tool github.tree with recursive=true to retrieve its directory/file tree. "
            "DO NOT call github.repositories and DO NOT list the user's other repositories. "
            "Return the structure of the requested repository only."
        )
        platform = "github"

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
