"""FRIDAY core package bootstrap."""

# GitHub App user tokens can have repository metadata and Contents access while
# individual Git data endpoints may vary by token/permission configuration.
# Patch both the analyzer entry point and its tree primitive so every existing
# caller uses the Contents-based repository traversal consistently.
from tools.github import repository_agent as _github_repository_agent
from core.github_repository_contents import analyze_repository as _analyze_repository
from core.github_repository_contents import contents_tree as _contents_tree

_github_repository_agent._tree = _contents_tree
_github_repository_agent.github_analyze_repository = _analyze_repository
