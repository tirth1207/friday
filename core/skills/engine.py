from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+.#_-]*", re.IGNORECASE)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class SkillMetadata:
    id: str
    name: str
    description: str
    path: str
    source: str = "community"
    version: str | None = None
    author: str | None = None
    license: str | None = None
    tags: tuple[str, ...] = ()
    triggers: tuple[str, ...] = ()
    capabilities: dict[str, bool] = field(default_factory=dict)
    enabled: bool = True
    trusted: bool = False
    priority: int = 0


@dataclass(frozen=True)
class SkillMatch:
    skill: SkillMetadata
    score: float
    reasons: tuple[str, ...] = ()


class SkillParseError(ValueError):
    pass


class SkillEngine:
    """Discover, index and rank portable SKILL.md packages.

    Discovery is intentionally filesystem based: adding a new skill only
    requires copying a skill directory into one of the configured roots.
    The engine refreshes its index when directory contents change, so skills
    can be added or removed without restarting FRIDAY.
    """

    def __init__(self, roots: list[tuple[str, str]] | None = None):
        self.roots = roots or self._default_roots()
        self._skills: dict[str, SkillMetadata] = {}
        self._signatures: dict[str, tuple[int, int]] = {}

    @staticmethod
    def _default_roots() -> list[tuple[str, str]]:
        raw = os.getenv("FRIDAY_SKILLS_DIRS")
        if raw:
            roots: list[tuple[str, str]] = []
            for item in raw.split(os.pathsep):
                if not item.strip():
                    continue
                if "=" in item:
                    source, path = item.split("=", 1)
                    roots.append((source.strip() or "community", path.strip()))
                else:
                    roots.append(("community", item.strip()))
            if roots:
                return roots
        return [
            ("builtin", "skills/builtin"),
            ("community", "skills/community"),
            ("local", "skills/local"),
        ]

    @staticmethod
    def _normalise_id(value: str) -> str:
        value = value.strip().lower()
        value = re.sub(r"[^a-z0-9._-]+", "-", value)
        return value.strip("-._")

    @staticmethod
    def _as_tuple(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,)
        if isinstance(value, list):
            return tuple(str(item) for item in value if str(item).strip())
        return ()

    def _parse_skill(self, path: Path, source: str) -> tuple[SkillMetadata, str]:
        text = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(text)
        if not match:
            raise SkillParseError("SKILL.md must start with YAML frontmatter")
        try:
            data = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            raise SkillParseError(f"invalid YAML frontmatter: {exc}") from exc
        if not isinstance(data, dict):
            raise SkillParseError("frontmatter must be a mapping")

        name = str(data.get("name") or path.parent.name).strip()
        skill_id = self._normalise_id(str(data.get("id") or name))
        description = str(data.get("description") or "").strip()
        if not skill_id or not description:
            raise SkillParseError("name/id and description are required")

        capabilities = data.get("capabilities") or {}
        if not isinstance(capabilities, dict):
            capabilities = {}
        capabilities = {str(k): bool(v) for k, v in capabilities.items()}

        metadata = SkillMetadata(
            id=skill_id,
            name=name,
            description=description,
            path=str(path.parent.resolve()),
            source=source,
            version=str(data["version"]) if data.get("version") is not None else None,
            author=str(data["author"]) if data.get("author") is not None else None,
            license=str(data["license"]) if data.get("license") is not None else None,
            tags=self._as_tuple(data.get("tags")),
            triggers=self._as_tuple(data.get("triggers")),
            capabilities=capabilities,
            enabled=bool(data.get("enabled", True)),
            trusted=bool(data.get("trusted", source == "builtin")),
            priority=int(data.get("priority", 0)),
        )
        return metadata, match.group(2).strip()

    def refresh(self) -> list[SkillMetadata]:
        discovered: dict[str, SkillMetadata] = {}
        for source, root_value in self.roots:
            root = Path(root_value).expanduser()
            if not root.is_absolute():
                root = Path.cwd() / root
            if not root.exists():
                continue
            for skill_file in root.rglob("SKILL.md"):
                try:
                    metadata, _ = self._parse_skill(skill_file, source)
                except (OSError, SkillParseError):
                    continue
                if not metadata.enabled:
                    continue
                # Earlier roots win, allowing a built-in skill to be shadowed
                # only by explicitly placing it in a higher-priority root.
                discovered.setdefault(metadata.id, metadata)
        self._skills = discovered
        return list(self._skills.values())

    def list(self) -> list[SkillMetadata]:
        self.refresh()
        return sorted(self._skills.values(), key=lambda item: (item.source, item.name.lower()))

    def get(self, skill_id: str) -> SkillMetadata | None:
        self.refresh()
        return self._skills.get(self._normalise_id(skill_id))

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token.lower() for token in _WORD_RE.findall(text) if len(token) > 1}

    def match(self, request: str, limit: int = 5) -> list[SkillMatch]:
        self.refresh()
        request_lower = request.lower()
        request_tokens = self._tokens(request)
        matches: list[SkillMatch] = []
        for skill in self._skills.values():
            score = float(skill.priority)
            reasons: list[str] = []
            description_tokens = self._tokens(skill.description)
            overlap = request_tokens & description_tokens
            if overlap:
                score += min(45.0, len(overlap) * 7.0)
                reasons.append(f"description overlap: {', '.join(sorted(overlap)[:5])}")

            for trigger in skill.triggers:
                trigger_lower = trigger.lower().strip()
                if trigger_lower and trigger_lower in request_lower:
                    score += 32.0
                    reasons.append(f"trigger: {trigger}")

            for tag in skill.tags:
                if tag.lower() in request_tokens or tag.lower() in request_lower:
                    score += 12.0
                    reasons.append(f"tag: {tag}")

            if skill.id in request_lower or skill.name.lower() in request_lower:
                score += 20.0
                reasons.append("skill explicitly referenced")

            if skill.trusted:
                score += 2.0
            if skill.source == "builtin":
                score += 3.0
            if score > 0:
                matches.append(SkillMatch(skill=skill, score=score, reasons=tuple(reasons)))

        matches.sort(key=lambda item: (-item.score, item.skill.name.lower()))
        return matches[: max(1, limit)]

    def load(self, skill_id: str, max_chars: int = 12000) -> str | None:
        skill = self.get(skill_id)
        if skill is None:
            return None
        skill_file = Path(skill.path) / "SKILL.md"
        try:
            text = skill_file.read_text(encoding="utf-8")
        except OSError:
            return None
        match = _FRONTMATTER_RE.match(text)
        instructions = match.group(2).strip() if match else text.strip()
        return instructions[:max_chars]

    def context_for_request(self, request: str, limit: int = 5, load_instructions: int = 3) -> str:
        matches = self.match(request, limit=limit)
        if not matches:
            return "No installed skill matched this request."
        lines = ["Relevant installed skills (selected automatically):"]
        for index, match in enumerate(matches, 1):
            skill = match.skill
            caps = ", ".join(k for k, enabled in skill.capabilities.items() if enabled) or "none declared"
            lines.append(
                f"{index}. {skill.id} — {skill.description} "
                f"[source={skill.source}, trusted={skill.trusted}, capabilities={caps}, score={match.score:.1f}]"
            )
        for match in matches[:load_instructions]:
            instructions = self.load(match.skill.id)
            if instructions:
                lines.append(f"\n--- {match.skill.id} instructions ---\n{instructions}")
        return "\n".join(lines)


skill_engine = SkillEngine()
