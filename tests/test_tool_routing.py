from core.memory.context import _is_repo_structure_request, resolve_request
from core.orchestrator import _is_github_repository_list_request, is_tool_required


def test_general_question_stays_conversational():
    assert is_tool_required("who is Narendra Modi?") is False


def test_github_repository_request_uses_tools():
    assert is_tool_required("fetch my GitHub repositories") is True


def test_github_commit_request_uses_tools():
    assert is_tool_required("show my GitHub commits") is True


def test_os_inspection_uses_tools():
    assert is_tool_required("show my system information") is True


def test_normal_conversation_does_not_use_os_tools():
    assert is_tool_required("how are you?") is False


def test_specific_repository_structure_is_not_repository_listing():
    request = "list the project structure of my friday repo in github"
    assert _is_repo_structure_request(request) is True
    assert _is_github_repository_list_request(request) is False
    assert is_tool_required(request) is True


def test_resolved_repository_structure_requires_recursive_tree():
    resolved = resolve_request("list the project structure of my friday repo in github")["resolved_request"]
    assert "github.tree" in resolved
    assert "recursive=true" in resolved
    assert "DO NOT call github.repositories" in resolved
