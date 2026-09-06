import re

from core.orchestrator_structured import _extract_pseudo_tool_call, _normalize_github_arguments
from core.runtime.langchain_tools import get_langchain_tools, registry_tool_name


VALID_PROVIDER_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


def test_all_langchain_tool_names_match_provider_constraints():
    tools = get_langchain_tools()
    assert tools
    for tool in tools:
        assert VALID_PROVIDER_NAME.fullmatch(tool.name), tool.name


def test_dotted_registry_names_are_mapped_back_to_internal_names():
    assert registry_tool_name("filesystem__list") == "filesystem.list"
    assert registry_tool_name("github__file__read") == "github.file.read"
    assert registry_tool_name("os__path__exists") == "os.path.exists"
    assert registry_tool_name("github.tree") == "github.tree"


def test_github_arguments_normalize_common_model_aliases():
    result = _normalize_github_arguments(
        "github.tree",
        {"repo_full_name": "tirth1207/ai_test", "branch": "main", "recursive": True},
    )
    assert result == {
        "repository": "tirth1207/ai_test",
        "ref": "main",
        "recursive": True,
    }


def test_pseudo_tool_call_json_is_recovered():
    call = _extract_pseudo_tool_call(
        '{"tool":"github.tree","arguments":{"repo_full_name":"tirth1207/ai_test","recursive":true}}'
    )
    assert call == (
        "github.tree",
        {"repo_full_name": "tirth1207/ai_test", "recursive": True},
    )


def test_fenced_pseudo_tool_call_json_is_recovered():
    call = _extract_pseudo_tool_call(
        "```json\n{\"tool\":\"github.file.read\",\"arguments\":{\"repository\":\"tirth1207/friday\",\"path\":\"README.md\"}}\n```"
    )
    assert call is not None
    assert call[0] == "github.file.read"
    assert call[1]["repository"] == "tirth1207/friday"
