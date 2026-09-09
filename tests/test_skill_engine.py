import os
from pathlib import Path

from core.skills.engine import SkillEngine


def _write_skill(root: Path, name: str, description: str, triggers: str = ""):
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\ntriggers: [{triggers}]\ntags: [python, coding]\ntrusted: true\n---\n\n# Instructions\n\nUse the skill.\n",
        encoding="utf-8",
    )


def test_discovers_skills_recursively(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "python-expert", "Expert help with Python programming", "python, py")
    engine = SkillEngine(roots=[("community", str(root))])

    skills = engine.list()

    assert [skill.id for skill in skills] == ["python-expert"]
    assert skills[0].source == "community"


def test_matches_trigger_and_description(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "python-expert", "Expert help with Python programming", "python, py")
    _write_skill(root, "database", "Design and optimize SQL databases", "sql, database")
    engine = SkillEngine(roots=[("community", str(root))])

    matches = engine.match("debug this Python function", limit=2)

    assert matches
    assert matches[0].skill.id == "python-expert"
    assert matches[0].score > matches[1].score


def test_loads_only_skill_body(tmp_path):
    root = tmp_path / "skills"
    _write_skill(root, "python-expert", "Expert help with Python programming", "python")
    engine = SkillEngine(roots=[("community", str(root))])

    body = engine.load("python-expert")

    assert body is not None
    assert "# Instructions" in body
    assert "description:" not in body


def test_environment_roots_support_multiple_sources(tmp_path, monkeypatch):
    builtin = tmp_path / "builtin"
    community = tmp_path / "community"
    _write_skill(builtin, "core-skill", "Built in skill")
    _write_skill(community, "community-skill", "Community skill")
    monkeypatch.setenv("FRIDAY_SKILLS_DIRS", os.pathsep.join([f"builtin={builtin}", f"community={community}"]))

    engine = SkillEngine()

    assert {skill.id for skill in engine.list()} == {"core-skill", "community-skill"}
