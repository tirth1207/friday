import asyncio
import re
import sys

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from core.github_context import clear_active_repository, get_active_repository, set_active_repository
from core.github_diagnostics import list_github_diagnostics, run_github_diagnostic
from core.github_oauth import (
    apply_connection_to_github_tools, authorization_url, clear_connection, connection_status,
    exchange_code, refresh_connection_if_needed, settings as github_oauth_settings,
)
from core.github_repositories import list_selectable_repositories
from core.memory import memory_store
from core.orchestrator_structured import ask_friday
from services.api.websocket import friday_websocket

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI(title="FRIDAY", description="Personal AI Operating Layer", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    repository: str | None = None


class RepositoryContextRequest(BaseModel):
    repository: str | None = None


_FILE_EXTENSION_RE = re.compile(r"\.[A-Za-z0-9]{1,6}$")


def _looks_like_file_path(candidate: str) -> bool:
    return bool(_FILE_EXTENSION_RE.search(candidate.rsplit("/", 1)[-1]))


def _normalize_repository_context(value: str | None) -> str | None:
    """Normalize repository labels that may come from the UI/chat transcript."""
    if not value:
        return None
    normalized = value.strip()
    normalized = re.sub(r"^repository\s*:\s*", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^repository(?=[A-Za-z0-9_.-]+/)", "", normalized, flags=re.IGNORECASE)
    return normalized or None


def _explicit_repository_from_message(message: str) -> str | None:
    """Extract an explicit owner/name while ignoring file paths such as test/page.tsx."""
    text = (message or "").strip()
    normalized = re.sub(r"^repository\s*[:\-]?\s*", "", text, flags=re.IGNORECASE)
    normalized = re.sub(r"^repository(?=[A-Za-z0-9_.-]+/)", "", normalized, flags=re.IGNORECASE)
    for match in re.finditer(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:\.git)?\b", normalized, re.IGNORECASE):
        candidate = match.group(1).removesuffix(".git")
        if not _looks_like_file_path(candidate):
            return candidate
    return None


def _is_explicit_build_request(message: str) -> bool:
    text = (message or "").strip().lower()
    action = re.search(r"\b(build|implement|finish|complete|fix|repair|refactor|write|create|make|add|remove|replace|update|ship|commit|push)\b", text)
    target = re.search(r"\b(code|feature|project|repo|repository|bug|issue|file|component|frontend|backend|api|app|application|function|test|implementation|improvement|change|page)\b", text)
    return bool(action and target)


def _provider_error_message(error: Exception) -> str:
    """Return a provider diagnosis only for errors that actually came from the provider."""
    error_text = str(error).strip()
    lowered = error_text.lower()
    error_type = type(error).__name__
    provider_markers = (
        "nvidia", "chatnvidia", "integrate.api.nvidia.com", "nvidia_api_key",
        "api key", "rate limit", "too many requests", "429", "401", "403",
        "model not found", "provider", "llm", "completion",
        "internal server error", "service unavailable", "bad gateway", "500", "502", "503",
    )
    if not any(marker in lowered for marker in provider_markers):
        return f"FRIDAY's Developer Agent failed ({error_type}): {error_text or 'unknown backend error'}"
    if "nvidia_api_key" in lowered or "api key" in lowered or "invalid api key" in lowered:
        return "FRIDAY is configured, but the NVIDIA API key is missing or invalid. Set NVIDIA_API_KEY in the backend .env and restart FRIDAY."
    if "401" in lowered or "403" in lowered or "unauthorized" in lowered or "forbidden" in lowered:
        return "FRIDAY reached NVIDIA, but authentication was rejected. Check NVIDIA_API_KEY and make sure the key is active."
    if "404" in lowered and ("model" in lowered or "nvidia" in lowered):
        return "FRIDAY reached NVIDIA, but the configured model was not found or is unavailable to this key."
    if "429" in lowered or "rate limit" in lowered or "too many requests" in lowered:
        return "FRIDAY reached NVIDIA, but the provider is rate-limiting this key/model. Retry shortly."
    if "500" in lowered or "502" in lowered or "503" in lowered or "internal server error" in lowered or "service unavailable" in lowered:
        return "FRIDAY reached NVIDIA, but the provider returned a server-side error. This is usually transient — try again in a moment."
    if "timeout" in lowered or "timed out" in lowered:
        return "FRIDAY reached NVIDIA, but the provider request timed out."
    if "connection" in lowered or "connect" in lowered or "dns" in lowered:
        return "FRIDAY could not connect to the NVIDIA endpoint. Check the backend network connection."
    return f"FRIDAY's NVIDIA provider request failed ({error_type}): {error_text or 'unknown provider error'}"


def _developer_response(result: dict, repository: str | None) -> str:
    """Turn execution evidence into a concise, user-facing delivery report."""
    repo = result.get("repository") or repository or "workspace"
    summary = str(result.get("summary") or "Developer task completed.").strip()
    if result.get("delivery_error"):
        summary = "I completed the implementation, but delivery did not finish successfully."

    lines = ["## Developer Agent", "", summary, ""]
    lines.append(f"**Repository:** `{repo}`")

    commit = result.get("commit_evidence")
    push = result.get("push_evidence")
    if result.get("committed") and isinstance(commit, dict):
        sha = str(commit.get("commit_sha") or "")
        lines.append(f"**Commit:** `{sha[:10]}` — {commit.get('message', 'changes committed')}")
    elif result.get("committed"):
        lines.append("**Commit:** completed")

    if result.get("pushed") and isinstance(push, dict):
        branch = push.get("branch") or "current branch"
        sha = str(push.get("remote_sha") or push.get("commit_sha") or "")
        lines.append(f"**Push:** `{branch}` updated successfully · `{sha[:10]}`")
    elif result.get("delivery_error"):
        error = str(result.get("delivery_error"))
        lines.append(f"**Push:** failed — {error}")

    if result.get("verified"):
        lines.append("**Verification:** passed")
    else:
        lines.append("**Verification:** not confirmed")

    lines.append("")
    lines.append("_FRIDAY inspected the repository context first and used the existing project structure for the change._")
    return "\n".join(lines)


@app.on_event("startup")
async def startup() -> None:
    if await refresh_connection_if_needed():
        print("[FRIDAY GitHub] Restored GitHub App user connection")


@app.get("/")
async def root():
    return {"name": "FRIDAY", "status": "online", "version": "0.3.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "github": connection_status(), "active_repository": get_active_repository()}


@app.get("/conversations")
async def conversations(limit: int = 80):
    safe_limit = max(1, min(limit, 80))
    return {"conversations": memory_store.get_conversations(safe_limit)}


@app.get("/memory/experiences")
async def experiences(query: str = "", limit: int = 20):
    safe_limit = max(1, min(limit, 100))
    return {"experiences": memory_store.search_experiences(query, safe_limit)}


@app.get("/auth/github")
async def github_auth_start():
    try:
        return RedirectResponse(authorization_url())
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/auth/github/callback")
async def github_auth_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(f"{github_oauth_settings.frontend_url.rstrip('/')}/github?error={error}")
    if not code:
        raise HTTPException(status_code=400, detail="GitHub authorization code is missing.")
    try:
        connection = await exchange_code(code, state)
        apply_connection_to_github_tools()
        login = str(connection.get("login") or "GitHub")
        return RedirectResponse(f"{github_oauth_settings.frontend_url.rstrip('/')}/github?connected=1&login={login}")
    except Exception as error:
        print(f"[FRIDAY GitHub OAuth] Callback failed: {error}")
        return RedirectResponse(f"{github_oauth_settings.frontend_url.rstrip('/')}/github?error=oauth_failed")


@app.get("/auth/github/status")
async def github_auth_status():
    return connection_status()


@app.post("/auth/github/disconnect")
async def github_auth_disconnect():
    clear_connection(); clear_active_repository()
    from tools.github.repository_agent import settings as github_settings
    github_settings.pat = ""; github_settings.username = ""
    return {"connected": False, "active_repository": None}


@app.get("/auth/github/repositories")
async def github_repositories():
    try:
        await refresh_connection_if_needed()
        repositories = await list_selectable_repositories(limit=100)
        return {"repositories": repositories, "active_repository": get_active_repository()}
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/auth/github/repository-context")
async def github_repository_context():
    return {"repository": get_active_repository()}


@app.post("/auth/github/repository-context")
async def github_repository_context_set(request: RepositoryContextRequest):
    repository = _normalize_repository_context(request.repository)
    if repository is None:
        clear_active_repository(); return {"repository": None}
    try:
        await refresh_connection_if_needed()
        from tools.github.repository_agent import _resolve_repository
        canonical = await _resolve_repository(repository)
        set_active_repository(canonical)
        return {"repository": canonical}
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/auth/github/diagnostics")
async def github_diagnostics():
    try:
        await refresh_connection_if_needed(); return {"tests": await list_github_diagnostics()}
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/auth/github/diagnostics/{test_id}")
async def github_diagnostic(test_id: str, repository: str | None = None):
    try:
        await refresh_connection_if_needed(); return await run_github_diagnostic(test_id, repository)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        await refresh_connection_if_needed()
        explicit_repository = _explicit_repository_from_message(request.message)
        repository = explicit_repository or _normalize_repository_context(request.repository) or _normalize_repository_context(get_active_repository())
        if repository:
            from tools.github.repository_agent import _resolve_repository
            repository = await _resolve_repository(repository)
            set_active_repository(repository)

        if _is_explicit_build_request(request.message):
            from core.agents.developer_loop import DeveloperLoop
            result = await DeveloperLoop(max_iterations=6, allow_mutations=True).run(request.message, repository)
            response = _developer_response(result, repository)
            memory_store.add_message("user", request.message)
            memory_store.add_message("assistant", response)
            return {"response": response, "repository": repository, "developer_run": result}

        response = await ask_friday(request.message, repository=repository)
        return {"response": response, "repository": repository}
    except Exception as error:
        print(f"[FRIDAY] Chat error: {type(error).__name__}: {error}")
        return {"response": _provider_error_message(error), "error": str(error).strip(), "error_type": type(error).__name__, "status": "ai_unavailable"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await friday_websocket(websocket)
