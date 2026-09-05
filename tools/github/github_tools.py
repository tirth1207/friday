"""Authenticated GitHub tools for FRIDAY."""

from __future__ import annotations

import base64
import os
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from langchain.tools import tool

GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = os.getenv("GITHUB_API_VERSION", "2022-11-28")
MAX_PAGE_SIZE = 100
MAX_FILE_CHARS = 150_000


def _credentials() -> tuple[str, str]:
    username = os.getenv("GITHUB_USERNAME", "").strip()
    token = os.getenv("GITHUB_PAT", "").strip()
    if not username:
        raise RuntimeError("GITHUB_USERNAME is not configured.")
    if not token:
        raise RuntimeError("GITHUB_PAT is not configured.")
    return username, token


def _repo_name(value: str) -> str:
    raw = value.strip()
    if raw.startswith(("https://github.com/", "http://github.com/")):
        parsed = urlparse(raw)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub repository URL: {value}")
        owner, repo = parts[0], parts[1]
    else:
        raw = raw.removesuffix(".git").strip("/")
        parts = [part for part in raw.split("/") if part]
        if len(parts) == 1:
            owner, repo = _credentials()[0], parts[0]
        elif len(parts) == 2:
            owner, repo = parts
        else:
            raise ValueError(f"Invalid repository: {value}")
    return f"{owner}/{repo.removesuffix('.git')}"


def _repo_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": item.get("name"),
        "full_name": item.get("full_name"),
        "private": item.get("private"),
        "fork": item.get("fork"),
        "archived": item.get("archived"),
        "description": item.get("description"),
        "language": item.get("language"),
        "default_branch": item.get("default_branch"),
        "stars": item.get("stargazers_count", 0),
        "forks": item.get("forks_count", 0),
        "open_issues": item.get("open_issues_count", 0),
        "size_kb": item.get("size", 0),
        "updated_at": item.get("updated_at"),
        "pushed_at": item.get("pushed_at"),
        "html_url": item.get("html_url"),
    }


def _truncate(text: str, limit: int = MAX_FILE_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n\n[OUTPUT TRUNCATED - MAX {limit} CHARACTERS]"


async def _request(path: str, params: dict[str, Any] | None = None) -> Any:
    _, token = _credentials()
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "FRIDAY-Personal-AI",
    }
    timeout = httpx.Timeout(20.0, connect=7.0, read=20.0, write=20.0, pool=10.0)
    async with httpx.AsyncClient(base_url=GITHUB_API, headers=headers, timeout=timeout) as client:
        try:
            response = await client.get(path, params=params)
        except httpx.RequestError as error:
            raise RuntimeError(f"GitHub network request failed: {error}") from error
        if response.status_code >= 400:
            try:
                detail = response.json().get("message", "GitHub request failed")
            except Exception:
                detail = response.text[:300]
            raise RuntimeError(f"GitHub API {response.status_code}: {detail}")
        return response.json()


async def github_get_profile(username: str | None = None) -> dict[str, Any]:
    """Fetch a GitHub profile; omit username to use the authenticated account."""
    configured_username, _ = _credentials()
    target = (username or configured_username).strip()
    data = await _request("/user" if target.lower() == configured_username.lower() else f"/users/{target}")
    return {
        "login": data.get("login"), "name": data.get("name"), "bio": data.get("bio"),
        "company": data.get("company"), "location": data.get("location"),
        "public_repos": data.get("public_repos", 0), "private_repos": data.get("total_private_repos"),
        "owned_private_repos": data.get("owned_private_repos"), "followers": data.get("followers", 0),
        "following": data.get("following", 0), "html_url": data.get("html_url"),
    }


async def github_list_repositories(username: str | None = None, limit: int = 100, sort: str = "pushed", page: int = 1) -> list[dict[str, Any]]:
    """List repositories accessible to the authenticated account, including permitted private repositories."""
    configured_username, _ = _credentials()
    target = (username or configured_username).strip()
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    page = max(1, page)
    path = "/user/repos" if target.lower() == configured_username.lower() else f"/users/{target}/repos"
    data = await _request(path, {"type": "all", "sort": sort, "direction": "desc", "per_page": limit, "page": page})
    return [_repo_summary(item) for item in data]


async def github_get_repository(repository: str) -> dict[str, Any]:
    """Fetch detailed metadata for owner/name, a repository name, or a GitHub repository URL."""
    data = await _request(f"/repos/{_repo_name(repository)}")
    summary = _repo_summary(data)
    summary.update({
        "homepage": data.get("homepage"), "created_at": data.get("created_at"),
        "license": (data.get("license") or {}).get("spdx_id"), "topics": data.get("topics", []),
        "owner": (data.get("owner") or {}).get("login"), "permissions": data.get("permissions", {}),
    })
    return summary


async def github_list_commits(repository: str, limit: int = 20, page: int = 1) -> list[dict[str, Any]]:
    """Fetch recent commits from a repository."""
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    page = max(1, page)
    data = await _request(f"/repos/{_repo_name(repository)}/commits", {"per_page": limit, "page": page})
    return [{
        "sha": item.get("sha"),
        "message": (item.get("commit") or {}).get("message", "").split("\n", 1)[0],
        "author": (item.get("author") or {}).get("login") or (item.get("commit") or {}).get("author", {}).get("name"),
        "date": (item.get("commit") or {}).get("author", {}).get("date"),
        "html_url": item.get("html_url"),
    } for item in data]


async def github_get_contents(repository: str, path: str = "", ref: str | None = None) -> Any:
    """Fetch a repository file or directory listing at an optional branch, tag, or commit."""
    repo = _repo_name(repository)
    clean_path = path.strip().lstrip("/")
    endpoint = f"/repos/{repo}/contents/{quote(clean_path, safe='/')}" if clean_path else f"/repos/{repo}/contents"
    data = await _request(endpoint, {"ref": ref} if ref else None)
    if isinstance(data, list):
        return [{
            "name": item.get("name"), "path": item.get("path"), "type": item.get("type"),
            "size": item.get("size"), "sha": item.get("sha"), "download_url": item.get("download_url"),
            "html_url": item.get("html_url"),
        } for item in data]

    content = data.get("content") or ""
    if data.get("encoding") == "base64":
        try:
            content = base64.b64decode(content).decode("utf-8")
        except UnicodeDecodeError:
            return {
                "type": data.get("type"), "name": data.get("name"), "path": data.get("path"),
                "sha": data.get("sha"), "size": data.get("size"), "binary": True,
                "message": "File is not UTF-8 text and was not decoded.", "html_url": data.get("html_url"),
                "download_url": data.get("download_url"),
            }
    return {
        "type": data.get("type"), "name": data.get("name"), "path": data.get("path"),
        "sha": data.get("sha"), "size": data.get("size"), "encoding": "utf-8",
        "content": _truncate(content), "html_url": data.get("html_url"), "download_url": data.get("download_url"),
    }


async def github_read_file(repository: str, path: str, ref: str | None = None) -> dict[str, Any]:
    """Read one text file from an accessible repository."""
    result = await github_get_contents(repository, path, ref)
    if not isinstance(result, dict) or result.get("type") != "file":
        raise ValueError(f"Path is not a file: {path}")
    return result


async def github_list_directory(repository: str, path: str = "", ref: str | None = None) -> list[dict[str, Any]]:
    """List files and directories beneath a repository path."""
    result = await github_get_contents(repository, path, ref)
    if not isinstance(result, list):
        raise ValueError(f"Path is not a directory: {path or '/'}")
    return result


async def github_get_file_metadata(repository: str, path: str, ref: str | None = None) -> dict[str, Any]:
    """Return repository file metadata without returning the file body."""
    result = await github_get_contents(repository, path, ref)
    if not isinstance(result, dict):
        raise ValueError(f"Path is not a file: {path}")
    result = dict(result)
    result.pop("content", None)
    result["content_available"] = result.get("type") == "file"
    return result


async def github_get_tree(repository: str, ref: str | None = None, recursive: bool = True) -> list[dict[str, Any]]:
    """Return the Git tree for a repository ref."""
    repo = _repo_name(repository)
    target_ref = ref or (await _request(f"/repos/{repo}")).get("default_branch") or "main"
    try:
        commit_data = await _request(f"/repos/{repo}/commits/{quote(target_ref, safe='')}")
    except RuntimeError:
        ref_data = await _request(f"/repos/{repo}/git/ref/heads/{quote(target_ref, safe='')}")
        commit_sha = ((ref_data.get("object") or {}).get("sha"))
        if not commit_sha:
            raise RuntimeError(f"Could not resolve repository ref: {target_ref}")
        commit_data = await _request(f"/repos/{repo}/git/commits/{commit_sha}")
    tree_sha = ((commit_data.get("commit") or {}).get("tree") or {}).get("sha") or ((commit_data.get("tree") or {}).get("sha"))
    if not tree_sha:
        raise RuntimeError(f"Could not resolve repository tree for: {target_ref}")
    data = await _request(f"/repos/{repo}/git/trees/{tree_sha}", {"recursive": "1"} if recursive else None)
    return [{
        "path": item.get("path"), "mode": item.get("mode"), "type": item.get("type"),
        "sha": item.get("sha"), "size": item.get("size"), "url": item.get("url"),
    } for item in data.get("tree", [])]


async def github_search_code(query: str, repository: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Search GitHub code, optionally scoped to one repository."""
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    search_query = query.strip()
    if not search_query:
        raise ValueError("Search query cannot be empty.")
    if repository:
        search_query = f"{search_query} repo:{_repo_name(repository)}"
    data = await _request("/search/code", {"q": search_query, "per_page": limit})
    return [{
        "name": item.get("name"), "path": item.get("path"), "sha": item.get("sha"),
        "repository": (item.get("repository") or {}).get("full_name"), "html_url": item.get("html_url"),
    } for item in data.get("items", [])]


async def github_list_branches(repository: str, limit: int = 100, page: int = 1) -> list[dict[str, Any]]:
    """List repository branches."""
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    page = max(1, page)
    data = await _request(f"/repos/{_repo_name(repository)}/branches", {"per_page": limit, "page": page})
    return [{"name": item.get("name"), "protected": item.get("protected"), "sha": (item.get("commit") or {}).get("sha")} for item in data]


async def github_get_commit(repository: str, sha: str = "") -> dict[str, Any]:
    """Fetch one commit with metadata, stats, and changed-file patches."""
    repo = _repo_name(repository)
    target = sha.strip() or (await _request(f"/repos/{repo}")).get("default_branch") or "HEAD"
    data = await _request(f"/repos/{repo}/commits/{quote(target, safe='')}")
    return {
        "sha": data.get("sha"), "message": (data.get("commit") or {}).get("message", ""),
        "author": (data.get("author") or {}).get("login") or (data.get("commit") or {}).get("author", {}).get("name"),
        "date": (data.get("commit") or {}).get("author", {}).get("date"), "html_url": data.get("html_url"),
        "stats": data.get("stats", {}),
        "files": [{
            "filename": file.get("filename"), "status": file.get("status"), "additions": file.get("additions"),
            "deletions": file.get("deletions"), "changes": file.get("changes"),
            "patch": _truncate(file.get("patch") or "", 30_000), "raw_url": file.get("raw_url"), "blob_url": file.get("blob_url"),
        } for file in (data.get("files") or [])],
    }


# LangChain v1 expects the tool name as the positional first argument.
github_get_profile_tool = tool("github_get_profile")(github_get_profile)
github_list_repositories_tool = tool("github_list_repositories")(github_list_repositories)
github_get_repository_tool = tool("github_get_repository")(github_get_repository)
github_list_commits_tool = tool("github_list_commits")(github_list_commits)
github_get_contents_tool = tool("github_get_contents")(github_get_contents)
github_read_file_tool = tool("github_read_file")(github_read_file)
github_list_directory_tool = tool("github_list_directory")(github_list_directory)
github_get_file_metadata_tool = tool("github_get_file_metadata")(github_get_file_metadata)
github_get_tree_tool = tool("github_get_tree")(github_get_tree)
github_search_code_tool = tool("github_search_code")(github_search_code)
github_list_branches_tool = tool("github_list_branches")(github_list_branches)
github_get_commit_tool = tool("github_get_commit")(github_get_commit)

GITHUB_LANGCHAIN_TOOLS = [
    github_get_profile_tool,
    github_list_repositories_tool,
    github_get_repository_tool,
    github_list_commits_tool,
    github_get_contents_tool,
    github_read_file_tool,
    github_list_directory_tool,
    github_get_file_metadata_tool,
    github_get_tree_tool,
    github_search_code_tool,
    github_list_branches_tool,
    github_get_commit_tool,
]
