import re

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
