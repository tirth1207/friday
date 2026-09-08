import re
from typing import Any

from core.memory.memory import memory_store


CONTEXT_KEY = "active_conversation_context"


def _clean(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _is_greeting(text: str) -> bool:
    return bool(re.fullmatch(r"(?:hi|hello|hey|yo|good morning|good afternoon|good evening)[!. ]*", _clean(text)))


def _looks_like_followup(text: str) -> bool:
    clean = _clean(text)
    return bool(re.fullmatch(r"(?:github|gitlab|git|yes|yeah|yep|no|nope|okay|ok|sure|continue|go ahead|top \d+|only \w+(?: \w+)?|just \w+(?: \w+)?|this|that|those|these|it|them|same|again|do it|compare|why|how about that)[!. ]*", clean))


def _is_repo_ranking(text: str) -> bool:
    clean = _clean(text)
    return re.search(r"\b(?:repo|repos|repository|repositories)\b", clean) is not None and re.search(r"\b(?:rank|ranking|top|best)\b", clean) is not None


def _is_repo_file_read_request(text: str) -> bool:
    clean = _clean(text)
    return re.search(r"\b(?:repo|repository|project|github)\b", clean) is not None and re.search(r"\b(?:read|fetch|show|open|get|retrieve|contents?|content)\b", clean) is not None and re.search(r"\b(?:file|files|path|\.env(?:\.example)?|package\.json|readme(?:\.md)?)\b", clean) is not None


def _is_repo_structure_request(text: str) -> bool:
    clean = _clean(text)
    has_repo_context = re.search(r"\b(?:repo|repository|project|github)\b", clean) is not None
    has_structure_intent = re.search(r"\b(?:structure|project structure|directory tree|tree|folder structure|file structure|contents)\b", clean) is not None
    has_list_like_intent = re.search(r"\b(?:list|show|get|fetch|display|see|view)\b", clean) is not None
    has_specific_repo = re.search(r"\b(?:repo|repository)\s+(?:named|called)\s+[A-Za-z0-9_.-]+\b", clean) is not None or re.search(r"\b(?:my|the)\s+[A-Za-z0-9_.-]+\s+(?:repo|repository|project)\b", clean) is not None or re.search(r"\b[a-z0-9_.-]+/[a-z0-9_.-]+\b", clean) is not None
    return has_repo_context and has_structure_intent and has_list_like_intent and has_specific_repo


def _is_repo_explanation_request(text: str, active_platform: str = "") -> bool:
    clean = _clean(text)
    return re.search(r"\b(?:explain|explanation|describe|analyze|analyse|understand|overview)\b", clean) is not None and re.search(r"\b(?:project|repo|repository|codebase)\b", clean) is not None and (active_platform == "github" or re.search(r"\bgithub\b", clean) is not None)


def _is_friday_project_explain_request(text: str) -> bool:
    clean = _clean(text)
    return re.search(r"\bfriday\b", clean) is not None and re.search(r"\b(?:project|repo|repository|codebase)\b", clean) is not None and re.search(r"\b(?:explain|explanation|describe|analyze|analyse|understand|overview)\b", clean) is not None


def _is_env_key_request(text: str) -> bool:
    clean = _clean(text)
    return re.search(r"\b(?:env|environment|environmental)\b", clean) is not None and re.search(r"\b(?:key|keys|variable|variables|config|configuration|needed|required|requirements?)\b", clean) is not None


def _is_research_request(text: str) -> bool:
    clean = _clean(text)
    explicit_research = re.search(r"\b(?:research|investigate|investigation|look\s+up|look\s+online|search\s+(?:the\s+)?web|web\s+search|find\s+online|sources?|papers?|documentation)\b", clean) is not None
    open_question = re.search(r"\b(?:what|why|how|which|who|where|when|latest|current)\b", clean) is not None
    external_subject = re.search(r"\b(?:news|company|product|technology|library|framework|api|paper|study|market|person|website|internet|online)\b", clean) is not None
    return explicit_research or (open_question and external_subject)


def _is_browser_request(text: str) -> bool:
    clean = _clean(text)
    return re.search(r"\b(?:browse|browser|website|webpage|navigate|click|type\s+into|open\s+(?:the\s+)?website)\b", clean) is not None and re.search(r"\bhttps?://|\b(?:site|page|website|webpage)\b", clean) is not None


def _is_music_request(text: str) -> bool:
    clean = _clean(text)
    return re.search(r"\b(?:music|song|songs|spotify|play|pause|next track|current song|current track)\b", clean) is not None and re.search(r"\b(?:spotify|song|music|track|play|pause|next)\b", clean) is not None


def resolve_request(message: str) -> dict[str, Any]:
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

    if _is_friday_project_explain_request(resolved):
        resolved = f"{resolved}\n\nResolved repository target: tirth1207/friday. MANDATORY EXECUTION REQUIREMENT: explain the actual GitHub repository tirth1207/friday using registered GitHub tools. Fetch github.repository, github.tree with repository=tirth1207/friday and recursive=true, and README when available before generating the explanation. Do not return planner JSON to the user. Execute the selected tools and answer from their results."
        platform = "github"
    elif _is_repo_explanation_request(resolved, platform):
        resolved = f"{resolved}\n\nMANDATORY EXECUTION REQUIREMENT: this is a GitHub repository/project explanation request. Identify the requested repository from the user's message and conversation context. Use registered GitHub tools, starting with github.repository when the repository can be identified, then github.tree with repository=<owner>/<repo> and recursive=true. Read important source/config files discovered in the tree before explaining the architecture. Do not return tool-call JSON to the user and do not substitute local filesystem data for remote GitHub data."
        platform = "github"

    if platform == "github" and (_is_env_key_request(resolved) or _is_repo_file_read_request(resolved)):
        base_context = active_task or previous_user
        resolved = f"{resolved}\n\nThe current task is about the GitHub repository from the recent conversation. Previous repository context: {base_context}\n"
        if _is_env_key_request(resolved):
            resolved += "MANDATORY EXECUTION REQUIREMENT: read .env.example with the registered tool github.file.read before answering. Extract only environment variable NAMES. Never expose or invent secret values. Do not answer from memory."
        else:
            resolved += "MANDATORY EXECUTION REQUIREMENT: if the user asks for file contents, use the registered tool github.file.read for the requested repository/path. Do not substitute a directory listing or file metadata when content was requested."
        platform = "github"

    if _is_repo_structure_request(resolved):
        resolved = f"{resolved}\n\nMANDATORY EXECUTION REQUIREMENT: this is a specific-repository project-structure request. Resolve the named repository and use the registered tool github.tree with the argument repository=<owner>/<repo> and recursive=true to retrieve its directory/file tree. The tool argument MUST be named 'repository'. DO NOT call github.repositories and DO NOT list the user's other repositories. Return the structure of the requested repository only."
        platform = "github"

    if _is_repo_ranking(resolved):
        resolved = f"{resolved}\n\nMANDATORY EXECUTION REQUIREMENT: before ranking, fetch the user's GitHub repositories with the registered tool github.repositories. Do not answer from memory and do not claim the repository list is empty unless that tool actually returns an empty list or a real API error occurs."
        platform = "github"

    if _is_research_request(resolved):
        resolved = f"{resolved}\n\nCURRENT RESEARCH TASK. MANDATORY EXECUTION REQUIREMENT: use Research Agent tools. Prefer research.web.search for discovery, research.web.fetch for primary-source pages, and OSIRIS tools for structured/current intelligence when relevant. Base factual claims on retrieved evidence and include source URLs where available."
        platform = "research"
    elif _is_browser_request(resolved):
        resolved = f"{resolved}\n\nCURRENT BROWSER TASK. MANDATORY EXECUTION REQUIREMENT: use browser.navigate/read_page for safe browsing. browser.click and browser.type require explicit confirmation. For planner execution, use agent_name \"Research Agent\" so the registered browser tool runs through the research-capable specialist path."
        platform = "browser"
    elif _is_music_request(resolved):
        resolved = f"{resolved}\n\nCURRENT MUSIC TASK. MANDATORY EXECUTION REQUIREMENT: use music.* tools for Spotify playback. Playback mutations require explicit confirmation; music.current is read-only. For planner execution, use agent_name \"Research Agent\" so the registered music tool runs through the specialist execution path."
        platform = "music"

    if not is_greeting and not is_followup:
        active_task = message.strip()

    if platform:
        memory_store.set_preference(CONTEXT_KEY, {"active_task": active_task, "platform": platform})
    elif active_task:
        memory_store.set_preference(CONTEXT_KEY, {"active_task": active_task})

    return {"message": message.strip(), "resolved_request": resolved, "recent_messages": recent, "active_task": active_task, "platform": platform}
