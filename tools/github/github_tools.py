"""GitHub data tools for FRIDAY.

Authentication is intentionally read only from environment variables:
- GITHUB_USERNAME
- GITHUB_PAT

Never pass a PAT through chat. GitHub recommends treating access tokens like
passwords and sending them in the Authorization header.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from langchain.tools import tool

GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"


def _credentials() -> tuple[str, str]:
    username = os.getenv("GITHUB_USERNAME", "").strip()
    token = os.getenv("GITHUB_PAT", "").strip()
    if not username:
        raise RuntimeError("GITHUB_USERNAME is not configured.")
    if not token:
        raise RuntimeError("GITHUB_PAT is not configured.")
    return username, token


async def _request(path: str, params: dict[str, Any] | None = None) -> Any:
    _, token = _credentials()
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "FRIDAY-Personal-AI",
    }
    timeout = httpx.Timeout(15.0, connect=5.0)

    async with httpx.AsyncClient(base_url=GITHUB_API, headers=headers, timeout=timeout) as client:
        response = await client.get(path, params=params)
        if response.status_code >= 400:
            try:
                detail = response.json().get("message", "GitHub request failed")
            except Exception:
                detail = response.text[:300]
            raise RuntimeError(f"GitHub API {response.status_code}: {detail}")
        return response.json()


def _repo_name(value: str) -> str:
    repo = value.strip().removeprefix("https://github.com/").removesuffix(".git").strip("/")
    if "/" not in repo:
        username, _ = _credentials()
        repo = f"{username}/{repo}"
    return repo


def _repo_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": item.get("name"),
        "full_name": item.get("full_name"),
        "private": item.get("private"),
        "description": item.get("description"),
        "language": item.get("language"),
        "default_branch": item.get("default_branch"),
        "stars": item.get("stargazers_count", 0),
        "forks": item.get("forks_count", 0),
        "open_issues": item.get("open_issues_count", 0),
        "updated_at": item.get("updated_at"),
        "pushed_at": item.get("pushed_at"),
        "html_url": item.get("html_url"),
    }


async def github_get_profile(username: str | None = None) -> dict[str, Any]:
    """Fetch GitHub profile data; use the authenticated profile when no username is supplied."""
    configured_username, _ = _credentials()
    target = (username or configured_username).strip()
    data = await _request("/user" if target.lower() == configured_username.lower() else f"/users/{target}")
    return {
        "login": data.get("login"),
        "name": data.get("name"),
        "bio": data.get("bio"),
        "company": data.get("company"),
        "location": data.get("location"),
        "public_repos": data.get("public_repos", 0),
        "private_repos": data.get("total_private_repos"),
        "owned_private_repos": data.get("owned_private_repos"),
        "followers": data.get("followers", 0),
        "following": data.get("following", 0),
        "html_url": data.get("html_url"),
    }


async def github_list_repositories(
    username: str | None = None,
    limit: int = 20,
    sort: str = "pushed",
) -> list[dict[str, Any]]:
    """List repositories for the configured user, including private repositories when the PAT permits access."""
    configured_username, _ = _credentials()
    target = (username or configured_username).strip()
    limit = max(1, min(limit, 100))

    # /user/repos is the authenticated endpoint and can include private repos.
    # /users/{username}/repos is used when explicitly asking for another user.
    path = "/user/repos" if target.lower() == configured_username.lower() else f"/users/{target}/repos"
    params = {"type": "all", "sort": sort, "direction": "desc", "per_page": limit}
    data = await _request(path, params)
    return [_repo_summary(item) for item in data[:limit]]


async def github_get_repository(repository: str) -> dict[str, Any]:
    """Fetch detailed metadata for one GitHub repository such as owner/name or a repository name."""
    data = await _request(f"/repos/{_repo_name(repository)}")
    summary = _repo_summary(data)
    summary.update(
        {
            "homepage": data.get("homepage"),
            "size_kb": data.get("size", 0),
            "created_at": data.get("created_at"),
            "license": (data.get("license") or {}).get("spdx_id"),
            "topics": data.get("topics", []),
        }
    )
    return summary


async def github_list_commits(repository: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch recent commits for a repository."""
    limit = max(1, min(limit, 100))
    data = await _request(
        f"/repos/{_repo_name(repository)}/commits",
        {"per_page": limit},
    )
    return [
        {
            "sha": item.get("sha"),
            "message": (item.get("commit") or {}).get("message", "").split("\n", 1)[0],
            "author": (item.get("author") or {}).get("login")
            or (item.get("commit") or {}).get("author", {}).get("name"),
            "date": (item.get("commit") or {}).get("author", {}).get("date"),
            "html_url": item.get("html_url"),
        }
        for item in data[:limit]
    ]


# LangChain tool objects provide schemas for specialized agents, while the raw
# async functions remain compatible with FRIDAY's existing tool registry.
github_get_profile_tool = tool("github_get_profile")(github_get_profile)
github_list_repositories_tool = tool("github_list_repositories")(github_list_repositories)
github_get_repository_tool = tool("github_get_repository")(github_get_repository)
github_list_commits_tool = tool("github_list_commits")(github_list_commits)

GITHUB_LANGCHAIN_TOOLS = [
    github_get_profile_tool,
    github_list_repositories_tool,
    github_get_repository_tool,
    github_list_commits_tool,
]
