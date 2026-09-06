import re

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


def _explicit_repository_from_message(message: str) -> str | None:
    text = message or ""
    match = re.search(r"(?:\brepository\b\s*[:\-]?\s*)?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:\.git)?\b", text, re.IGNORECASE)
    return match.group(1).removesuffix(".git") if match else None


def _is_explicit_build_request(message: str) -> bool:
    """Detect direct engineering commands without hijacking normal coding questions."""
    text = (message or "").strip().lower()
    action = re.search(r"\b(build|implement|finish|complete|fix|repair|refactor|write|create|add|remove|replace|update|ship)\b", text)
    target = re.search(r"\b(code|feature|project|repo|repository|bug|issue|file|component|frontend|backend|api|app|application|function|test|implementation)\b", text)
    return bool(action and target)


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
    return {"conversations": memory_store.get_conversations(limit)}


@app.get("/memory/experiences")
async def experiences(query: str = "", limit: int = 20):
    return {"experiences": memory_store.search_experiences(query, limit)}


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
    repository = request.repository
    if repository is None or not repository.strip():
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
        repository = explicit_repository or (request.repository.strip() if request.repository else None) or get_active_repository()
        if repository:
            from tools.github.repository_agent import _resolve_repository
            repository = await _resolve_repository(repository)
            set_active_repository(repository)

        if _is_explicit_build_request(request.message):
            from core.agents.developer_loop import DeveloperLoop
            result = await DeveloperLoop(max_iterations=4, allow_mutations=True).run(request.message, repository)
            response = (
                "## Developer Agent\n\n"
                f"{result.get('summary', 'Engineering loop completed.')}\n\n"
                f"- Iterations: `{result.get('iterations', 0)}`\n"
                f"- Verified: `{result.get('verified', False)}`\n"
                f"- Changes enabled: `{result.get('mutations_enabled', True)}`"
            )
            memory_store.add_message("user", request.message)
            memory_store.add_message("assistant", response)
            return {"response": response, "repository": repository, "developer_run": result}

        response = await ask_friday(request.message, repository=repository)
        return {"response": response, "repository": repository}
    except Exception as error:
        print(f"[FRIDAY] Chat error: {error}")
        return {"response": "I couldn't complete that request because the AI service is currently unavailable. Please try again.", "error": str(error)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await friday_websocket(websocket)
