from core.github_repository_contents import EXPLANATION_CONTRACT, _build_repository_map


def test_repository_explanation_contract_requires_structured_markdown_sections():
    assert EXPLANATION_CONTRACT["format"] == "Markdown"
    assert EXPLANATION_CONTRACT["required_sections"][:3] == [
        "## Overview",
        "## What the project does",
        "## Main features",
    ]
    assert "Separate observed facts from reasonable inferences; label inferences explicitly." in EXPLANATION_CONTRACT["rules"]


def test_repository_map_separates_root_files_and_directories():
    tree = [
        {"path": "README.md", "type": "blob"},
        {"path": "src", "type": "tree"},
        {"path": "src/main.ts", "type": "blob"},
        {"path": "package.json", "type": "blob"},
    ]

    result = _build_repository_map(tree)

    assert result["root_files"] == ["README.md", "package.json"]
    assert result["top_level_directories"] == ["src"]
