import tools

from core.runtime.capabilities import capability_catalog, list_capabilities


def test_capability_catalog_groups_registered_tools():
    catalog = capability_catalog()
    assert "intelligence" in catalog
    assert "osiris.intelligence" in catalog["intelligence"]
    assert "github.repository" in catalog["intelligence"]
    assert "engineering" in catalog
    assert "git.status" in catalog["engineering"]


def test_capability_listing_can_hide_permission_required_tools():
    safe_groups = list_capabilities(include_permission_required=False)
    safe_names = {name for group in safe_groups for name in group["tools"]}
    assert "filesystem.list" in safe_names
    assert "git.status" in safe_names
    assert "git.commit" not in safe_names
    assert "terminal.execute" not in safe_names
