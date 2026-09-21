import tools  # noqa: F401

from core.runtime.permissions import PermissionLevel
from core.runtime.registry import tool_registry


def test_new_capabilities_are_registered():
    names = {item["name"] for item in tool_registry.list_tools()}
    expected = {
        "memory.remember",
        "memory.recall",
        "research.web.search",
        "research.web.fetch",
        "browser.navigate",
        "browser.read_page",
        "browser.click",
        "browser.type",
        "browser.screenshot",
        "music.play",
        "music.pause",
        "music.next",
        "music.current",
    }
    assert expected <= names


def test_browser_and_music_mutations_are_permission_gated():
    assert tool_registry.get_metadata("browser.click").permission == PermissionLevel.PERMISSION_REQUIRED
    assert tool_registry.get_metadata("browser.type").permission == PermissionLevel.PERMISSION_REQUIRED
    assert tool_registry.get_metadata("music.play").permission == PermissionLevel.PERMISSION_REQUIRED
    assert tool_registry.get_metadata("music.pause").permission == PermissionLevel.PERMISSION_REQUIRED
    assert tool_registry.get_metadata("music.next").permission == PermissionLevel.PERMISSION_REQUIRED


def test_core_tool_surface_is_registered_on_import():
    expected = {
        "filesystem.list",
        "filesystem.read",
        "git.status",
        "git.branch",
        "github.repositories",
        "osiris.weather",
    }
    names = {item["name"] for item in tool_registry.list_tools()}
    assert expected <= names


def test_provider_safe_tool_names_resolve_to_canonical_ids():
    assert tool_registry.resolve_name("filesystem.list") == "filesystem.list"
    assert tool_registry.resolve_name("filesystem__list") == "filesystem.list"
    assert tool_registry.resolve_name("git__status") == "git.status"
    assert tool_registry.get_metadata("git__branch") is not None
