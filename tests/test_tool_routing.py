from core.memory.context import _is_friday_project_explain_request, _is_repo_structure_request, resolve_request
from core.orchestrator import _extract_github_repository_name, _is_github_repository_explain_request, _is_github_repository_list_request, is_tool_required


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
    assert "repository=<owner>/<repo>" in resolved
    assert "recursive=true" in resolved
    assert "DO NOT call github.repositories" in resolved


def test_friday_project_explanation_is_detected():
    request = "explain my friday project"
    assert _is_friday_project_explain_request(request) is True
    assert is_tool_required(request) is True


def test_friday_project_explanation_resolves_canonical_repository():
    resolved = resolve_request("explain my friday project")["resolved_request"]
    assert "tirth1207/friday" in resolved
    assert "github.tree" in resolved
    assert "recursive=true" in resolved
    assert "Do not return planner JSON" in resolved


def test_friday_repository_name_is_extractable_from_resolved_request():
    resolved = resolve_request("explain my friday project")["resolved_request"]
    assert _extract_github_repository_name(resolved) == "tirth1207/friday"
    assert _is_github_repository_explain_request(resolved) is True


def test_repository_specific_explanation_is_not_repository_listing():
    request = "explain tirth1207/friday repository"
    assert _is_github_repository_explain_request(request) is True
    assert _is_github_repository_list_request(request) is False
