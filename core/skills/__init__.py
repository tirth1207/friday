"""FRIDAY's pluggable skill system.

Skills are portable directories containing a SKILL.md file. Metadata is indexed
for cheap discovery and the full instructions are loaded only for selected
skills. Community skills can be dropped into a configured directory without
changing FRIDAY's core code.
"""

from .engine import SkillEngine, SkillMatch, SkillMetadata, skill_engine

__all__ = ["SkillEngine", "SkillMatch", "SkillMetadata", "skill_engine"]
