"""GitHub App user authorization for FRIDAY."""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubOAuthSettings(BaseSettings):
    app_client_id: str = ""
    app_client_secret: str = ""
    redirect_uri: str = "http://127.0.0.1:8000/auth/github/callback"
    encryption_key: str = ""
    frontend_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="GITHUB_", extra="ignore")


settings = GitHubOAuthSettings()
STATE_TTL_SECONDS = 600
CONNECTION_PATH = Path(__file__).resolve().parents[1] / ".friday" / "github_connection.enc"
_pending_states: dict[str, float] = {}


def _fernet() -> Fernet:
    key = settings.encryption_key.strip()
    if not key:
        raise RuntimeError("GITHUB_ENCRYPTION_KEY is missing. Generate a Fernet key and add it to .env.")
    try:
        return Fernet(key.encode())
    except Exception as error:
        raise RuntimeError("GITHUB_ENCRYPTION_KEY is invalid. It must be a Fernet key.") from error


def is_configured() -> bool:
    return bool(settings.app_client_id.strip() and settings.app_client_secret.strip() and settings.encryption_key.strip())


def authorization_url() -> str:
    if not is_configured():
        raise RuntimeError("GitHub App OAuth is not configured. Set GITHUB_APP_CLIENT_ID, GITHUB_APP_CLIENT_SECRET, and GITHUB_ENCRYPTION_KEY.")
    state = secrets.token_urlsafe(32)
    _pending_states[state] = time.time() + STATE_TTL_SECONDS
    now = time.time()
    for key, expires_at in list(_pending_states.items()):
        if expires_at <= now:
            _pending_states.pop(key, None)
    query = urlencode({"client_id": settings.app_client_id.strip(), "redirect_uri": settings.redirect_uri.strip(), "state": state})
    return f"https://github.com/login/oauth/authorize?{query}"


async def exchange_code(code: str, state: str | None) -> dict[str, Any]:
    if not is_configured():
        raise RuntimeError("GitHub App OAuth is not configured.")
    if not state or state not in _pending_states or _pending_states.pop(state) < time.time():
        raise RuntimeError("Invalid or expired GitHub OAuth state.")

    timeout = httpx.Timeout(20.0, connect=7.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            json={"client_id": settings.app_client_id.strip(), "client_secret": settings.app_client_secret.strip(), "code": code, "redirect_uri": settings.redirect_uri.strip()},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        token_data = response.json()
        if token_data.get("error"):
            raise RuntimeError(token_data.get("error_description") or token_data["error"])

        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            raise RuntimeError("GitHub did not return a user access token.")

        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {access_token}", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "FRIDAY-Personal-AI"},
        )
        user_response.raise_for_status()
        user = user_response.json()

    connection = {
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "expires_at": time.time() + int(token_data.get("expires_in", 28800)),
        "refresh_token_expires_at": time.time() + int(token_data.get("refresh_token_expires_in", 15897600)) if token_data.get("refresh_token_expires_in") else None,
        "login": user.get("login"),
        "github_user_id": user.get("id"),
        "avatar_url": user.get("avatar_url"),
    }
    _save_connection(connection)
    return connection


async def refresh_connection_if_needed() -> bool:
    connection = load_connection()
    if not connection:
        return False
    expires_at = float(connection.get("expires_at") or 0)
    if expires_at > time.time() + 300:
        return apply_connection_to_github_tools()
    refresh_token = str(connection.get("refresh_token") or "").strip()
    if not refresh_token:
        return apply_connection_to_github_tools()
    try:
        timeout = httpx.Timeout(20.0, connect=7.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": settings.app_client_id.strip(),
                    "client_secret": settings.app_client_secret.strip(),
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            token_data = response.json()
        if token_data.get("error"):
            return apply_connection_to_github_tools()
        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            return apply_connection_to_github_tools()
        connection["access_token"] = access_token
        connection["expires_at"] = time.time() + int(token_data.get("expires_in", 28800))
        if token_data.get("refresh_token"):
            connection["refresh_token"] = token_data["refresh_token"]
        if token_data.get("refresh_token_expires_in"):
            connection["refresh_token_expires_at"] = time.time() + int(token_data["refresh_token_expires_in"])
        _save_connection(connection)
        return apply_connection_to_github_tools()
    except Exception:
        return apply_connection_to_github_tools()


def _save_connection(connection: dict[str, Any]) -> None:
    CONNECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    encrypted = _fernet().encrypt(json.dumps(connection).encode("utf-8"))
    CONNECTION_PATH.write_bytes(encrypted)
    try:
        CONNECTION_PATH.chmod(0o600)
    except OSError:
        pass


def load_connection() -> dict[str, Any] | None:
    if not CONNECTION_PATH.exists():
        return None
    try:
        data = json.loads(_fernet().decrypt(CONNECTION_PATH.read_bytes()).decode("utf-8"))
        return data if isinstance(data, dict) else None
    except (InvalidToken, ValueError, OSError, RuntimeError):
        return None


def clear_connection() -> None:
    try:
        CONNECTION_PATH.unlink()
    except FileNotFoundError:
        pass


def connection_status() -> dict[str, Any]:
    connection = load_connection()
    if not connection:
        return {"configured": is_configured(), "connected": False}
    return {"configured": is_configured(), "connected": True, "login": connection.get("login"), "github_user_id": connection.get("github_user_id"), "expires_at": connection.get("expires_at")}


def apply_connection_to_github_tools() -> bool:
    connection = load_connection()
    if not connection:
        return False
    from tools.github.repository_agent import settings as github_settings
    token = str(connection.get("access_token") or "").strip()
    login = str(connection.get("login") or "").strip()
    if not token:
        return False
    github_settings.pat = token
    if login:
        github_settings.username = login
    return True
