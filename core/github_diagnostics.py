"""Direct GitHub API diagnostics for the FRIDAY integration UI.

These checks intentionally bypass the LLM/agent layer. They use the same authenticated
GitHub App user token as the GitHub Agent and report the real GitHub HTTP status.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from core.github_oauth import load_connection
from tools.github.repository_agent import GITHUB_API, GITHUB_API_VERSION


class GitHubDiagnosticError(RuntimeError):
    pass


TESTS: dict[str, dict[str, Any]] = {
    "identity": {"label": "Account identity", "permission": "OAuth identity", "method": "GET", "path": "/user", "needs_repo": False},
    "repositories": {"label": "List repositories", "permission": "Metadata", "method": "GET", "path": "/user/repos?per_page=1&visibility=all&affiliation=owner,collaborator,organization_member", "needs_repo": False},
    "metadata": {"label": "Repository metadata", "permission": "Metadata", "method": "GET", "path": "/repos/{repo}", "needs_repo": True},
    "contents": {"label": "Repository contents", "permission": "Contents", "method": "GET", "path": "/repos/{repo}/contents?ref={branch}", "needs_repo": True},
    "pull_requests": {"label": "Pull requests", "permission": "Pull requests", "method": "GET", "path": "/repos/{repo}/pulls?state=all&per_page=1", "needs_repo": True},
    "issues": {"label": "Issues", "permission": "Issues", "method": "GET", "path": "/repos/{repo}/issues?state=all&per_page=1", "needs_repo": True},
    "checks": {"label": "Check runs", "permission": "Checks", "method": "GET", "path": "/repos/{repo}/commits/{branch}/check-runs?per_page=1", "needs_repo": True},
    "statuses": {"label": "Commit statuses", "permission": "Commit statuses", "method": "GET", "path": "/repos/{repo}/commits/{branch}/status", "needs_repo": True},
    "actions": {"label": "Actions workflow runs", "permission": "Actions", "method": "GET", "path": "/repos/{repo}/actions/runs?per_page=1", "needs_repo": True},
    "code_scanning": {"label": "Code scanning alerts", "permission": "Code scanning alerts", "method": "GET", "path": "/repos/{repo}/code-scanning/alerts?per_page=1", "needs_repo": True},
    "dependabot": {"label": "Dependabot alerts", "permission": "Dependabot alerts", "method": "GET", "path": "/repos/{repo}/dependabot/alerts?per_page=1", "needs_repo": True},
    "secret_scanning": {"label": "Secret scanning alerts", "permission": "Secret scanning alerts", "method": "GET", "path": "/repos/{repo}/secret-scanning/alerts?per_page=1", "needs_repo": True},
    "security_advisories": {"label": "Repository security advisories", "permission": "Repository security advisories", "method": "GET", "path": "/repos/{repo}/security-advisories?per_page=1", "needs_repo": True},
    "deployments": {"label": "Deployments", "permission": "Deployments", "method": "GET", "path": "/repos/{repo}/deployments?per_page=1", "needs_repo": True},
    "packages": {"label": "Packages", "permission": "Packages", "method": "GET", "path": "/user/packages?package_type=npm&per_page=1", "needs_repo": False},
    "pages": {"label": "GitHub Pages", "permission": "Pages", "method": "GET", "path": "/repos/{repo}/pages", "needs_repo": True},
}


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "FRIDAY-GitHub-Diagnostics",
    }


async def _request(token: str, path: str) -> tuple[int, str, Any, str | None]:
    timeout = httpx.Timeout(20.0, connect=7.0, read=20.0, write=20.0, pool=10.0)
    async with httpx.AsyncClient(base_url=GITHUB_API, headers=_headers(token), timeout=timeout) as client:
        try:
            response = await client.get(path)
        except httpx.RequestError as error:
            raise GitHubDiagnosticError(f"Network error: {error}") from error
        try:
            payload = response.json()
        except Exception:
            payload = response.text[:500]
        return response.status_code, response.reason_phrase or "", payload, response.headers.get("X-Accepted-GitHub-Permissions")


def _message(payload: Any, status: int) -> str:
    if isinstance(payload, dict):
        return str(payload.get("message") or payload.get("error_description") or f"HTTP {status}")
    if isinstance(payload, str) and payload.strip():
        return payload.strip()[:500]
    return f"HTTP {status}"


async def run_github_diagnostic(test_id: str, repository: str | None = None) -> dict[str, Any]:
    """Run exactly one direct GET against GitHub and return diagnostic metadata."""
    spec = TESTS.get(test_id)
    if not spec:
        raise GitHubDiagnosticError(f"Unknown GitHub diagnostic: {test_id}")

    connection = load_connection()
    token = str((connection or {}).get("access_token") or "").strip()
    if not token:
        raise GitHubDiagnosticError("GitHub is not connected. Connect GitHub before running diagnostics.")

    repo = (repository or "").strip().strip("/").removesuffix(".git")
    if spec["needs_repo"] and not repo:
        raise GitHubDiagnosticError("A repository is required for this diagnostic.")

    branch = "main"
    if spec["needs_repo"]:
        metadata_status, _, metadata, metadata_permissions = await _request(token, f"/repos/{repo}")
        if metadata_status >= 400:
            return {
                "id": test_id,
                "label": spec["label"],
                "permission": spec["permission"],
                "method": spec["method"],
                "path": f"/repos/{repo}",
                "status": metadata_status,
                "ok": False,
                "message": _message(metadata, metadata_status),
                "accepted_permissions": metadata_permissions,
                "note": "Repository metadata lookup failed, so this diagnostic could not reach its target endpoint.",
            }
        branch = str((metadata or {}).get("default_branch") or "main")

    path = str(spec["path"]).format(
        repo=quote(repo, safe="/"),
        branch=quote(branch, safe=""),
    )
    status, reason, payload, accepted_permissions = await _request(token, path)
    return {
        "id": test_id,
        "label": spec["label"],
        "permission": spec["permission"],
        "method": spec["method"],
        "path": path,
        "status": status,
        "ok": 200 <= status < 300,
        "message": _message(payload, status),
        "reason": reason,
        "accepted_permissions": accepted_permissions,
        "note": "Direct GitHub API call; no LLM, supervisor, or GitHub Agent was used.",
    }


async def list_github_diagnostics() -> list[dict[str, Any]]:
    return [
        {
            "id": test_id,
            "label": spec["label"],
            "permission": spec["permission"],
            "method": spec["method"],
            "needs_repo": spec["needs_repo"],
        }
        for test_id, spec in TESTS.items()
    ]
