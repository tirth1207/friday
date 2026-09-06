"""FRIDAY core package bootstrap."""

# GitHub App user tokens can have Contents access while the low-level Git Trees
# endpoint is unavailable to the integration. Patch the repository-analysis
# entry point at package initialization so all existing callers transparently
# use the Contents-based analyzer.
from tools.github import repository_agent as _github_repository_agent
from core.github_repository_contents import analyze_repository as _analyze_repository

_github_repository_agent.github_analyze_repository = _analyze_repository
