from core.orchestrator import is_tool_required


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
