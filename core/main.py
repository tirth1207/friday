from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from core.github_context import clear_active_repository, get_active_repository, set_active_repository
from core.github_diagnostics import list_github_diagnostics, run_github_diagnostic
from core.github_oauth import (
    apply_connection_to_github_tools,
    authorization_url,
    clear_connection,
    connection_status,
    exchange_code,
    refresh_connection_if_needed,
    settings as github_oauth_settings,
)
from core.github_repositories import list_selectable_repositories
from core.orchestrator_structured import ask_friday
from services.api.websocket import friday_websocket


app = FastAPI(title="FRIDAY", description="Personal AI Operating Layer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    repository: str | None = None


@app.on_event("startup")
async def startup() -> None:
    if await refresh_connection_if_needed():
        print("[FRIDAY GitHub] Restored GitHub App user connection")


@app.get("/")
async def root():
    return {"name": "FRIDAY", "status": "online", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "github": connection_status(), "active_repository": get_active_repository()}


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
    clear_connection()
    clear_active_repository()
    from tools.github.repository_agent import settings as github_settings
    github_settings.pat = ""
    github_settings.username = ""
    return {"connected": False, "active_repository": None}


@app.get("/auth/github/repositories")
async def github_repositories():
    """List repositories available to the connected GitHub account for explicit selection."""
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
async def github_repository_context_set(repository: str | None = None):
    if repository is None or not repository.strip():
        clear_active_repository()
        return {"repository": None}
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
    """List direct GitHub API diagnostics. This endpoint does not invoke the AI."""
    try:
        await refresh_connection_if_needed()
        return {"tests": await list_github_diagnostics()}
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/auth/github/diagnostics/{test_id}")
async def github_diagnostic(test_id: str, repository: str | None = None):
    """Run one direct GitHub GET request, bypassing FRIDAY's AI/agent layer."""
    try:
        await refresh_connection_if_needed()
        return await run_github_diagnostic(test_id, repository)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        await refresh_connection_if_needed()
        repository = request.repository.strip() if request.repository else get_active_repository()
        if repository:
            from tools.github.repository_agent import _resolve_repository
            repository = await _resolve_repository(repository)
            set_active_repository(repository)
        response = await ask_friday(request.message, repository=repository)
        return {"response": response, "repository": repository}
    except Exception as error:
        print(f"[FRIDAY] Chat error: {error}")
        return {"response": "I couldn't complete that request because the AI service is currently unavailable. Please try again.", "error": str(error)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await friday_websocket(websocket)
